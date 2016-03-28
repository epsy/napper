# napper -- A REST Client for Python
# Copyright (C) 2016 by Yann Kaiser and contributors.
# See AUTHORS and COPYING for details.

import json
from collections import abc
import warnings
import re
from functools import partial

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

    @classmethod
    def from_restspec(cls, obj):
        with obj:
            ret = cls()
            for cond, params in obj.items():
                try:
                    f = getattr(ret, 'cond_' + cond)
                except AttributeError:
                    raise ValueError("Unknown condition type: " + cond)
                ret.checkers.append(partial(f, params))
            return ret

    def __call__(self, key, value, parent):
        return all(cond(key, value, parent) for cond in self.checkers)

    def cond_attr_exists(self, name, key, value, parent):
        try:
            value[name]
        except (KeyError, TypeError):
            return False
        else:
            return True


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


class Fetcher:
    def __init__(self):
        self.steps = []

    @classmethod
    def from_restspec(cls, obj):
        ret = cls()
        if not isinstance(obj, list):
            obj = [obj]
        for step in obj:
            if step is None:
                ret.steps.append(ret.step_root)
                continue
            elif not isinstance(step, abc.Mapping):
                ret.steps.append(partial(ret.step_value, step))
                continue
            with step:
                if 'attr' in step:
                    attr = step['attr']
                    ret.steps.append(
                        partial(ret.step_attr, Fetcher.from_restspec(attr)))
                elif 'item' in step:
                    i = step['item']
                    ret.steps.append(
                        partial(ret.step_item, Fetcher.from_restspec(i)))
                elif 'format' in step:
                    args = step['format']
                    if not isinstance(args, list):
                        args = []
                    ret.steps.append(
                        partial(ret.step_format,
                                [Fetcher.from_restspec(arg) for arg in args]))
                elif 'value' in step:
                    value = step['value']
                    try:
                        value = value._value
                    except AttributeError:
                        pass
                    ret.steps.append(partial(ret.step_value, value))
                else:
                    raise ValueError("Bad Fetcher description", step)
        return ret

    def __call__(self, value, root=None):
        if root is None: root = value
        for step in self.steps:
            value = step(value, root)
        return value

    def step_value(self, ret, value, root):
        return ret

    def step_root(self, value, root):
        return root

    def step_attr(self, get_attr_name, value, root):
        try:
            return value[get_attr_name(value, root)]
        except (KeyError, TypeError, IndexError):
            raise NoValue

    step_item = step_attr

    def step_format(self, args, value, root):
        return value.format(*(arg(value, root) for arg in args))


class RestSpec:
    def __init__(self):
        self.address = None
        self.is_permalink_attr = always_false
        self.is_paginator_object = always_false
        self.permalink_hint = no_value
        self.get_object_permalink = no_value
        self.paginator_next_url = no_value

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
            self.permalink_hint = Hint.from_restspec(obj.get('permalink_object'))
            self._read_paginator(obj.get('paginated_object'))

    def _read_paginator(self, obj):
        if obj is None:
            return
        with obj:
            self.is_paginator_object = Conditional.from_restspec(obj['when'])
            self.paginator_content = Fetcher.from_restspec(obj['content'])
            self.paginator_next_url = Fetcher.from_restspec(obj['next'])

    def join_path(self, path):
        return self.address + '/' + '/'.join(path)

    def is_same_origin(self, url):
        return url.startswith(self.address)
