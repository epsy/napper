# napper -- A REST Client for Python
# Copyright (C) 2016 by Yann Kaiser and contributors.
# See AUTHORS and COPYING for details.

import io
import json
import re

from .. import restspec
from ..errors import UnknownParameters
from .util import Tests


class ConfigTests(Tests):
    def make_spec(self, **obj):
        obj.setdefault('base_address', 'http://www.example.org')
        return restspec.RestSpec.from_file(io.StringIO(json.dumps(obj)))

    def test_unknown_params(self):
        with self.assertWarns(UnknownParameters):
            self.make_spec(
                base_address="http://some.address", invalidoption=0)

    def test_address(self):
        spec = self.make_spec(base_address="http://an.address.com")
        self.assertEqual(spec.address, "http://an.address.com")

    def test_address_trailing(self):
        spec = self.make_spec(base_address="http://an.address.com/")
        self.assertEqual(spec.address, "http://an.address.com")

    def make_matcher(self, pattern):
        m = restspec.Matcher()
        m.pattern = re.compile(pattern)
        return m

    def test_permalink_attr_suffix(self):
        spec = self.make_spec(permalink_attribute={"suffix": "_url"})
        self.assertEqual(spec.is_permalink_attr, self.make_matcher("^.*_url$"))

    def test_permalink_attr_prefix(self):
        spec = self.make_spec(permalink_attribute={"prefix": "link_"})
        self.assertEqual(spec.is_permalink_attr, self.make_matcher("^link_.*$"))

    def test_permalink_attr_prefix_suffix(self):
        spec = self.make_spec(
            permalink_attribute={"prefix": "link_", "suffix": "_url"})
        self.assertEqual(spec.is_permalink_attr, self.make_matcher("^link_.*_url$"))

    def test_permalink_attr_pattern(self):
        spec = self.make_spec(
            permalink_attribute={"pattern": "^link_[0-9]+_url$"})
        self.assertEqual(spec.is_permalink_attr, self.make_matcher("^link_[0-9]+_url$"))


class FetcherTests(Tests):
    def f(self, obj):
        obj = json.loads(json.dumps(obj), object_hook=restspec.WarnOnUnusedKeys)
        return restspec.Fetcher.from_restspec(obj)

    def nv(self):
        return self.assertRaises(restspec.NoValue)

    def test_missing_action(self):
        with self.assertRaises(ValueError):
            self.f({})

    def test_value(self):
        self.assertEqual(None, self.f({'value': None})({}))
        self.assertEqual(0, self.f({'value': 0})({}))
        self.assertEqual('ham', self.f({'value': 'ham'})({}))
        self.assertEqual({'a': 0}, self.f({'value': {'a': 0}})({}))

    def test_attribute(self):
        f = self.f({'attr': 'spam'})
        self.assertEqual('ham', f({'spam': 'ham', 'eggs': '42'}))
        with self.nv():
            f({'eggs': '42'})
        with self.nv():
            f('str doesnt have attrs')

    def test_attribute_indirection(self):
        f = self.f({'attr': {'attr': 'eggs'}})
        self.assertEqual('spam', f({'eggs': 'ham', 'ham': 'spam'}))
        with self.nv():
            f({'ham': 'spam'})
        with self.nv():
            f({'eggs': 'ham'})

    def test_deep_attribute(self):
        f = self.f([{'attr': 'spam'}, {'attr': 'ham'}])
        self.assertEqual('eggs', f({'spam': {'ham': 'eggs'}}))
        with self.nv():
            f('str doesnt have attrs')

    def test_item(self):
        fixt = ['spam', 'ham', 'eggs']
        self.assertEqual('spam', self.f({'item': 0})(fixt))
        self.assertEqual('ham', self.f({'item': 1})(fixt))
        self.assertEqual('eggs', self.f({'item': 2})(fixt))
        self.assertEqual('spam', self.f({'item': -3})(fixt))
        self.assertEqual('ham', self.f({'item': -2})(fixt))
        self.assertEqual('eggs', self.f({'item': -1})(fixt))
        with self.nv():
            self.f({'item': 3})(fixt)
        with self.nv():
            self.f({'item': -4})(fixt)

    def test_format(self):
        f = self.f({'format': ['John']})
        self.assertEqual('Hello John!', f('Hello {}!'))
        self.assertEqual('Goodbye John!', f('Goodbye {}!'))

    def test_root(self):
        f = self.f([{'attr': 'ham'}, None, {'attr': 'spam'}])
        self.assertEqual('sausages', f({'ham': 'eggs', 'spam': 'sausages'}))
        f = self.f(['Hello {}!', {'format': [[None, {'attr': 'name'}]]}])
        self.assertEqual('Hello John!', f({'name': 'John'}))
