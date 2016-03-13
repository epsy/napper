# napper -- A REST Client for Python
# Copyright (C) 2016 by Yann Kaiser and contributors.
# See AUTHORS and COPYING for details.
from .request import SiteFactory


github = SiteFactory('https://api.github.com')
