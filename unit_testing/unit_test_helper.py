"""Test case with a datastore that is eventually consistent and pre-populated
with a standard set of PERTS entities."""

from google.appengine.datastore import datastore_stub_util
from google.appengine.api import memcache
from google.appengine.ext import db
from google.appengine.ext import testbed
import logging
import unittest

from api import Api
from core import *
import util


class PertsTestCase(unittest.TestCase):
    """Contains important global settings for running unit tests.

    Errors related to logging, and appstats not being able to access memcache,
    would appear without these settings.

    Use Example:
    ```
    class MyTestCase(unit_test_help.PertsTestCase):
        def set_up(self):
            # Let PertsTestCase do its important work
            super(MyTestCase, self).setUp()

            # Add your own stubs here
            self.testbed.init_user_stub()

        # Add your tests here
        def test_my_stuff(self):
            pass
    ```
    """

    def setUp(self):
        """Sets self.testbed and activates it, among other global settings.

        This function (noticeably not named with PERTS-standard undrescore
        case) is automatically called when starting a test by the unittest
        module. We use it for basic configuration and delegate further set
        up to the more canonically named set_up() of inheriting classes.
        """
        if not util.is_localhost():
            # Logging test activity in production causes errors. This
            # suppresses all logs of level critical and lower, which means all
            # of them. See
            # https://docs.python.org/2/library/logging.html#logging.disable
            logging.disable(logging.CRITICAL)

        # Start a clean testing environment for one test.
        self.testbed = testbed.Testbed()
        self.testbed.activate()

        # user services
        self.testbed.init_user_stub()

        # Writing students involves tasks and memcache, so we need stubs for
        # those.
        self.testbed.init_memcache_stub()
        self.testbed.init_taskqueue_stub(root_path='.')
        self.taskqueue_stub = self.testbed.get_stub(
            testbed.TASKQUEUE_SERVICE_NAME)

        # Basic apis not related to specific users.
        self.public_api = Api(User(user_type='public'))
        self.internal_api = Api(User(user_type='god'))

        # Let inheriting classes to their own set up.
        if hasattr(self, 'set_up'):
            self.set_up()

    def tearDown(self):
        """Automatically called at end of test by the unittest module."""
        # Re-enable logging.
        logging.disable(logging.NOTSET)
        # Tear down the testing environment used by a single test so the next
        # test gets a fresh start.
        self.testbed.deactivate()

    def populate(self):
        """Creates a standard set of entities as PERTS expects them to exist.

        Includes all the correct relationships, and leaves everything in a
        consistent state. Mimics the javascript populate script in god.html.
        """
        self.researcher = User.create(user_type='researcher')
        self.researcher_api = Api(self.researcher)
        self.researcher.put()

        self.school = self.researcher_api.create('school', {'name': 'DGN'})
        self.program = self.researcher_api.create('program', {
            'name': 'Test Program',
            'abbreviation': 'TP1',
        })
        self.cohort = self.researcher_api.create('cohort', {
            'name': 'DGN 2014',
            'code': 'trout viper',
            'program': self.program.id,
            'school': self.school.id,
        })

        self.school_admin = self.internal_api.create(
            'user', {'user_type': 'school_admin'})
        self.school_admin_api = Api(self.school_admin)
        # have the researcher set the school_admin as an owner of their cohort
        self.researcher_api.associate(
            'set_owner', self.school_admin, self.cohort)

        self.teacher = self.public_api.create('user', {'user_type': 'teacher'})
        self.teacher.put()
        self.teacher_api = Api(self.teacher)
        self.researcher_api.associate('associate', self.teacher, self.cohort)

        # This is normally done api_handlers.AssociateHandler
        self.teacher_activities = self.teacher_api.init_activities(
            'teacher', self.teacher.id, self.program.id,
            cohort_id=self.cohort.id)

        # Different in Yosemite: school_admins create classrooms.
        self.classroom = self.school_admin_api.create('classroom', {
            'name': "English 101",
            'user': self.teacher.id,
            'program': self.program.id,
            'cohort': self.cohort.id,
        })

        self.student = self.public_api.create('user', {
            'user_type': 'student',
            'classroom': self.classroom.id,
        })
        self.student.put()
        self.student_api = Api(self.student)

        # This is normally done api_handlers.CreateHandler
        # Different in Yosemite: school_admins create classrooms (and thus
        # student activities).
        self.student_activities = self.school_admin_api.init_activities(
            'student', self.teacher.id, self.program.id,
            cohort_id=self.cohort.id, classroom_id=self.classroom.id)

        # Force everything into a consistent state, just in case we're using
        # an inconsistent policy.
        db.get([self.researcher.key(), self.school_admin.key(),
                self.teacher.key(), self.student.key(), self.school.key(),
                self.program.key(), self.cohort.key(), self.classroom.key(),
                self.teacher_activities[0].key(),
                self.teacher_activities[1].key(),
                self.student_activities[0].key(),
                self.student_activities[1].key()])


class InconsistentTestCase(PertsTestCase):
    """A badly-behaved datastore environment for testing PERTS entities."""

    def set_up(self):
        # Create a consistency policy that will simulate the High Replication
        # consistency model. This means it will be on it's 'worst' behavior.
        # Eventually consistent queries WILL return stale results.
        self.policy = datastore_stub_util.PseudoRandomHRConsistencyPolicy(
            probability=0)

        # Initialize the datastore stub with this policy.
        self.testbed.init_datastore_v3_stub(consistency_policy=self.policy)

        # Swap the above two lines with this to see the effects of a more
        # forgiving datastore, where eventually consistent queries MIGHT
        # return stale results.
        # self.testbed.init_datastore_v3_stub()


class PopulatedInconsistentTestCase(PertsTestCase):
    """A standard datastore environment for testing PERTS entities.

    Datastore is populated with one of each entity (except pds) with correct
    relationships. Even though datastore has a 0 chance of being consistent,
    populated entities have been forced into a consistent state for
    convenience.
    """

    def set_up(self):
        # Create a consistency policy that will simulate the High Replication
        # consistency model. This means it will be on it's 'worst' behavior.
        # Eventually consistent queries WILL return stale results.
        self.policy = datastore_stub_util.PseudoRandomHRConsistencyPolicy(
            probability=0)

        # Initialize the datastore stub with this policy.
        self.testbed.init_datastore_v3_stub(consistency_policy=self.policy)

        # Swap the above two lines with this to see the effects of a more
        # forgiving datastore, where eventually consistent queries MIGHT
        # return stale results.
        # self.testbed.init_datastore_v3_stub()

        self.populate()
