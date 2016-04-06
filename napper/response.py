# napper -- A REST Client for Python
# Copyright (C) 2016 by Yann Kaiser and contributors.
# See AUTHORS and COPYING for details.
import collections.abc

from . import request, restspec
from .util import requestmethods, rag, getattribute_dict, metafunc, METHODS


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
        return self.val[i]

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
        data = rag(req, '_raw_data')
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
            plink_name = site.spec.permalink_hint(self._real_object)
            try:
                addr = self._real_object[plink_name]
            except KeyError:
                pass
            else:
                return getattr(PermalinkString(addr, request=self.request),
                               name)
        try:
            return self._real_object[name]
        except KeyError:
            try:
                name_hint = site.spec.is_permalink_attr.hint(
                    name, self._real_object)
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
                    name, item, self._real_object):
                return PermalinkString(item, request=self.request)
            return item
        return upgrade_object(item, self.request,
                              {'parent': 'self', 'attribute': name})
