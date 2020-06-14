"""Testing memcache functions."""

from google.appengine.api import memcache
from google.appengine.ext import db
import datetime
import time
import unittest

from api import Api
from core import *
from cron import Cron
from named import *
import unit_test_helper


class MemcacheTestCase(unit_test_helper.PopulatedInconsistentTestCase):
    def test_cache_roster(self):
        """Querying /api/get_roster should cache the result.

        Rosters are cached because querying them from the datastore is slow.
        From the browser on localhost, querying ~100 users from a cohort or
        classroom takes about 4 seconds. If the result of that query is stored
        in memcache, the same http call takes about 500 ms.

        However, it's critical that memcache not serve stale data. So these
        tests also check that whenever a user is modified, the related
        classroom and cohort rosters are cleared from memcache.
        """
        result, from_memcache = self.school_admin_api.get_roster(self.cohort.id)
        self.assertEquals(result, memcache.get(self.cohort.id + '_roster'))

        result, from_memcache = self.school_admin_api.get_roster(self.classroom.id)
        self.assertEquals(result, memcache.get(self.classroom.id + '_roster'))

    def test_create_user_clears_memcache(self):
        self.test_cache_roster()
        student = self.public_api.create('user', {
            'user_type': 'student',
            'classroom': self.classroom.id,
        })
        self.check_updated_rosters_cleared_from_memcache()

    def test_delete_user_clears_memcache(self):
        self.test_cache_roster()
        self.school_admin_api.delete(self.student.id)
        self.check_updated_rosters_cleared_from_memcache()

    def test_update_user_clears_memcache(self):
        self.test_cache_roster()
        self.school_admin_api.update(
            'user', self.student.id, {'first_name': 'a'})
        self.check_updated_rosters_cleared_from_memcache()

    def test_put_user_clears_memcache(self):
        self.test_cache_roster()
        self.student.last_name = 'b'
        self.student.put()
        self.check_updated_rosters_cleared_from_memcache()

    def test_dbput_user_clears_memcache(self):
        self.test_cache_roster()
        self.student.login_email = 'c'
        db.put(self.student)
        self.check_updated_rosters_cleared_from_memcache()

    def test_unassociated_user_clears_memcache(self):
        self.test_cache_roster()
        self.internal_api.unassociate(
            'unassociate', self.student, self.classroom)
        self.check_updated_rosters_cleared_from_memcache()

    def test_aggregate_user_clears_memcache(self):
        pd_params = {
            'variable': 's1__progress',
            'program': self.program.id,
            'activity': self.student_activities[0].id,
            'activity_ordinal': 1,
            'value': 100,
            'scope': self.student.id,
        }
        pd = Api(self.student).create('pd', pd_params)
        db.get(pd.key())  # simulate a delay before the aggregator runs
        Cron(self.internal_api).aggregate()
        # Make sure aggregation happened as expected.
        self.student = db.get(self.student.key())
        self.assertEquals(self.student.aggregation_data,
                          {1: {'progress': 100}, 2: {'progress': None}})
        self.check_updated_rosters_cleared_from_memcache()

    def check_updated_rosters_cleared_from_memcache(self):
        self.assertIsNone(memcache.get(self.cohort.id + '_roster'))
        self.assertIsNone(memcache.get(self.classroom.id + '_roster'))
