# napper -- A REST Client for Python
# Copyright (C) 2016 by Yann Kaiser and contributors.
# See AUTHORS and COPYING for details.
from .util import AioTests
from .. import request, response, util


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


class StringAsyncReader:
    def __init__(self, source):
        self.source = source

    async def text(self):
        return self.source


def consume(ito):
    try:
        while True:
            next(ito)
    except StopIteration as e:
        return e.value


class JsonResponseTests(AioTests):
    def setUp(self):
        super().setUp()
        self.r = consume(
            response.convert_json(
                self.req, StringAsyncReader(json_object)))

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

    def test_permalink(self):
        for method in ['get', 'post', 'put', 'delete']:
            with self.subTest(method=method):
                req = getattr(self.r.snakes_url, method)()
                self.assertIsInstance(req, request.Request)
                self.assertEqual(util.m(req).url,
                                  'http://www.example.org/snakes')
                self.assertEqual(util.m(req).method, method.upper())

