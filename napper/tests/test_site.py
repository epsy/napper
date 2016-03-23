# napper -- A REST Client for Python
# Copyright (C) 2016 by Yann Kaiser and contributors.
# See AUTHORS and COPYING for details.
import io
import json
import re

from ..site import SiteFactory
from ..errors import UnknownParameters
from .util import Tests


class SiteTests(Tests):
    def test_close_session(self):
        sf = SiteFactory('http://www.example.org/')
        se = sf()
        self.assertFalse(se.session.closed)
        with se:
            self.assertFalse(se.session.closed)
        self.assertTrue(se.session.closed)


class ConfigTests(Tests):
    def sf_from_restspec(self, **obj):
        obj.setdefault('base_address', 'http://www.example.org')
        sf = SiteFactory('')
        sf._read_restspec(io.StringIO(json.dumps(obj)))
        return sf

    def test_unknown_params(self):
        with self.assertWarns(UnknownParameters):
            self.sf_from_restspec(
                base_address="http://some.addressa", invalidoption=0)

    def test_address(self):
        sf = self.sf_from_restspec(base_address="http://an.address.com")
        self.assertEqual(sf.address, "http://an.address.com")

        sf = self.sf_from_restspec(base_address="http://an.address.com/")
        self.assertEqual(sf.address, "http://an.address.com")

    def test_permalink_attr_suffix(self):
        sf = self.sf_from_restspec(permalink_attribute={"suffix": "_url"})
        self.assertEqual(sf.permalink_attr, re.compile("^.*_url$"))

    def test_permalink_attr_prefix(self):
        sf = self.sf_from_restspec(permalink_attribute={"prefix": "link_"})
        self.assertEqual(sf.permalink_attr, re.compile("^link_.*$"))

    def test_permalink_attr_prefix_suffix(self):
        sf = self.sf_from_restspec(
            permalink_attribute={"prefix": "link_", "suffix": "_url"})
        self.assertEqual(sf.permalink_attr, re.compile("^link_.*_url$"))

    def test_permalink_attr_pattern(self):
        sf = self.sf_from_restspec(
            permalink_attribute={"pattern": "^link_[0-9]+_url$"})
        self.assertEqual(sf.permalink_attr, re.compile("^link_[0-9]+_url$"))
