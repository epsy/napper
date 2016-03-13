# napper -- A REST Client for Python
# Copyright (C) 2016 by Yann Kaiser and contributors.
# See AUTHORS and COPYING for details.
from .. import SiteFactory
from .util import AioTests


class SiteTests(AioTests):
    def test_close_session(self):
        sf = SiteFactory('http://www.example.org/')
        se = sf()
        self.assertFalse(se.session.closed)
        with se:
            self.assertFalse(se.session.closed)
        self.assertTrue(se.session.closed)
