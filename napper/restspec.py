# napper -- A REST Client for Python
# Copyright (C) 2016 by Yann Kaiser and contributors.
# See AUTHORS and COPYING for details.

import json
from collections import abc
import warnings
import re
from functools import partial, wraps
import enum

from .errors import UnknownParameters


class WarnOnUnusedKeys(abc.Mapping):
    def __init__(self, value):
        self._value = value

    def __repr__(self):
        return repr(self._value)

    def __len__(self):
        return len(self._value)

    def __getitem__(self, key):
        try:
            self._unused_keys.discard(key)
        except AttributeError:
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
                ret.hint_fmt = hint
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

    def __call__(self, value):
        if self.pattern is None:
            return False
        return bool(self.pattern.match(value))

    def hint(self, key):
        if self.hint_fmt is None:
            raise NoValue
        return self.hint_fmt.format(key)

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


@enum.unique
class Conversion(enum.Enum):
    RAW = 0
    WHOLE = 1
    EACH = 2
    WHOLE_CONDITIONAL = 3
    EACH_CONDITIONAL = 4
    MATCHER = 5

    @classmethod
    def convert(cls, conv, arg):
        if conv == cls.RAW:
            try:
                return arg._value
            except AttributeError:
                return arg
        elif conv == cls.WHOLE:
            return Fetcher.from_restspec(arg)
        elif conv == cls.EACH:
            return [Fetcher.from_restspec(a) for a in arg]
        elif conv == cls.WHOLE_CONDITIONAL:
            return Conditional.from_restspec(arg)
        elif conv == cls.EACH_CONDITIONAL:
            return [Conditional.from_restspec(a) for a in arg]
        elif conv == cls.MATCHER:
            return Matcher.from_restspec(arg)
        raise AssertionError("Bad conversion type", conv)

    @classmethod
    def convert_for_func(cls, func, arg):
        return cls.convert(getattr(func, 'convert_arg', cls.WHOLE), arg)


def attr_setter(attr, base_type):
    def func(value):
        assert isinstance(value, base_type)
        def deco(func):
            setattr(func, attr, value)
            return func
        return deco
    return func


convert_arg = attr_setter('convert_arg', Conversion)
takes_keywords = attr_setter('takes_keywords', dict)


