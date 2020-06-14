"""Test reading and writing of program data."""

import unittest

from core import *
from google.appengine.ext import db
from named import QualtricsLink
import unit_test_helper


class QualtricsTestCase(unit_test_helper.PopulatedInconsistentTestCase):

    def test_stuff(self):
        """Test that QualtricsLink.get_link catches inconsistent results
        proving that get_link() handles inconsistency and doesn't return
        deleted (already used and thus non-unique) links"""

        # Create two links and put them to the db
        a = QualtricsLink.create(key_name='test_a', link='test_a',
                                 session_ordinal=1)
        b = QualtricsLink.create(key_name='test_b', link='test_b',
                                 session_ordinal=1)
        a.put()
        b.put()

        # db.get by key forces consistency
        a, b = db.get([a.key(), b.key()])

        # delete link a to put db into inconsistent state.
        db.delete(a)

        # get_link pulls in alphabetical order by link, so
        # a is retrieved first, then b.
        b_link = QualtricsLink.get_link(1)

        self.assertEquals(b_link, 'test_b')
