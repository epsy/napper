# napper -- A REST Client for Python
# Copyright (C) 2016 by Yann Kaiser and contributors.
# See AUTHORS and COPYING for details.
import asyncio
import json
import collections.abc
from functools import partial

from . import request, restspec
from .util import requestmethods, rag, getattribute_dict, metafunc, METHODS


@asyncio.coroutine
def convert_json(request, response):
    return upgrade_object(
        json.loads((yield from response.text()),
                   object_hook=partial(ResponseObject, request=request)),
        request)


def upgrade_object(val, request):
    if isinstance(val, str):
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
        if isinstance(item, str):
            if self.request.site.spec.is_permalink_attr(
                    name, item, self._real_object):
                return PermalinkString(item, request=self.request)
            return item
        return upgrade_object(item, self.request)
