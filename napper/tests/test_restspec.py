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

    def test_multiple_actions(self):
        with self.assertRaises(ValueError):
            self.f({'attr': 'abc', 'value': 42})

    def test_implicit_value(self):
        self.assertEqual(None, self.f(None)({}))
        self.assertEqual(0, self.f(0)({}))
        self.assertEqual(42, self.f(42)({}))
        self.assertEqual('ham', self.f('ham')({}))
        self.assertEqual(['item1', 'item2'], self.f([['item1', 'item2']])({}))

    def test_value(self):
        self.assertEqual(None, self.f({'value': None})({}))
        self.assertEqual(0, self.f({'value': 0})({}))
        self.assertEqual('ham', self.f({'value': 'ham'})({}))
        self.assertEqual({'a': 0}, self.f({'value': {'a': 0}})({}))
        self.assertEqual('always', self.f('always')({}))
        self.assertEqual('never', self.f('never')({}))

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
        f = self.f([{'attr': 'ham'}, {'context': 'root'}, {'attr': 'spam'}])
        self.assertEqual('sausages', f({'ham': 'eggs', 'spam': 'sausages'}))
        f = self.f(['Hello {}!', {'format': [[{'context': 'root'}, {'attr': 'name'}]]}])
        self.assertEqual('Hello John!', f({'name': 'John'}))


class ConditionalTests(Tests):
    def c(self, obj):
        obj = json.loads(json.dumps(obj), object_hook=restspec.WarnOnUnusedKeys)
        return restspec.Conditional.from_restspec(obj)

    def test_missing(self):
        with self.assertRaises(ValueError):
            self.c({})

    def test_always_false(self):
        c = self.c("never")
        self.assertFalse(c({}))
        self.assertFalse(c("abc"))
        self.assertFalse(c({"spam": "ham"}))
        r = {"spam": "ham"}
        self.assertFalse(c("ham", {"parent": r, "key": "spam", "root": r}))

    def test_always_true(self):
        c = self.c("always")
        self.assertTrue(c({}))
        self.assertTrue(c("abc"))
        self.assertTrue(c({"spam": "ham"}))
        r = {"spam": "ham"}
        self.assertTrue(c("ham", {"parent": r, "key": "spam", "root": r}))

    def test_attr_exists(self):
        c = self.c({'attr_exists': 'attr'})
        self.assertTrue(c({'attr': 'ham'}))
        r = {'spam': 'ham'}
        self.assertFalse(c(r, context={"root": r}))
        r2 = {"attr": r}
        self.assertFalse(
            c(r, {"attribute": "attr", "parent": r2, "root": r2}))

    def test_eq_value(self):
        c = self.c({'is_eq': 42})
        self.assertTrue(c(42))
        self.assertFalse(c(43))
        c = self.c({'eq': [{"context": "value"}, 42]})
        self.assertTrue(c(42))
        self.assertFalse(c(43))

    def test_eq(self):
        c = self.c({'eq': [42, {"attr": "spam"}]})
        self.assertTrue(c({"spam": 42}))
        self.assertFalse(c({"spam": 43}))

    def test_attr_name_is(self):
        c = self.c({'eq': ["permalink", [{"context": "attribute"}]]})
        r = {"permalink": "abc", "spam": "def"}
        self.assertTrue(
            c(r["permalink"], {"attribute": "permalink", "parent": r}))
        self.assertFalse(
            c(r["spam"], {"attribute": "spam", "parent": r}))

    def test_not(self):
        c = self.c({'not': {'is_eq': "apples"}})
        self.assertFalse(c("apples"))
        self.assertTrue(c("oranges"))

    def test_any(self):
        c = self.c({'any': [{'is_eq': 'pear'}, {'is_eq': 'apple'}]})
        self.assertTrue(c("pear"))
        self.assertTrue(c("apple"))
        self.assertFalse(c("orange"))

    def test_any_recover(self):
        c = self.c({'any': [{'eq': ['ham', {'context': 'attribute'}]},
                            {'is_eq': 42}]})
        self.assertTrue(c(42))
        self.assertFalse(c(43))

    def test_all(self):
        c = self.c({'all': [
                        {'is_eq': 'spam'},
                        {'eq': ['ham', {'context': 'attribute'}]}
                    ]})
        self.assertTrue(c("spam", context={'attribute': 'ham'}))
        self.assertFalse(c("spam", context={'attribute': 'eggs'}))
        self.assertFalse(c("spam", context={}))
        self.assertFalse(c("orange", context={'attribute': 'ham'}))

    def test_not_conditional(self):
        with self.assertRaises(ValueError):
            self.c(42)
        with self.assertRaises(ValueError):
            self.c({"value": ['abc']})

    def test_raw_value(self):
        c = self.c(True)
        self.assertTrue(c({}))
        c = self.c(False)
        self.assertFalse(c({}))

    def test_implicit_and(self):
        c = self.c({'attr_exists': 'abc', 'eq': [{'attr': 'spam'}, 'ham']})
        self.assertTrue(c({'abc': 0, 'spam': 'ham'}))
        self.assertFalse(c({'abc': 0, 'spam': 'eggs'}))
        self.assertFalse(c({'abc': 0}))
        self.assertFalse(c({'spam': 'ham'}))

    def test_mixed(self):
        with self.assertRaises(ValueError):
            self.c({'attr_exists': 'abc', 'value': 'True'})
