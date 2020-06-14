"""Test reading and writing of program data."""

import unittest

from api import Api
from core import *
from cron import Cron
import unit_test_helper


class PdTestCase(unit_test_helper.PopulatedInconsistentTestCase):

    ### testing functions ###

    # See: http://docs.python.org/2/library/unittest.html#assert-methods

    def test_get_user_by_key(self):
        """An example of a strongly consistent query."""
        fetched_student = User.get_by_id(self.student.id)
        self.assertEqual(self.student, fetched_student)

    @unittest.expectedFailure
    def test_get_user_by_query(self):
        """An example of an eventually consistent query."""
        # A newly-created student won't be returned by a property-based query.
        new_student = User.create(user_type='student')
        new_student.put()
        fetched_student = User.all().filter('id =', new_student.id).get()
        self.assertEqual(new_student, fetched_student)

    def test_pd_variables_overwrite(self):
        """A second pd with the same variable should delete the first."""

        pd1 = self.student_api.create('pd', {
            'variable': 'condition',
            'value': 'first value',
            'program': self.program.id,
            'scope': self.student.id,
        })

        # In the process of creating this pd, the first should be deleted.
        pd2 = self.student_api.create('pd', {
            'variable': 'condition',
            'value': 'second value',
            'program': self.program.id,
            'scope': self.student.id,
        })
        
        # Re-fetch the original so we can see if it was correctly deleted.
        pd1 = Pd.get_by_id(pd1.id)
        self.assertTrue(pd1.deleted, "Original pd not deleted.")

    def test_pd_duplicates_overwrite(self):
        """Even if there are duplicate pds, writing new ones should succeed."""
        # Create w/o the api to intentionally create duplicates
        pd_id1 = 'Pd_1.' + self.student.id
        pd_id2 = 'Pd_2.' + self.student.id
        pd1 = Pd(key_name=pd_id1, id=pd_id1, parent=self.student,
                 scope=self.student.id, program=self.program.id,
                 variable='condition', value='duplicate test', public=True)
        pd2 = Pd(key_name=pd_id2, id=pd_id2, parent=self.student,
                 scope=self.student.id, program=self.program.id,
                 variable='condition', value='duplicate test', public=True)
        db.put([pd1, pd2])

        # Prove that there are duplicates.
        duplicates = self.student_api.get('pd', {}, ancestor=self.student)
        self.assertEquals(len(duplicates), 2)

        # Write a pd the normal way.
        pd3 = self.student_api.create('pd', {
            'variable': 'condition',
            'value': 'non-duplicate',
            'program': self.program.id,
            'scope': self.student.id,
        })

        # Only the new one should be present.
        non_duplicate = self.student_api.get('pd', {}, ancestor=self.student)
        self.assertEquals(len(non_duplicate), 1)
        self.assertEquals(non_duplicate[0].value, 'non-duplicate')

    def test_excessive_duplication(self):
        """Writing over 100 duplicates raises an exception."""
        # Create w/o the api to intentionally create duplicates
        duplicates = []
        for x in range(100):
            pd_id = 'Pd_{}.{}'.format(x, self.student.id)
            pd = Pd(key_name=pd_id, id=pd_id, parent=self.student,
                    scope=self.student.id, program=self.program.id,
                    variable='condition', value='duplicate test', public=True)
            duplicates.append(pd)
        db.put(duplicates)

        # Prove that there are duplicates.
        duplicates = self.student_api.get('pd', {}, ancestor=self.student)
        self.assertEquals(len(duplicates), 100)

        # Attempt to delete the excessive duplicates, expecting an exception.
        with self.assertRaises(Exception):
            pd_id = 'Pd_101.{}'.format(self.student.id)
            pd = Pd(key_name=pd_id, id=pd_id, parent=self.student,
                    scope=self.student.id, program=self.program.id,
                    variable='condition', value='non-duplicate', public=True)
            Pd.delete_previous_versions(pd, self.student)

    def test_batch_put_pd(self):
        params = {
            'pd_batch': [{'variable': 's2__toi_1', 'value': 1},
                         {'variable': 's2__toi_2', 'value': 1},
                         {'variable': 's2__toi_3', 'value': 1},
                         {'variable': 's2__toi_4', 'value': 1},
                         {'variable': 's2__toi_5', 'value': 1},
                         {'variable': 's2__toi_6', 'value': 1},
                         {'variable': 's2__toi_7', 'value': 1},
                         {'variable': 's2__toi_8', 'value': 1},
                         {'variable': 's2__toi_9', 'value': 1},
                         {'variable': 's2__toi_10', 'value': 1}],
            'activity': self.student_activities[0].id,
            'activity_ordinal': 1,
            'program': self.program.id,
            'scope': self.student.id,
            'is_test': False,
        }
        self.student_api.batch_put_pd(params)

        # We should get all the data back, using a strongly consistent
        # ancestor query.
        results = Pd.all().ancestor(self.student).fetch(10)
        self.assertEqual(len(results), 10)
        for pd in results:
            self.assertTrue(isinstance(pd, Pd))

    def test_get_by_ancestor(self):
        """Setting ancestor in api.get() should be strongly consistent."""
        self.student_api.create('pd', {
            'variable': 'consent',
            'value': 'true',
            'activity': self.student_activities[0].id,
            'activity_ordinal': 1,
            'program': self.program.id,
            'scope': self.student.id,
        })

        inconsistent_results = self.student_api.get(
            'pd', {'variable': 'consent'})
        consistent_results = self.student_api.get(
            'pd', {'variable': 'consent'}, ancestor=self.student)

        self.assertEquals(len(inconsistent_results), 0)
        self.assertEquals(len(consistent_results), 1)

    def test_progress_pds_never_decrease_in_value(self):
        """Progress pds lower in value than existing ones get written as
        deleted."""

        kw = {
            'variable': 's1__progress',
            'activity': self.student_activities[0].id,
            'activity_ordinal': 1,
            'program': self.program.id,
            'scope': self.student.id,
        }

        self.student_api.create('pd', dict(kw, **{'value': '50'}))

        # A pd in another program, or with a different variable shouldn't cause
        # any conflict.
        self.student_api.create('pd', dict(kw, **{'variable': 's2__progress',
                                                  'value': '100'}))
        self.student_api.create('pd', dict(kw, **{'program': 'fake_program',
                                                  'value': '100'}))

        # Putting a *higher* value should work.
        self.student_api.create('pd', dict(kw, **{'value': '70'}))
        higher_results = self.student_api.get(
            'pd', {'variable': 's1__progress'}, ancestor=self.student)
        self.assertEquals(higher_results[0].value, '70')

        # Putting a *lower* value should not work.
        self.student_api.create('pd', dict(kw, **{'value': '60'}))
        higher_results = self.student_api.get(
            'pd', {'variable': 's1__progress'}, ancestor=self.student)
        self.assertNotEquals(higher_results[0].value, '60')

        # Full history should be availabe.
        all_pd = Pd.all().filter('variable =', 's1__progress') \
                         .filter('program =', self.program.id) \
                         .ancestor(self.student) \
                         .order('created') \
                         .fetch(4)

        self.assertTrue(all_pd[0].deleted)
        self.assertFalse(all_pd[1].deleted)
        self.assertTrue(all_pd[2].deleted)

        self.assertEquals(all_pd[0].value, '50')
        self.assertEquals(all_pd[1].value, '70')
        self.assertEquals(all_pd[2].value, '60')
