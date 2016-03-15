# napper -- A REST Client for Python
# Copyright (C) 2016 by Yann Kaiser and contributors.
# See AUTHORS and COPYING for details.
import asyncio
import functools
from collections import abc
import warnings

from .errors import UnknownParameters


def getattribute_common(func):
    @functools.wraps(func)
    def _wrapper(self, attr):
        if len(attr) > 4 and attr.startswith('__') and attr.endswith('__'):
            return object.__getattribute__(self, attr)
        return func(self, attr)
    return _wrapper


def getattribute_attrs(*attrs):
    attrs = set(attrs)
    def _deco(func):
        @functools.wraps(func)
        def _wrapper(self, attr):
            if attr in attrs or len(attr) > 4 and \
                    attr.startswith('__') and attr.endswith('__'):
                return object.__getattribute__(self, attr)
            return func(self, attr)
        return _wrapper
    return _deco


getattribute_dict = getattribute_attrs('keys', 'values', 'items')


def rag(self, name):
    """Normal attribute resolution"""
    return object.__getattribute__(self, name)


class DemagifiedObject(object):
    def __init__(self, obj):
        try:
            self.__dict__ = rag(obj, '__dict__')
        except AttributeError:
            pass
        self.__real_object = obj

    def __getattr__(self, name):
        return object.__getattribute__(self.__real_object, name)

    def __repr__(self):
        return "m({0!r})".format(self.__real_object)


m = DemagifiedObject


def metafunc(func):
    @functools.wraps(func)
    def _wrapped(self, *args, **kwargs):
        return func(m(self), *args, **kwargs)
    return _wrapped


METHODS = {
    'get', 'put', 'post', 'delete'
}


def _requestmethod(method):
    def func(self, **params):
        return self.request(method, params)
    func.__name__ = method
    return func


def requestmethods(cls):
    for method in METHODS:
        setattr(cls, method, _requestmethod(method))
    return cls


def run(coro):
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(coro)


class ThrowOnUnusedKeys(abc.Mapping):
    def __init__(self, value):
        self._value = value

    def __len__(self):
        return len(self._value)

    def __getitem__(self, key):
        self._unused_keys.remove(key)
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
