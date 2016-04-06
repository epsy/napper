# napper -- A REST Client for Python
# Copyright (C) 2016 by Yann Kaiser and contributors.
# See AUTHORS and COPYING for details.
import json

from .util import Tests
from .. import request, response, util, restspec


class JsonResponseTests(Tests):
    json_object = """
    {
        "num": 3,
        "object": {
            "prop1": "hello",
            "eggs_url": "https://www.example.org/object/eggs"
        },
        "ham": "spam",
        "snakes_url": "http://www.example.org/snakes"
    }
    """

    def setUp(self):
        super().setUp()
        self.r = self.make_response()

    def make_response(self):
        return response.upgrade_object(
            json.loads(self.json_object), util.m(self.req))

    def test_values_attr(self):
        self.assertEqual(self.r.num, 3)
        self.assertEqual(self.r.ham, 'spam')
        self.assertEqual(self.r.snakes_url, 'http://www.example.org/snakes')
        self.assertEqual(self.r.object.prop1, 'hello')
        self.assertEqual(self.r.object.eggs_url,
                         'https://www.example.org/object/eggs')
        with self.assertRaises(AttributeError):
            self.r.doesntexist
        with self.assertRaises(AttributeError):
            self.r.object.doesntexist
        with self.assertRaises(AttributeError):
            self.r.snakes_url.doesntexist

    def test_values_item(self):
        self.assertEqual(self.r['num'], 3)
        self.assertEqual(self.r['ham'], 'spam')
        self.assertEqual(self.r['snakes_url'], 'http://www.example.org/snakes')
        self.assertEqual(self.r['object']['prop1'], 'hello')
        self.assertEqual(self.r['object']['eggs_url'],
                         'https://www.example.org/object/eggs')
        with self.assertRaises(KeyError):
            self.r['doesntexist']
        with self.assertRaises(KeyError):
            self.r['object']['doesntexist']
        with self.assertRaises(TypeError):
            self.r['snakes_url']['doesntexist']

    def test_values_mixed(self):
        self.assertEqual(self.r.object['prop1'], 'hello')
        self.assertEqual(self.r['object'].prop1, 'hello')
        self.assertEqual(self.r.object['eggs_url'],
                         'https://www.example.org/object/eggs')
        self.assertEqual(self.r['object'].eggs_url,
                         'https://www.example.org/object/eggs')

    def test_permalink_denied(self):
        with self.assertRaises(AttributeError):
            self.r.snakes_url.get()

    def attr_matcher(self, **match):
        return restspec.Conditional.from_restspec(self.to_config_dict(
            [{'context': 'attribute'}, {'matches': match}]))

    async def test_permalink(self):
        self.sfactory.spec.is_permalink_attr = \
            self.attr_matcher(pattern='^.*_url$')
        resp = self.make_response()
        for method in ['get', 'post', 'put', 'delete']:
            with self.subTest(method=method):
                req = getattr(resp.snakes_url, method)()
                self.assertIsInstance(req, request.Request)
                self.assertEqual(util.m(req).url,
                                  'http://www.example.org/snakes')
                self.assertEqual(util.m(req).method, method.upper())

    async def test_permalink_hint(self):
        self.sfactory.spec.is_permalink_attr = \
            self.attr_matcher(suffix='_url')
        resp = self.make_response()
        req = resp.snakes.get()
        self.assertIsInstance(req, request.Request)
        self.assertEqual(util.m(req).url, 'http://www.example.org/snakes')
        self.assertEqual(util.m(req).method, 'GET')
