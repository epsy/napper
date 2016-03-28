# napper -- A REST Client for Python
# Copyright (C) 2016 by Yann Kaiser and contributors.
# See AUTHORS and COPYING for details.

import sys
import importlib.abc
import os.path

from .request import SessionFactory
from .restspec import RestSpec


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
