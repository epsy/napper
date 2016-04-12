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

    def test_permalink_attr_suffix(self):
        spec = self.make_spec(permalink_attribute=[
            {"context": "attribute"}, {"matches": {"suffix": "_url"}}])
        self.assertTrue(
            spec.is_permalink_attr("https://...", {"attribute": "abcd_url"}))
        self.assertFalse(
            spec.is_permalink_attr("https://...", {"attribute": "abcd"}))

    def test_permalink_attr_prefix(self):
        spec = self.make_spec(permalink_attribute=[
            {"context": "attribute"}, {"matches": {"prefix": "link_"}}])
        self.assertTrue(
            spec.is_permalink_attr("https://...", {"attribute": "link_abcd"}))
        self.assertFalse(
            spec.is_permalink_attr("https://...", {"attribute": "abcd"}))

    def test_permalink_attr_prefix_suffix(self):
        spec = self.make_spec(permalink_attribute=[
            {"context": "attribute"}, {"matches": {"prefix": "link_",
                                                   "suffix": "_url"}}])
        self.assertTrue(spec.is_permalink_attr(
            "https://...", {"attribute": "link_abcd_url"}))
        self.assertFalse(spec.is_permalink_attr(
            "https://...", {"attribute": "link_abcd"}))
        self.assertFalse(spec.is_permalink_attr(
            "https://...", {"attribute": "abcd_url"}))
        self.assertFalse(spec.is_permalink_attr(
            "https://...", {"attribute": "abcd"}))

    def test_permalink_attr_pattern(self):
        spec = self.make_spec(permalink_attribute=[
            {"context": "attribute"},
            {"matches": {"pattern": "^link_[0-9]+_url$"}}])
        self.assertTrue(spec.is_permalink_attr(
            "https://...", {"attribute": "link_4_url"}))
        self.assertTrue(spec.is_permalink_attr(
            "https://...", {"attribute": "link_123456_url"}))
        self.assertFalse(spec.is_permalink_attr(
            "https://...", {"attribute": "link_abcd_url"}))
        self.assertFalse(spec.is_permalink_attr(
            "https://...", {"attribute": "1234567"}))


class FetcherTests(Tests):
    def f(self, obj):
        obj = json.loads(json.dumps(obj), object_hook=restspec.WarnOnUnusedKeys)
        return restspec.Fetcher.from_restspec(obj)

    def nv(self):
        return self.assertRaises(restspec.NoValue)

    def test_none(self):
        f = self.f(None)
        with self.nv():
            f({})
        with self.nv():
            f("abc")
        with self.nv():
            f({"spam": "ham"})
        r = {"spam": "ham"}
        with self.nv():
            f("ham", {"parent": r, "key": "spam", "root": r})

    def test_missing_action(self):
        with self.assertRaises(ValueError):
            self.f({})

    def test_multiple_actions(self):
        with self.assertRaises(ValueError):
            self.f({'attr': 'abc', 'value': 42})

    def test_implicit_value(self):
        self.assertEqual(None, self.f([None])({}))
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

    def test_ifelse(self):
        f = self.f({'if': {'is_eq': 23}, 'then': 'abc', 'else': 'def'})
        self.assertEqual(f(23), 'abc')
        self.assertEqual(f(24), 'def')


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

    def test_none(self):
        c = self.c(None)
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

    def test_match(self):
        c = self.c({'matches': {'prefix': 'link_', 'suffix': '_url'}})
        self.assertTrue(c('link_stuff_url'))
        self.assertFalse(c('link_stuff'))
        self.assertFalse(c('stuff_url'))
        self.assertFalse(c('link_url'))
        c = self.c({'matches': {'pattern': 'link_.*_url'}})
        self.assertTrue(c('link_stuff_url'))
        self.assertFalse(c('link_stuff'))
        self.assertFalse(c('stuff_url'))
        self.assertFalse(c('link_url'))

    def test_hint(self):
        c = self.c([{'context': 'attribute'}, {'matches': {'suffix': '_url'}}])
        self.assertEqual(c.attr_name_hint('abc'), 'abc_url')
        self.assertEqual(c.attr_name_hint('xyz'), 'xyz_url')

    def test_nohint(self):
        cs = [
            self.c(True),
            self.c([{'attr': 'abc'}, {'attr': 'def'}, {'is_eq': 'ghi'}]),
            self.c([{'attr': 'abc'}, {'is_eq': 123}]),
            self.c([{'context': [{'attr': 'abc'}, {'attr': 'def'}]},
                    {'is_eq': 'ghi'}]),
            self.c([{'context': {'attr': 'abc'}}, {'is_eq': 123}]),
            self.c([{'context': 'value'}, {'is_eq': 123}]),
            self.c([{'context': 'attribute'}, {'is_eq': 123}]),
        ]
        for c in cs:
            with self.assertRaises(restspec.NoValue):
                c.attr_name_hint("test")