def boolean_result(func):
    @wraps(func)
    def _ret(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except NoValue:
            return False
    _ret.boolean_result = True
    return _ret


class Fetcher:
    def __init__(self):
        self.steps = []

    @classmethod
    def from_restspec(cls, obj):
        if obj is None:
            return no_value
        ret = cls()
        if not isinstance(obj, list):
            obj = [obj]
        for step in obj:
            if not isinstance(step, abc.Mapping):
                ret.steps.append(partial(ret.step_value, step))
                continue
            with step:
                conds = []
                has_noncond = False
                errors = []
                for key in step:
                    try:
                        func = getattr(ret, 'step_' + key)
                    except AttributeError:
                        errors.append(key)
                    else:
                        kwds = getattr(func, 'takes_keywords', {})
                        kwargs = {}
                        for kname, conv in kwds.items():
                            kwargs[kname] = Conversion.convert(
                                conv, step[kname.rstrip('_')])
                        par = partial(
                            func,
                            Conversion.convert_for_func(func, step[key]),
                            **kwargs)
                        if getattr(func, 'boolean_result', False):
                            conds.append(par)
                        else:
                            if has_noncond:
                                raise ValueError(
                                    "Fetcher step description has multiple "
                                    "fetchers")
                            has_noncond = True
                            ret.steps.append(par)
                        if has_noncond and conds:
                            raise ValueError(
                                "Fetcher step description mixes conditionals "
                                "and fetchers")
                if len(conds) == 1:
                    ret.steps.append(conds[0])
                elif conds:
                    ret.steps.append(partial(ret.step_all, conds))
                elif not has_noncond:
                    raise ValueError("Fetcher step description is empty")
        return ret

    def __repr__(self):
        return '<{} {}>'.format(self.__class__.__name__, self.steps)

    def __call__(self, value, context=None):
        if context is None: context = {'root': value, 'value': value}
        context = context.copy()
        for step in self.steps:
            value = step(value, context)
            context['value'] = value
        return value

    @boolean_result
    def always(self, ret, value, context):
        return ret

    @convert_arg(Conversion.RAW)
    def step_value(self, ret, value, context):
        return ret

    def step_attr(self, get_attr_name, value, context):
        name = get_attr_name(value, context)
        try:
            return value[name]
        except (KeyError, TypeError, IndexError):
            raise NoValue

    step_item = step_attr

    @convert_arg(Conversion.EACH)
    def step_format(self, args, value, context):
        return value.format(*(arg(value, context) for arg in args))

    def step_context(self, context_key, value, context):
        key = context_key(value, context)
        try:
            return context[key]
        except KeyError:
            raise NoValue

    @boolean_result
    def step_attr_exists(self, name, value, context):
        try:
            value[name(value, context)]
        except (KeyError, TypeError):
            return False
        else:
            return True

    @boolean_result
    @convert_arg(Conversion.EACH)
    def step_eq(self, args, value, context):
        assert len(args) >= 2
        values = (arg(value, context) for arg in args)
        first = next(values)
        for val in values:
            if val != first:
                return False
        return True

    @boolean_result
    def step_is_eq(self, arg, value, context):
        return arg(value, context) == value

    @boolean_result
    @convert_arg(Conversion.MATCHER)
    def step_matches(self, arg, value, context):
        return arg(value)

    @boolean_result
    @convert_arg(Conversion.WHOLE_CONDITIONAL)
    def step_not(self, arg, value, context):
        return not arg(value, context)

    @boolean_result
    @convert_arg(Conversion.EACH_CONDITIONAL)
    def step_all(self, args, value, context):
        return all(arg(value, context) for arg in args)

    @boolean_result
    @convert_arg(Conversion.EACH_CONDITIONAL)
    def step_any(self, args, value, context):
        return any(arg(value, context) for arg in args)

    @convert_arg(Conversion.WHOLE_CONDITIONAL)
    @takes_keywords({'then_': Conversion.WHOLE, 'else_': Conversion.WHOLE})
    def step_if(self, cond, value, context, *, then_, else_):
        if cond(value, context):
            return then_(value, context)
        else:
            return else_(value, context)


class Conditional(Fetcher):
    @classmethod
    def from_restspec(cls, obj):
        if obj in ["always", "never", None]:
            ret = cls()
            ret.steps.append(partial(ret.always, obj == "always"))
            return ret
        ret = super().from_restspec(obj)
        last_step = ret.steps[-1]
        last_func = last_step.func
        if not getattr(last_func, 'boolean_result', False):
            if last_func != ret.step_value or last_step.args[0] not in [True, False]:
                raise ValueError("Conditional required, got: ", last_func)
        return ret

    def attr_name_hint(self, name):
        if len(self.steps) == 2:
            s0 = self.steps[0]
            s1 = self.steps[1]
            if s0.func == self.step_context:
                f1 = s0.args[0]
                if len(f1.steps) == 1:
                    v1 = f1.steps[0]
                    if v1.func == f1.step_value and v1.args == ('attribute',):
                        if s1.func == self.step_matches:
                            return s1.args[0].hint(name)
        raise NoValue


always_false = Conditional.from_restspec("never")


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
                Conditional.from_restspec(obj.get('permalink_attribute'))
            self.get_object_permalink = \
                Fetcher.from_restspec(obj.get('permalink_object'))
            #self.permalink_hint = Hint.from_restspec(obj.get('permalink_object'))
            self._read_paginator(obj.get('paginated_object'))

    def _read_paginator(self, obj):
        if obj is None:
            return
        with obj:
            self.is_paginator_object = Fetcher.from_restspec(obj['when'])
            self.paginator_content = Fetcher.from_restspec(obj['content'])
            self.paginator_next_url = Fetcher.from_restspec(obj['next'])

    def join_path(self, path):
        return self.address + '/' + '/'.join(path)

    def is_same_origin(self, url):
        return url.startswith(self.address)
