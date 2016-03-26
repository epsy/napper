# napper -- A REST Client for Python
# Copyright (C) 2016 by Yann Kaiser and contributors.
# See AUTHORS and COPYING for details.
from .util import run
from .site import SessionFactory, RestSpecFinder
from .errors import CrossOriginRequestError


__all__ = [
    'SessionFactory',
    'run',
    'CrossOriginRequestError',
    ]


RestSpecFinder().install()
del RestSpecFinder
