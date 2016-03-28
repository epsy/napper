# napper -- A REST Client for Python
# Copyright (C) 2016 by Yann Kaiser and contributors.
# See AUTHORS and COPYING for details.
from ..request import SessionFactory
from ..util import rag
from .util import Tests


class SiteTests(Tests):
    def test_close_session(self):
        factory = SessionFactory.from_address('http://www.example.org/')
        session = factory()
        ah_session = rag(session, 'session')
        self.assertFalse(ah_session.closed)
        with session:
            self.assertFalse(ah_session.closed)
        self.assertTrue(ah_session.closed)
