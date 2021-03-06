# napper -- A REST Client for Python
# Copyright (C) 2016 by Yann Kaiser and contributors.
# See AUTHORS and COPYING for details.
import json
import collections.abc

import aiohttp

from . import request, restspec
from .util import requestmethods, rag, getattribute_dict, metafunc, METHODS, UniversalDetector


class ResponseType:
    async def parse_response(self, response):
        return response

    def upgrade(self, data, request):
        return data


class TextResponse(ResponseType):
    def __init__(self, *, encoding=None, **kwargs):
        super().__init__(**kwargs)
        self.encoding = encoding

    async def parse_response(self, response):
        response = await super().parse_response(response)
        return await response.text(encoding=self.encoding)


class BytesResponse(ResponseType):
    async def parse_response(self, response):
        return await (await super().parse_response(response)).read()


class JsonResponse(TextResponse):
    async def parse_response(self, response):
        return json.loads(await super().parse_response(response))

    def upgrade(self, data, request):
        return upgrade_object(super().upgrade(data, request), request)


class DrippingResponse(ResponseType):
    def __init__(self, item_type, *, separator=b'\n', include_separator=True,
                                     remainder='return'):
        self.item_type = item_type
        self.separator = separator
        self.include_separator = include_separator
        self.remainder = remainder

    async def parse_response(self, response):
        return response

    def upgrade(self, data, request):
        return ResponseReleaser(Dripper(self, data, request), data)


class DrippedBytesResponse(BytesResponse):
    async def parse_response(self, dripper_value):
        dripper, value = dripper_value
        return value


class DrippedTextResponse(TextResponse):
    async def _get_encoding(self, dripper, value):
        if self.encoding is not None:
            return self.encoding

        response = dripper.response

        content_type = response.headers.get(aiohttp.hdrs.CONTENT_TYPE, '').lower()
        _, _, _, params = aiohttp.helpers.parse_mimetype(content_type)
        self.encoding = params.get('charset')

        if self.encoding is not None:
            return self.encoding

        reader = dripper.response.content

        detector = UniversalDetector()
        detector.feed(value)
        detector.feed(reader._buffer)

        pos = len(reader._buffer)

        while not detector.done and not reader._eof:
            await reader._wait_for_data('DrippedTextResponse._get_encoding')
            detector.feed(reader._buffer[pos:])
            pos = len(reader._buffer)

        if not detector.done:
            detector.close()

        self.encoding = detector.result['encoding']
        return self.encoding

    async def parse_response(self, dripper_value):
        dripper, value = dripper_value
        enc = await self._get_encoding(dripper, value)
        return value.decode(enc)


class ResponseReleaser:
    def __init__(self, obj, response):
        self.obj = obj
        self.response = response

    async def __aenter__(self):
        return self.obj

    async def __aexit__(self, typ, val, tb):
        await self.response.release()


class Dripper:
    def __init__(self, response_type, response, request):
        self.response_type = response_type
        self.response = response
        self.request = request
        self._buffer = b''
        self._finished = False

        self.item_type = self.response_type.item_type
        self.item_type.__class__ = self._upgrade_item_type(type(self.item_type))

    def _upgrade_item_type(self, typ):
        if issubclass(typ, BytesResponse):
            mixin = DrippedBytesResponse
        elif issubclass(typ, TextResponse):
            mixin = DrippedTextResponse
        else:
            raise TypeError("Unsupported type for dripping: {}".format(typ))

        if typ in [BytesResponse, TextResponse]:
            return mixin
        else:
            return type('Dripped' + typ.__name__, (typ, mixin), {})

    async def __aiter__(self):
        return self

    async def __anext__(self):
        if self._finished:
            raise StopAsyncIteration
        reader = self.response.content
        rt = self.response_type
        sep = rt.separator
        while sep not in reader._buffer:
            if reader._eof:
                self._finished = True
                if rt.remainder == 'return':
                    remainder = await reader.read()
                    if remainder:
                        return await self.return_value(remainder)
                elif rt.remainder == 'ignore':
                    pass
                elif rt.remainder == 'error':
                    raise ValueError("Data remains after last separator")
                else:
                    raise ValueError("Bad value for remainder handling")
                raise StopAsyncIteration
            await reader._wait_for_data('dripper.__anext__')
        return await self.return_value(
            await reader.read(len(sep) + reader._buffer.index(sep)))

    async def return_value(self, value):
        parsed = await self.item_type.parse_response((self, value))
        return self.item_type.upgrade(parsed, self.request)


