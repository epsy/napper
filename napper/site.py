import sys
import aiohttp
import json
import importlib.abc
import os.path
import re

from .util import metafunc, getattribute_common, ThrowOnUnusedKeys
from .request import Request, RequestBuilder
from .errors import CrossOriginRequestError


class NeverMatch(object):
    def match(self, haystack):
        return None


class SiteFactory:
    permalink_attr = NeverMatch()
    permalink_hint = lambda key, obj: None

    def __init__(self, address):
        self.address = address.rstrip('/')

    def _read_restspec(self, f):
        with json.load(f, object_hook=ThrowOnUnusedKeys) as cfg:
            self.address = cfg['base_address'].rstrip('/')
            self.permalink_attr, self.permalink_hint = self._parse_matcher(
                    cfg.get('permalink_attribute'))

    def _no_hint(self, key, obj):
        return None

    def _parse_matcher(self, value):
        if value is None:
            return NeverMatch(), self._no_hint
        if value == 'any':
            return re.compile(''), self._no_hint
        hint = value.get('hint')
        hint_func = lambda k, o: hint
        with value:
            try:
                pat = value['pattern']
            except KeyError:
                pass
            else:
                return (
                    re.compile(pat),
                    hint_func if hint else self._no_hint
                    )
            prefix = value.get('prefix')
            suffix = value.get('suffix')
            if prefix is None and suffix is None:
                raise ValueError('Need at least a prefix and/or suffix, '
                                 'or a pattern')
            prefix = prefix or ''
            suffix = suffix or ''
            hint = (prefix + '{}' + suffix) if not hint else hint
            return (
                re.compile('^{}.*{}$'.format(re.escape(prefix),
                                             re.escape(suffix))),
                hint_func)

    @classmethod
    def from_restspec_file(cls, file_or_name):
        try:
            file_or_name.read
        except AttributeError:
            f = open(file_or_name)
        else:
            f = file_or_name
        ret = cls('')
        ret._read_restspec(f)
        return ret

    def __repr__(self):
        return "<SiteFactory [{}]>".format(self.address)

    def __call__(self, session=None, proxy=None):
        """
        :param session: An `aiohttp.ClientSession` object
        :param proxy: If session is unset, an http proxy addess. See
            the documentation on `aiohttp.ProxyConnector`
        """
        if session is None:
            conn = None
            if proxy is not None:
                conn = aiohttp.ProxyConnector(proxy=proxy)
            session = aiohttp.ClientSession(connector=conn)
        return SiteSession(self, session)


class SiteSession:
    def __init__(self, factory, session):
        self.factory = factory
        self.session = session

    def __enter__(self):
        return Site(self.factory, self)

    def __exit__(self, typ, val, tb):
        self.close()

    def close(self):
        self.session.close()

    def request(self, *args, **kwargs):
        return self.session.request(*args, **kwargs)


_unset = object()


class Site:
    @property
    def site(self):
        return self

    def __init__(self, factory, session, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.factory = factory
        self.address = factory.address
        self.session = session

    @metafunc
    def __repr__(self):
        return "<Site [{0.address}]>".format(self)

    @metafunc
    def __getitem__(self, name):
        return RequestBuilder(self, (name,))

    __getattribute__ = getattribute_common(__getitem__)

    @metafunc
    def join_path(self, path):
        return self.address + '/' + '/'.join(path)

    @metafunc
    def is_same_origin(self, url):
        return url.startswith(self.address)

    @metafunc
    def build_request(self, method, path, **kwargs):
        jpath = self.join_path(path)
        return Request(self, method, jpath, **kwargs)

    @metafunc
    def _request(self, method, url, *args, **kwargs):
        if not self.is_same_origin(url):
            raise CrossOriginRequestError(self, method, url, (), {})
        return self.session.request(method, url, *args, **kwargs)

    @metafunc
    def is_permalink_attr(self, key, item):
        return self.factory.permalink_attr.match(key) is not None


class RestSpecFinder(importlib.abc.MetaPathFinder):
    def install(self):
        sys.meta_path.append(self)

    def find_spec(self, fullname, path, target=None):
        _, _, mod = fullname.rpartition('.')
        modfile = mod + '.restspec.json'
        for p in path:
            filename = os.path.join(p, modfile)
            if os.path.exists(filename):
                return importlib.machinery.ModuleSpec(
                    fullname, RestSpecLoader(), origin=filename)
        return None


class RestSpecLoader(importlib.abc.Loader):
    def create_module(self, spec):
        return SiteFactory('')

    def exec_module(self, site_factory):
        site_factory._read_restspec(open(site_factory.__spec__.origin))
        return site_factory
