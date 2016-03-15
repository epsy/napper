# napper -- A REST Client for Python
# Copyright (C) 2016 by Yann Kaiser and contributors.
# See AUTHORS and COPYING for details.
import io

from ..site import SiteFactory
from .util import AioTests


class SiteTests(AioTests):
    def sf_from_restspec(self, text):
        sf = SiteFactory('')
        sf._read_restspec(io.StringIO(text))
        return sf

    def test_close_session(self):
        sf = SiteFactory('http://www.example.org/')
        se = sf()
        self.assertFalse(se.session.closed)
        with se:
            self.assertFalse(se.session.closed)
        self.assertTrue(se.session.closed)

    def test_unknown_params(self):
        with self.assertRaises(ValueError):
            self.sf_from_restspec("""
                {"base_address": "http://some.addressa", "invalidoption": 0}
                """)

    def test_address(self):
        sf = self.sf_from_restspec("""
            {"base_address": "http://an.address.com"}
        """)
        self.assertEqual(sf.address, "http://an.address.com")