def upgrade_object(val, request, context=None):
    spec = request.site.spec
    if context is None:
        context = {}
    context.setdefault('root', val)
    if spec.is_paginator_object(val, context):
        return PaginatorObject(val, request)
    elif isinstance(val, dict):
        return ResponseObject(val, request)
    elif isinstance(val, str):
        return PermalinkString(val, request=request)
    elif isinstance(val, list):
        return ResponseList(val, request=request)
    else:
        return val


class ResponseList(collections.abc.Sequence):
    def __init__(self, val, request):
        self.request = request
        self.val = val

    def __repr__(self):
        return repr(self.val)

    def __getitem__(self, i):
        return self.request.response_type.upgrade(self.val[i], self.request)

    def __len__(self):
        return len(self.val)

    async def __aiter__(self):
        return ResponseListIterator(self)


class PaginatorObject(collections.abc.Sequence):
    def __init__(self, val, request):
        self.request = request
        self.spec = request.site.spec
        self.paginator = val
        self.pages = [val]
        self.done = False
        self.cache = list(self.spec.paginator_content(val))

    def __repr__(self):
        return '<PaginatorObject {0}{1}>'.format(
            self.cache, '...' if not self.done else '')

    def __getitem__(self, i):
        return self.cache[i]

    async def item(self, i):
        while not self.done and len(self.cache) <= i:
            await self._fetch_next_page()
        if len(self.cache) > i:
            return self.cache[i]
        else:
            raise IndexError(i)

    async def _fetch_next_page(self):
        try:
            url = self.spec.paginator_next_url(self.pages[-1])
        except restspec.NoValue:
            self.done = True
            return
        req = request.Request(self.request.site, 'get', url)
        await req
        data = await rag(req, 'parsed_response')()
        self.pages.append(data)
        self.cache.extend(self.spec.paginator_content(data))

    def __len__(self, i):
        return len(self.val)

    async def __aiter__(self):
        return PaginatorIterator(self)


class PaginatorIterator:
    def __init__(self, p):
        self.p = p
        self.index = 0

    async def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            ret = await self.p.item(self.index)
        except IndexError:
            raise StopAsyncIteration
        self.index += 1
        return ret


class ResponseListIterator:
    def __init__(self, val):
        self.ito = iter(val)

    async def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self.ito)
        except StopIteration as exc:
            raise StopAsyncIteration from exc


@requestmethods
class PermalinkString(str):
    def __new__(cls, *args, request, **kwargs):
        ret = super().__new__(cls, *args, **kwargs)
        if isinstance(request, type(restspec)): raise TypeError
        ret.origin_request = request
        return ret

    def request(self, method, *args, **kwargs):
        site = rag(self.origin_request, 'site')
        return request.Request(site, method, self)


class ResponseObject(collections.abc.Mapping):
    def __init__(self, value, request):
        self.value = value
        self.request = request

    @metafunc
    def __repr__(self):
        return repr(self.value)

    @metafunc
    def __len__(self):
        return len(self.value)

    @metafunc
    def __iter__(self):
        return iter(self.value)

    @getattribute_dict
    @metafunc
    def __getattribute__(self, name):
        site = self.request.site
        if name in METHODS or name == 'request':
            try:
                addr = site.spec.get_object_permalink(self._real_object)
            except restspec.NoValue:
                pass
            else:
                return getattr(PermalinkString(addr, request=self.request),
                               name)
        try:
            return self._real_object[name]
        except KeyError:
            try:
                name_hint = site.spec.is_permalink_attr.attr_name_hint(name)
            except restspec.NoValue:
                raise AttributeError(name) from None
            try:
                return self._real_object[name_hint]
            except KeyError:
                raise AttributeError(name) from None

    @metafunc
    def __getitem__(self, name):
        item = self.value[name]
        spec = self.request.site.spec
        if isinstance(item, str):
            if spec.is_permalink_attr(
                    item, {'attribute': name, 'parent': self._real_object}):
                return PermalinkString(item, request=self.request)
            return item
        return upgrade_object(item, self.request,
                              {'parent': 'self', 'attribute': name})
