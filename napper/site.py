import sys
import aiohttp
import importlib.abc
import os.path

from .util import metafunc, getattribute_common, rag
from .restspec import RestSpec
from .request import Request, RequestBuilder
from .errors import CrossOriginRequestError


class NeverMatch(object):
    def match(self, haystack):
        return None


class SessionFactory:
    def __init__(self, spec):
        self.spec = spec

    @classmethod
    def from_address(cls, address):
        spec = RestSpec()
        spec.address = address.rstrip('/')
        return cls(spec)

    def __repr__(self):
        return "<SessionFactory [{}]>".format(self.address)

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
        return Session(self.spec, session)

    def permalink_hint(self, key, obj):
        return None

    def permalink_obj(self, key):
        return None


_unset = object()


class Session:
    @property
    def site(self):
        return self

    def __init__(self, spec, session, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.spec = spec
        self.session = session

    @metafunc
    def __repr__(self):
        return "<Site [{0.spec.address}]>".format(self)

    def __enter__(self):
        return self

    def __exit__(self, *args, **kwargs):
        rag(self, 'session').close()

    close = __exit__

    @metafunc
    def __getitem__(self, name):
        return RequestBuilder(self, (name,))

    __getattribute__ = getattribute_common(__getitem__)

    @metafunc
    def build_request(self, method, path, **kwargs):
        jpath = self.spec.join_path(path)
        return Request(self, method, jpath, **kwargs)

    @metafunc
    def _request(self, method, url, *args, **kwargs):
        if not self.spec.is_same_origin(url):
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
        return SessionFactory(None)

    def exec_module(self, session_factory):
        session_factory.spec = RestSpec.from_file(open(session_factory.__spec__.origin))
        return session_factory