class MatcherTests(Tests):
    def m(self, spec):
        return restspec.Matcher.from_restspec(self.to_config_dict(spec))

    def test_false(self):
        m = self.m(None)
        self.assertFalse(m('abcdef'))
        self.assertFalse(m(''))
        self.assertEqual(m.pattern, None)

    def test_true(self):
        m = self.m("any")
        self.assertTrue(m('abcdef'))
        self.assertTrue(m(''))
        self.assertEqual(m.pattern, re.compile(''))

    def test_pattern(self):
        m = self.m({'pattern': 'abc.*def'})
        self.assertTrue(m('abcdef'))
        self.assertTrue(m('abcxyzdef'))
        self.assertTrue(m('abc123def'))
        self.assertFalse(m('abc'))
        self.assertFalse(m('abcxyz'))
        self.assertFalse(m('xyzdef'))
        self.assertFalse(m('def'))
        self.assertFalse(m('xyz'))
        self.assertFalse(m(''))
        self.assertEqual(m.pattern, re.compile('abc.*def'))

    def test_prefix(self):
        m = self.m({'prefix': 'abc'})
        self.assertTrue(m('abc'))
        self.assertTrue(m('abcdef'))
        self.assertTrue(m('abc123'))
        self.assertFalse(m(''))
        self.assertFalse(m('def'))
        self.assertFalse(m('123'))
        self.assertFalse(m('defabc'))
        self.assertEqual(m.pattern, re.compile('^abc.*$'))

    def test_suffix(self):
        m = self.m({'suffix': 'xyz'})
        self.assertTrue(m('xyz'))
        self.assertTrue(m('abcdefxyz'))
        self.assertTrue(m('123xyz'))
        self.assertFalse(m('xyzabc'))
        self.assertFalse(m(''))
        self.assertFalse(m('abc'))
        self.assertFalse(m('123'))
        self.assertEqual(m.pattern, re.compile('^.*xyz$'))

    def test_prefix_suffix(self):
        m = self.m({'prefix': 'abc', 'suffix': 'xyz'})
        self.assertTrue(m('abcxyz'))
        self.assertTrue(m('abcdefxyz'))
        self.assertTrue(m('abc123xyz'))
        self.assertFalse(m('xyzabc'))
        self.assertFalse(m(''))
        self.assertFalse(m('abc'))
        self.assertFalse(m('123'))
        self.assertFalse(m('xyz'))
        self.assertFalse(m('abcxyz123'))
        self.assertFalse(m('123abcxyz'))
        self.assertEqual(m.pattern, re.compile('^abc.*xyz$'))

    def test_prefix_suffix_escape(self):
        m = self.m({'prefix': '$', 'suffix': '$'})
        self.assertTrue(m('$abcdef$'))
        self.assertTrue(m('$$'))
        self.assertTrue(m('$123$'))
        self.assertFalse(m('abc$'))
        self.assertFalse(m('$abc'))
        self.assertFalse(m('$'))
        self.assertEqual(m.pattern, re.compile(r'^\$.*\$$'))

    def test_nospec(self):
        with self.assertRaises(ValueError):
            self.m({})

    def test_pat_nohint(self):
        m = self.m({'pattern': 'abc.*'})
        with self.assertRaises(restspec.NoValue):
            m.hint('test')

    def test_pat_expl_hint(self):
        m = self.m({'pattern': 'abc.*', 'hint': 'abc{}def'})
        self.assertEqual(m.hint('test'), 'abctestdef')
        self.assertEqual(m.hint('abc'), 'abcabcdef')
        self.assertEqual(m.hint(''), 'abcdef')

    def test_prefix_hint(self):
        m = self.m({'prefix': 'abc'})
        self.assertEqual(m.hint('test'), 'abctest')
        self.assertEqual(m.hint(''), 'abc')
        self.assertEqual(m.hint('abc'), 'abcabc')

    def test_suffix_hint(self):
        m = self.m({'suffix': 'abc'})
        self.assertEqual(m.hint('test'), 'testabc')
        self.assertEqual(m.hint(''), 'abc')
        self.assertEqual(m.hint('abc'), 'abcabc')

    def test_prefix_suffix_hint(self):
        m = self.m({'prefix': 'abc', 'suffix': 'xyz'})
        self.assertEqual(m.hint('test'), 'abctestxyz')
        self.assertEqual(m.hint(''), 'abcxyz')
        self.assertEqual(m.hint('abc'), 'abcabcxyz')

    def test_prefix_expl_hint(self):
        m = self.m({'prefix': 'abc', 'hint': 'abc{}123'})
        self.assertEqual(m.hint("xyz"), "abcxyz123")

    def test_suffix_expl_hint(self):
        m = self.m({'suffix': 'abc', 'hint': '123{}abc'})
        self.assertEqual(m.hint("xyz"), "123xyzabc")

    def test_prefix_suffix_expl_hint(self):
        m = self.m({'prefix': 'abc', 'suffix': 'xyz', 'hint': 'abcxyz{}abcxyz'})
        self.assertEqual(m.hint("123"), "abcxyz123abcxyz")
