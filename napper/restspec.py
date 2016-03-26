# napper -- A REST Client for Python
# Copyright (C) 2016 by Yann Kaiser and contributors.
# See AUTHORS and COPYING for details.

import json
from collections import abc
import warnings
import re

from .errors import UnknownParameters


class WarnOnUnusedKeys(abc.Mapping):
    def __init__(self, value):
        self._value = value

    def __len__(self):
        return len(self._value)

    def __getitem__(self, key):
        try:
            self._unused_keys.remove(key)
        except KeyError:
            pass
        return self._value[key]

    def __iter__(self):
        return iter(self._value)

    def __enter__(self):
        try:
            self._unused_keys
        except AttributeError:
            pass
        else:
            raise TypeError(
                "{} not non-reentrant"
                .format(self.__class__.__name__))
        self._unused_keys = set(self._value)
        return self

    def __exit__(self, typ, val, tb):
        if typ is not None:
            return
        if self._unused_keys:
            warnings.warn("Unknown parameters: " + ', '.join(self._unused_keys),
                          UnknownParameters)


class NoValue(Exception):
    pass


def no_value(*args, **kwargs):
    raise NoValue


def always_false(*args, **kwargs):
    return False
always_false.hint = no_value

class Conditional:
    def __init__(self):
        self.checkers = []


class Matcher:
    def __init__(self):
        self.pattern = None
        self.hint_fmt = None

    @classmethod
    def from_restspec(cls, obj):
        ret = cls()
        if obj is None:
            return ret
        if obj == "any":
            ret.pattern = re.compile('')
            return ret
        with obj:
            hint = obj.get("hint")
            if 'pattern' in obj:
                pat = obj['pattern']
                ret.pattern = re.compile(pat)
            else:
                if 'prefix' not in obj and 'suffix' not in obj:
                    raise ValueError('Need at least a prefix and/or suffix, '
                                     'or a pattern')
                prefix = obj.get('prefix', "")
                suffix = obj.get('suffix', "")
                hint = (prefix + '{}' + suffix) if hint is None else hint
                ret.hint_fmt = hint
                ret.pattern = re.compile(
                    '^{}.*{}$'.format(re.escape(prefix), re.escape(suffix)))
        return ret

    def __call__(self, key, value, parent):
        if self.pattern is None:
            return False
        return bool(self.pattern.match(key))

    def hint(self, key, parent):
        if self.hint_fmt is None:
            raise NoValue
        return self.hint_fmt.format(key, parent)

    def __repr__(self):
        return '<Matcher [{}]>'.format(self.pattern.pattern)

    def __eq__(self, other):
        return isinstance(other, Matcher) and self.pattern == other.pattern


class Hint:
    def __init__(self):
        self.fmt = None

    @classmethod
    def from_restspec(cls, fmt):
        ret = cls()
        ret.fmt = fmt
        return ret

    def __call__(self, obj):
        if self.fmt is None:
            raise NoValue
        return self.fmt.format(obj)

    def __repr__(self):
        return '<Hint []>'.format(self.fmt)


class RestSpec:
    def __init__(self):
        self.address = None
        self.is_permalink_attr = always_false
        self.is_paginator = always_false
        self.permalink_hint = no_value
        self.get_object_permalink = no_value

    @classmethod
    def from_file(cls, f):
        ret = cls()
        ret._read_spec_file(f)
        return ret

    def _read_spec_file(self, f):
        self._read_spec(json.load(f, object_hook=WarnOnUnusedKeys))

    def _read_spec(self, obj):
        with obj:
            self.address = obj.get('base_address').rstrip('/')
            self.is_permalink_attr = \
                Matcher.from_restspec(obj.get('permalink_attribute'))
            self.permalink_hint = Hint.from_restspec( obj.get('permalink_object'))

    def parse_conditional(self, obj):
        if obj is None:
            return always_false, no_value
        #hintability = False
        return always_false, no_value

    def join_path(self, path):
        return self.address + '/' + '/'.join(path)

    def is_same_origin(self, url):
        return url.startswith(self.address)
