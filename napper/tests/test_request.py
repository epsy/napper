# napper -- A REST Client for Python
# Copyright (C) 2016 by Yann Kaiser and contributors.
# See AUTHORS and COPYING for details.
from .util import AioTests
from .. import CrossOriginRequestError
from ..request import Request
from .. import util


class RequestBuilderTests(AioTests):
    def assertAttrEqual(self, obj, attr, exp):
        self.assertEqual(util.rag(obj, attr), exp)

    def assertIEqual(self, left, right):
        self.assertEqual(left.lower(), right.lower())

    def assertRequestEqual(self, req, exp_method, exp_url):
        self.assertIsInstance(req, Request)
        self.assertIEqual(util.rag(req, 'method'), exp_method)
        self.assertEqual(util.rag(req, 'url'), exp_url)

    def test_site(self):
        with self.make_site('http://www.example.org/') as site:
            self.assertIs(util.rag(site, 'site'), site)
            self.assertAttrEqual(site, 'address', 'http://www.example.org')

    def test_site_deep(self):
        with self.make_site('http://www.example.org/apath') as site:
            self.assertIs(util.rag(site, 'site'), site)
            self.assertAttrEqual(site, 'address', 'http://www.example.org/apath')

    def test_site_deep2(self):
        with self.make_site('http://www.example.org/apath/subpath') as site:
            self.assertIs(util.rag(site, 'site'), site)
            self.assertAttrEqual(site, 'address', 'http://www.example.org/apath/subpath')

    def test_get_root(self):
        self.assertRequestEqual(self.site.get(), 'get', 'http://www.example.org/')

    def test_post_root(self):
        self.assertRequestEqual(self.site.post(), 'post', 'http://www.example.org/')

    def test_put_root(self):
        self.assertRequestEqual(self.site.put(), 'put', 'http://www.example.org/')

    def test_delete_root(self):
        self.assertRequestEqual(self.site.delete(), 'delete', 'http://www.example.org/')

    def test_call_root(self):
        with self.assertRaises(TypeError):
            self.site()

    def test_call_path(self):
        with self.assertRaises(TypeError):
            self.site.apath()

    def test_call_subpath(self):
        with self.assertRaises(TypeError):
            self.site.apath.subpath()

    def test_trailing_slash(self):
        with self.make_site('http://www.example.org/apath/') as site:
            self.assertRequestEqual(
                site.subpath.get(),
                'get', 'http://www.example.org/apath/subpath')
        with self.make_site('http://www.example.org/apath') as site:
            self.assertRequestEqual(
                site.subpath.get(),
                'get', 'http://www.example.org/apath/subpath')

    def test_site_attrs(self):
        with self.make_site('http://www.example.org/apath') as site:
            subp = site.subpath
            sreq = subp.get()
            ureq = subp.get()
            site_attr = util.rag(subp, 'site')
            subp_attr = util.rag(subp, 'site')
            sreq_attr = util.rag(sreq, 'site')
            ureq_attr = util.rag(ureq, 'site')
            self.assertEqual(site_attr.address, 'http://www.example.org/apath')
            self.assertEqual(subp_attr.address, 'http://www.example.org/apath')
            self.assertEqual(sreq_attr.address, 'http://www.example.org/apath')
            self.assertEqual(ureq_attr.address, 'http://www.example.org/apath')


class RequestTests(AioTests):
    async def test_values(self):
        resp = await self.request('{"a": 42, "ham": ["eggs", "spam"]}')
        self.assertEqual(resp['a'], 42)
        self.assertEqual(resp.a, 42)
        self.assertEqual(resp['ham'][0], "eggs")
        self.assertEqual(resp['ham'][1], "spam")

    async def test_await_twice(self):
        with self.text_response('{"a": 42, "ham": ["eggs", "spam"]}'):
            resp1 = await self.req
        resp2 = await self.req
        self.assertEqual(resp1['a'], 42)
        self.assertEqual(resp1.a, 42)
        self.assertEqual(resp1['ham'][0], "eggs")
        self.assertEqual(resp1['ham'][1], "spam")
        self.assertEqual(resp2['a'], 42)
        self.assertEqual(resp2.a, 42)
        self.assertEqual(resp2['ham'][0], "eggs")
        self.assertEqual(resp2['ham'][1], "spam")

    async def test_aiter(self):
        resp = await self.request('{"ham": ["eggs", "spam"]}')
        items = []
        async for val in resp.ham:
            items.append(val)
        self.assertEqual(items, ['eggs', 'spam'])

    async def test_aiter_direct(self):
        resp = await self.request('["eggs", "spam"]')
        items = []
        async for val in resp:
            items.append(val)
        self.assertEqual(items, ['eggs', 'spam'])

    async def test_aiter_direct_noawait(self):
        with self.text_response('["eggs", "spam"]'):
            items = []
            async for val in self.req:
                items.append(val)
        self.assertEqual(items, ['eggs', 'spam'])

    async def test_resp_property_attr(self):
        with self.text_response('{"abc": "def"}', 200):
            self.assertEqual((await self.req.abc), 'def')

    async def test_resp_property_item(self):
        with self.text_response('{"abc": "def"}', 200):
            self.assertEqual((await self.req['abc']), 'def')

    async def test_resp_property_index(self):
        with self.text_response('["abc", "def"]', 200):
            self.assertEqual((await self.req[0]), 'abc')
            self.assertEqual((await self.req[1]), 'def')

    async def test_multi_property_attr(self):
        with self.text_response('{"abc": {"defh": "xyz"}}'):
            self.assertEqual((await self.req.abc.defh), 'xyz')

    async def test_multi_property_item(self):
        with self.text_response('{"abc": {"defh": "xyz"}}'):
            self.assertEqual((await self.req['abc']['defh']), 'xyz')

    async def test_multi_property_index(self):
        with self.text_response('["abc", ["def", "xyz"]]'):
            self.assertEqual((await self.req[1][0]), 'def')
            self.assertEqual((await self.req[1][1]), 'xyz')

    async def test_follow_request(self):
        with self.text_responses(
                ('{"thing": "http://www.example.org/other_res"}', 200),
                ('"spam"', 200)):
            self.assertEqual((await self.req.thing.get()), 'spam')

    async def test_follow_request_attr(self):
        with self.text_responses(
                ('{"thing": "http://www.example.org/other_res"}', 200),
                ('{"ham": "spam"}', 200)):
            self.assertEqual((await self.req.thing.get().ham), 'spam')

    async def test_follow_xsite(self):
        with self.text_response('{"thing": "http://www.example.com/"}'):
            nextreq = await self.req.thing
        with self.assertRaises(CrossOriginRequestError):
            with self.text_response('"I am the danger"'):
                await nextreq.get()

    async def test_get_params(self):
        req = self.site.path.get(spam="ham", eggs=42)
        with self.text_response("0") as mock:
            await req
            self.assertRequestMade(
                mock, 'GET', 'http://www.example.org/path',
                params={'spam': 'ham', 'eggs': 42})

    async def test_post_params(self):
        req = self.site.path.post(spam="ham", eggs=42)
        with self.text_response("0") as mock:
            await req
            self.assertRequestMade(
                mock, 'POST', 'http://www.example.org/path',
                params={'spam': 'ham', 'eggs': 42})

    async def test_post_body(self):
        req = self.site.path.post({'spam': "ham", 'eggs': 42}, param="val")
        with self.text_response("0") as mock:
            await req
            self.assertRequestMade(
                mock, 'POST', 'http://www.example.org/path',
                params={'param': "val"}, data={'spam': 'ham', 'eggs': 42})
