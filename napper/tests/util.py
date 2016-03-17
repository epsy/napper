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
from ..site import Site, SiteFactory
from ..request import Request


class FakeTextResponse(object):
    def __init__(self, response, status=200):
        self._response = response
        self.status = status

    async def text(self, encoding=None):
        return self._response

    async def json(self, encoding=None, loads=json.loads):
        return loads(self._response)

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


class AioTestsMeta(type):
    def __new__(cls, name, bases, members):
        for name, value in dict(members).items():
            if name.startswith('test_') and inspect.iscoroutinefunction(value):
                members['async_' + name] = value
                members[name] = _make_asyncwrapper(value)
        return type.__new__(cls, name, bases, members)


class AioTests(unittest.TestCase, metaclass=AioTestsMeta):
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
        factory = SiteFactory(address)
        return factory()

    def setUp(self):
        super().setUp()
        self.sfactory = factory = SiteFactory('http://www.example.org')
        self.site = Site(factory, factory())
        self.req = self.site.res.get()

    def tearDown(self):
        super().setUp()
        session = rag(self.site, 'session')
        session.close()
        if not self.unclosed_ignored:
            AioTests.unclosed_ignored = True
            warnings.filterwarnings(
                'ignore', 'unclosed event loop', ResourceWarning)

    def read_restspec(self, **spec):
        spec.setdefault('base_address', 'http://www.example.org')
        self.sfactory._read_restspec(io.StringIO(json.dumps(spec)))

    def text_response(self, text, status=200, *, req=None):
        return self.text_responses((text, status), req=req)

    def text_responses(self, *text_status_pairs, req=None):
        if req is None:
            req = self.req
        site = rag(req, 'site')
        return patch.object(site.session, 'request', side_effect=(
            _fut_result(FakeTextResponse(text, status))
            for text, status in text_status_pairs
        ))

    def assertRequestMade(self, mock, method, url, params={}, **kwargs):
        return mock.assert_called_once_with(
            method, url, params=params, **kwargs)

    async def request(self, resp_text):
        with self.text_response(resp_text) as mock:
            resp = await self.req
            self.assertRequestMade(mock, 'GET', 'http://www.example.org/res')
        return resp
