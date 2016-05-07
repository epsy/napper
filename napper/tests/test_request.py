# napper -- A REST Client for Python
# Copyright (C) 2016 by Yann Kaiser and contributors.
# See AUTHORS and COPYING for details.
from .util import Tests
from .. import CrossOriginRequestError
from ..request import Request, SessionFactory
from ..response import PermalinkString
from .. import util, restspec, errors


class RequestBuilderTests(Tests):
    def test_site(self):
        with self.make_site('http://www.example.org/') as site:
            self.assertIs(util.rag(site, 'site'), site)
            self.assertEqual(util.rag(site, 'spec').address,
                             'http://www.example.org')

    def test_site_deep(self):
        with self.make_site('http://www.example.org/apath') as site:
            self.assertIs(util.rag(site, 'site'), site)
            self.assertEqual(util.rag(site, 'spec').address,
                             'http://www.example.org/apath')

    def test_site_deep2(self):
        with self.make_site('http://www.example.org/apath/subpath') as site:
            self.assertIs(util.rag(site, 'site'), site)
            self.assertEqual(util.rag(site, 'spec').address,
                             'http://www.example.org/apath/subpath')

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
            site_attr = util.rag(subp, 'site').spec
            subp_attr = util.rag(subp, 'site').spec
            sreq_attr = util.rag(sreq, 'site').spec
            ureq_attr = util.rag(ureq, 'site').spec
            self.assertEqual(site_attr.address, 'http://www.example.org/apath')
            self.assertEqual(subp_attr.address, 'http://www.example.org/apath')
            self.assertEqual(sreq_attr.address, 'http://www.example.org/apath')
            self.assertEqual(ureq_attr.address, 'http://www.example.org/apath')


class RequestTests(Tests):
    def setUp(self):
        super().setUp()
        self.matcher = restspec.Conditional.from_restspec(self.to_config_dict(
            [{'context': 'attribute'}, {'matches': {'pattern': '^thing$'}}]
            ))


class FollowTests(RequestTests):
    async def test_follow_request(self):
        util.rag(self.site, 'spec').is_permalink_attr = self.matcher
        with self.text_responses(
                '{"thing": "http://www.example.org/other_res"}', '"spam"'):
            self.assertEqual((await self.req.thing.get()), 'spam')

    async def test_follow_request_attr(self):
        util.rag(self.site, 'spec').is_permalink_attr = self.matcher
        with self.text_responses(
                '{"thing": "http://www.example.org/other_res"}',
                '{"ham": "spam"}'):
            self.assertEqual((await self.req.thing.get().ham), 'spam')

    async def test_follow_xsite(self):
        util.rag(self.site, 'spec').is_permalink_attr = self.matcher
        with self.text_response('{"thing": "http://www.example.com/"}'):
            nextreq = await self.req.thing
        with self.assertRaises(CrossOriginRequestError):
            with self.text_response('"I am the danger"'):
                await nextreq.get()

    async def test_permalink_attr(self):
        self.read_restspec(permalink_attribute=[
            {'context': 'attribute'}, {'matches': {'suffix': '_url'}}])
        req = self.site.path.get()
        with self.text_response('{"eggs_url": "http://www.example.org/eggs"}'):
            resp = await req
        perma = resp.eggs
        self.assertIsInstance(perma, PermalinkString)
        self.assertIs(util.rag(perma, 'origin_request')._real_object, req)
        self.assertEqual(perma, "http://www.example.org/eggs")
        req2 = perma.get()
        self.assertIsInstance(req2, Request)
        self.assertAttrEqual(req2, 'url', "http://www.example.org/eggs")
        self.assertIs(util.rag(req2, 'site')._real_object, self.site)

    async def test_permalink_object(self):
        self.read_restspec(permalink_object={'attr': 'permalink'})
        req = self.site.path.get()
        with self.text_response('{"permalink": "http://www.example.org/eggs"}'):
            resp = await req
        req2 = resp.get()
        self.assertIsInstance(req2, Request)
        self.assertAttrEqual(req2, 'url', "http://www.example.org/eggs")
        self.assertIs(util.rag(req2, 'site')._real_object, self.site)


class ParamsTests(RequestTests):
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


class ValueTests(RequestTests):
    async def test_values(self):
        resp = await self.request('{"a": 42, "ham": ["eggs", "spam"]}')
        self.assertEqual(resp['a'], 42)
        self.assertEqual(resp.a, 42)
        self.assertEqual(resp['ham'][0], "eggs")
        self.assertEqual(resp['ham'][1], "spam")

    async def test_await_twice(self):
        with self.text_response('{"a": 42, "ham": ["eggs", "spam"]}'):
            resp1 = await self.req
        self.assertEqual(resp1['a'], 42)
        self.assertEqual(resp1.a, 42)
        self.assertEqual(resp1['ham'][0], "eggs")
        self.assertEqual(resp1['ham'][1], "spam")
        resp2 = await self.req
        self.assertEqual(resp1['a'], 42)
        self.assertEqual(resp1.a, 42)
        self.assertEqual(resp1['ham'][0], "eggs")
        self.assertEqual(resp1['ham'][1], "spam")
        self.assertEqual(resp2['a'], 42)
        self.assertEqual(resp2.a, 42)
        self.assertEqual(resp2['ham'][0], "eggs")
        self.assertEqual(resp2['ham'][1], "spam")

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


class IterTests(RequestTests):
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

    async def test_paginated_list_after_link(self):
        self.read_restspec(paginated_object={
                "when": {"attr_exists": "list"},
                "content": {"attr": "list"},
                "next": {"attr": "after"}
            })
        req = self.site.path.get()
        lis = []
        with self.text_responses(
                '{"list": [1, 2, 3], "after": "http://www.example.org/eggs"}',
                '{"list": [4, 5, 6]}'):
            async for item in req:
                lis.append(item)
        self.assertEqual(lis, [1, 2, 3, 4, 5, 6])


class StatusTests(RequestTests):
    async def test_raise_http404(self):
        with self.text_response('{"docs": "someplace"}', status=404):
            with self.assertRaises(errors.http.NotFound) as r:
                await self.req
            self.assertEqual(r.exception.response.docs, 'someplace')
            self.assertEqual(r.exception.response['docs'], 'someplace')

    async def test_404_expected(self):
        with self.text_response('{"docs": "someplace"}', status=404):
            self.req.expected = errors.http.NotFound
            resp = await self.req
            self.assertEqual(resp['docs'], 'someplace')
            self.assertEqual(resp.docs, 'someplace')

    async def test_raise_unknown_status(self):
        with self.text_response('{"status": "all teapots unavailable"}', 518):
            with self.assertRaises(errors.http.ServerError) as r:
                await self.req
            self.assertEqual(r.exception.status_code, 518)
            self.assertEqual(r.exception.response.status, "all teapots unavailable")

    async def test_raise_unknown_status_class(self):
        with self.text_response('{"status": "your service will be assimilated"}', 600):
            with self.assertRaises(errors.http.Any) as r:
                await self.req
            self.assertEqual(r.exception.status_code, 600)
            self.assertEqual(r.exception.response.status, "your service will be assimilated")

    async def test_inst_http(self):
        with self.assertRaises(TypeError):
            errors.http()


class SiteTests(Tests):
    def test_close_session(self):
        factory = SessionFactory.from_address('http://www.example.org/')
        session = factory()
        ah_session = util.rag(session, 'session')
        self.assertFalse(ah_session.closed)
        with session:
            self.assertFalse(ah_session.closed)
        self.assertTrue(ah_session.closed)
