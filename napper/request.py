# napper -- A REST Client for Python
# Copyright (C) 2016 by Yann Kaiser and contributors.
# See AUTHORS and COPYING for details.
import json
import asyncio

import aiohttp

from .restspec import RestSpec
from .response import upgrade_object
from .errors import CrossOriginRequestError
from .util import m, rag, METHODS, metafunc, getattribute_common


class SessionFactory:
    def __init__(self, spec):
        self.spec = spec

    @classmethod
    def from_address(cls, address):
        spec = RestSpec()
        spec.address = address.rstrip('/')
        return cls(spec)

    def __repr__(self):
        return "<SessionFactory [{}]>".format(self.address)

    def __call__(self, session=None, proxy=None):
        """
        :param session: An `aiohttp.ClientSession` object
        :param proxy: If session is unset, an http proxy addess. See
            the documentation on `aiohttp.ProxyConnector`
        """
        if session is None:
            conn = None
            if proxy is not None:
                conn = aiohttp.ProxyConnector(proxy=proxy)
            session = aiohttp.ClientSession(connector=conn)
        return Session(self.spec, session)


_unset = object()


class Session:
    @property
    def site(self):
        return self

    def __init__(self, spec, session, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.spec = spec
        self.session = session

    @metafunc
    def __repr__(self):
        return "<Site [{0.spec.address}]>".format(self)

    def __enter__(self):
        return self

    def __exit__(self, *args, **kwargs):
        rag(self, 'session').close()

    close = __exit__

    @metafunc
    def __getitem__(self, name):
        return RequestBuilder(self, (name,))

    __getattribute__ = getattribute_common(__getitem__)

    @metafunc
    def build_request(self, method, path, **kwargs):
        jpath = self.spec.join_path(path)
        return Request(self, method, jpath, **kwargs)

    @metafunc
    def _request(self, method, url, *args, **kwargs):
        if not self.spec.is_same_origin(url):
            raise CrossOriginRequestError(self, method, url, (), {})
        return self.session.request(method, url, *args, **kwargs)


class RequestBuilder(object):
    def __init__(self, site, path):
        self.site = site
        self.spec = rag(site, 'spec')
        self.path = path

    @metafunc
    def __repr__(self):
        return '<RequestBuilder [{0}/{1}]>'.format(
                rag(self.site, 'address'),
                '/'.join(self.path))

    @metafunc
    def __call__(self, *args, **params):
        path = self.path
        kwargs = {}
        if not path:
            raise TypeError("Cannot call this RequestBuilder instance."
                            " (Forgot to use '.get()' ?)")
        elif path[-1] == 'request':
            method, = args
        else:
            *path, method = path
            kwargs['params'] = params
            if args:
                kwargs['data'], = args
        if method not in METHODS:
            raise TypeError(
                "{0!r} is not a request method".format(method))
        return self.site.build_request(method, path, **kwargs)

    @metafunc
    def __getitem__(self, name):
        return RequestBuilder(self.site, self.path + (name,))

    __getattribute__ = getattribute_common(__getitem__)


class Request(object):
    def __init__(self, site, method, url, **kwargs):
        """
        :param site: a `Site` instance passed through `.util.m`
        :param method: a request method ('get', 'post', ...)
        :param url: a full request URL
        """
        self.site = site
        self.method = method.upper()
        self.url = url
        self.kwargs = kwargs

    def __repr__(self):
        return '<Request [{0} {1}]>'.format(
            rag(self, 'method'), rag(self, 'url'))

    @getattribute_common
    def __getattribute__(self, name):
        return MultiRequestBuilder(self, (('attr', name),))

    def __getitem__(self, key):
        return MultiRequestBuilder(self, (('item', key),))

    @metafunc
    @asyncio.coroutine
    def _read_result(self):
        r = yield from self.site._request(
            self.method, self.url, **self.kwargs)
        try:
            self._raw_data = json.loads((yield from r.text()))
        finally:
            r.close()

    @metafunc
    def __await__(self):
        try:
            self._raw_data
        except AttributeError:
            yield from self._read_result()
        return upgrade_object(None, self._raw_data, None, self)

    __iter__ = __await__ # compatibility with yield from (i.e. in __await__)

    async def __aiter__(self):
        """Iterate over the elements returned from the request"""
        resp = await self
        return await type(resp).__aiter__(resp)


# def find_permalink(obj, name):
#     link = None
#     try:
#         link = obj[name + '_url']
#     except KeyError:
#         raise AttributeError(name)
#     return Permalink(link)


def format_action(action):
    typ, *args = action
    if typ == 'attr':
        return '.' + args[0]
    elif typ == 'item':
        return '[{0!r}]'.format(args[0])
    elif typ == 'call':
        return '(' + ', '.join(
            '{0}={1!r}'.format(k,v) for k,v in args[0].items()) + ')'
    raise ValueError(action)


class MultiRequestBuilder(object):
    def __init__(self, datasource, actions):
        self.datasource = datasource
        self.actions = actions

    @metafunc
    def __repr__(self):
        return '<MultiRequestBuilder: {0}{1}>'.format(
            self.datasource,
            ''.join(format_action(a) for a in self.actions)
        )

    @metafunc
    def stack_action(self, typ, *args):
        return MultiRequestBuilder(
            self.datasource, self.actions + ((typ, *args),))

    @getattribute_common
    def __getattribute__(self, name):
        return m(self).stack_action('attr', name)

    def __getitem__(self, key):
        return m(self).stack_action('item', key)

    def __call__(self, **kwargs):
        return m(self).stack_action('call', (), kwargs)

    @metafunc
    def __await__(self):
        ret = yield from self.datasource
        for typ, *args in self.actions:
            if typ == 'attr':
                attr, = args
                ret = getattr(ret, attr)
            elif typ == 'item':
                key, = args
                ret = ret[key]
            elif typ == 'call':
                fargs, fkwargs = args
                ret = yield from ret(*fargs, **fkwargs)
            else:
                raise NotImplementedError('Unknown action ' + typ)
        #while not isinstance(ret, JsonResponse):
        #    ret = yield from ret
        return ret

    #__iter__ = __await__ # compatibility with yield from (i.e. in __await__)
