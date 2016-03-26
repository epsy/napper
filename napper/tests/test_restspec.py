import io
import json
import re

from .. import restspec
from ..errors import UnknownParameters
from .util import Tests


class ConfigTests(Tests):
    def make_spec(self, **obj):
        obj.setdefault('base_address', 'http://www.example.org')
        return restspec.RestSpec.from_file(io.StringIO(json.dumps(obj)))

    def test_unknown_params(self):
        with self.assertWarns(UnknownParameters):
            self.make_spec(
                base_address="http://some.address", invalidoption=0)

    def test_address(self):
        spec = self.make_spec(base_address="http://an.address.com")
        self.assertEqual(spec.address, "http://an.address.com")

    def test_address_trailing(self):
        spec = self.make_spec(base_address="http://an.address.com/")
        self.assertEqual(spec.address, "http://an.address.com")

    def make_matcher(self, pattern):
        m = restspec.Matcher()
        m.pattern = re.compile(pattern)
        return m

    def test_permalink_attr_suffix(self):
        spec = self.make_spec(permalink_attribute={"suffix": "_url"})
        self.assertEqual(spec.is_permalink_attr, self.make_matcher("^.*_url$"))

    def test_permalink_attr_prefix(self):
        spec = self.make_spec(permalink_attribute={"prefix": "link_"})
        self.assertEqual(spec.is_permalink_attr, self.make_matcher("^link_.*$"))

    def test_permalink_attr_prefix_suffix(self):
        spec = self.make_spec(
            permalink_attribute={"prefix": "link_", "suffix": "_url"})
        self.assertEqual(spec.is_permalink_attr, self.make_matcher("^link_.*_url$"))

    def test_permalink_attr_pattern(self):
        spec = self.make_spec(
            permalink_attribute={"pattern": "^link_[0-9]+_url$"})
        self.assertEqual(spec.is_permalink_attr, self.make_matcher("^link_[0-9]+_url$"))
