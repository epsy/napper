import sys
import aiohttp
import json
import importlib.abc
import os.path

from .util import metafunc, getattribute_common
from .request import Request, RequestBuilder
from .errors import CrossOriginRequestError


class SiteFactory:
    def __init__(self, address):
        self.address = address.rstrip('/')

    def _read_restspec(self, obj):
        self.address = obj['base_address']

    @classmethod
    def from_restspec_obj(cls, obj):
        ret = cls('')
        ret._read_restspec(obj)
        return ret

    @classmethod
    def from_restspec_file(cls, file_or_name):
        try:
            file_or_name.read
        except AttributeError:
            f = open(file_or_name)
        else:
            f = file_or_name
        return cls.from_restspec_obj(json.load(f))

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
        site_factory._read_restspec(
            json.load(open(site_factory.__spec__.origin)))
        return site_factory
