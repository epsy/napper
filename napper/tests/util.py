# napper -- A REST Client for Python
# Copyright (C) 2016 by Yann Kaiser and contributors.
# See AUTHORS and COPYING for details.
import unittest
from unittest.mock import patch
import inspect
from functools import wraps
import asyncio
import json
import warnings
import io

from ..util import rag
from ..request import Request, SessionFactory
from .. import restspec


class FakeTextResponse(object):
    def __init__(self, response, status=200):
        if isinstance(response, bytes):
            self._bytes_response = response
        else:
            self._response = response
        self.status = status

    async def text(self, encoding=None):
        return self._response

    async def json(self, encoding=None, loads=json.loads):
        return loads(self._response)

    async def read(self):
        return self._bytes_response

    def close(self):
        pass


def _fut_result(result):
    ret = asyncio.Future()
    ret.set_result(result)
    return ret


def _make_asyncwrapper(func):
    @wraps(func)
    def asyncwrapper(self):
        loop = asyncio.get_event_loop()
        loop.run_until_complete(func(self))
    return asyncwrapper


class TestsMeta(type):
    def __new__(cls, name, bases, members):
        for key, value in dict(members).items():
            if key.startswith('test_') and inspect.iscoroutinefunction(value):
                members['async_' + key] = value
                members[key] = _make_asyncwrapper(value)
        return type.__new__(cls, name, bases, members)


class Tests(unittest.TestCase, metaclass=TestsMeta):
    unclosed_ignored = False

    def assertAttrEqual(self, obj, attr, exp):
        self.assertEqual(rag(obj, attr), exp)

    def assertAttrIs(self, obj, attr, exp):
        self.assertIs(rag(obj, attr), exp)

    def assertIEqual(self, left, right):
        self.assertEqual(left.lower(), right.lower())

    def assertRequestEqual(self, req, exp_method, exp_url):
        self.assertIsInstance(req, Request)
        self.assertIEqual(rag(req, 'method'), exp_method)
        self.assertEqual(rag(req, 'url'), exp_url)

    def make_site(self, address='http://www.example.org'):
        return SessionFactory.from_address(address)()

    def setUp(self):
        asyncio.get_event_loop().run_until_complete(self.asyncSetUp())
        super().setUp()
        if not self.unclosed_ignored:
            Tests.unclosed_ignored = True
            warnings.filterwarnings(
                'ignore', 'unclosed event loop', ResourceWarning)
        self.req = self.site.res.get()

    async def asyncSetUp(self):
        self.sfactory = factory = SessionFactory.from_address(
                                                    'http://www.example.org')
        sessionmanager = factory()
        aexit = type(sessionmanager).__aexit__
        aenter = type(sessionmanager).__aenter__(sessionmanager)
        self.site = await aenter
        self.addAsyncCleanup(aexit(sessionmanager, None, None, None))

    def addAsyncCleanup(self, coroutine):
        @self.addCleanup
        def asyncCleanup():
            loop = asyncio.get_event_loop()
            loop.run_until_complete(coroutine)

    def read_restspec(self, **spec):
        spec.setdefault('base_address', 'http://www.example.org')
        self.sfactory.spec._read_spec_file(io.StringIO(json.dumps(spec)))

    def to_config_dict(self, obj):
        return json.loads(json.dumps(obj),
                          object_hook=restspec.WarnOnUnusedKeys)

    def text_response(self, text, status=200, *, req=None):
        return self.text_responses(text, final_status=status, req=req)

    def text_responses(self, *responses, final_status=200, req=None):
        if req is None:
            req = self.req
        site = rag(req, 'site')
        return patch.object(site.session, 'request', side_effect=(
            _fut_result(FakeTextResponse(text, final_status if not i else 200))
            for i, text in enumerate(responses, 1 - len(responses))
        ))

    def assertRequestMade(self, mock, method, url, params={}, **kwargs):
        return mock.assert_called_once_with(
            method, url, params=params, **kwargs)

    async def request(self, resp_text):
        with self.text_response(resp_text) as mock:
            resp = await self.req
            self.assertRequestMade(mock, 'GET', 'http://www.example.org/res')
        return resp
