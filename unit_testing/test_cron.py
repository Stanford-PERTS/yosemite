"""Testing cron functions."""

from google.appengine.api import taskqueue
import datetime
import time
import unittest

from api import Api
from core import *
from cron import Cron
from named import *
import unit_test_helper


class CronTestCase(unit_test_helper.PopulatedInconsistentTestCase):
    def test_aggregate(self):
        """Test aggregation of pds to activities.

        Documentation of Yosemite aggregation:
        https://docs.google.com/document/d/1tmZhuWMDX29zte6f0A8yXlSUvqluyMNEnFq8qyJq1pA
        TODO(chris): actually write the documentation!
        """
        cron = Cron(self.internal_api)

        # To insulate the expected aggregation stats from changes to the
        # populate script, we'll create a separate cohort and classroom. For
        # larger things we'll rely on the stuff set by the populate script,
        # e.g. self.program.
        cohort = self.researcher_api.create('cohort', {
            'name': 'DGN 2015',
            'code': 'lion mackerel',
            'program': self.program.id,
            'school': self.school.id,
        })
        self.researcher_api.associate('set_owner', self.school_admin, cohort)
        classroom = self.school_admin_api.create('classroom', {
            'name': "English 201",
            'user': self.school_admin.id,
            'program': self.program.id,
            'cohort': cohort.id,
        })
        student_activities = self.school_admin_api.init_activities(
            'student', self.school_admin.id, self.program.id,
            cohort_id=cohort.id, classroom_id=classroom.id)
        db.get([cohort.key(), classroom.key()])
        db.get([a.key() for a in student_activities])

        # To test aggregating across multiple users, we'll need several
        # students
        student_params = {'user_type': 'student', 'classroom': classroom.id}

        mystery_finisher = self.public_api.create('user', student_params)
        absentee = self.public_api.create('user', student_params)
        refusee = self.public_api.create('user', student_params)
        expelee = self.public_api.create('user', student_params)
        mr_perfect = self.public_api.create('user', student_params)
        non_finisher = self.public_api.create('user', student_params)
        wrong_name = self.public_api.create('user', student_params)

        # This student will be in another classroom, and we won't update her,
        # proving that cohort aggregation re-queries more than just the changed
        # stuff.
        other_classroom = self.school_admin_api.create('classroom', {
            'name': "English 202",
            'user': self.school_admin.id,
            'program': self.program.id,
            'cohort': cohort.id,
        })
        other_student_activities = self.school_admin_api.init_activities(
            'student', self.school_admin.id, self.program.id,
            cohort_id=cohort.id, classroom_id=other_classroom.id)
        other_student = self.public_api.create(
            'user', {'user_type': 'student', 'classroom': other_classroom.id})

        students = [mystery_finisher, absentee, refusee, expelee, mr_perfect,
                    non_finisher, wrong_name]
        student_keys = [s.key() for s in students]

        others = [other_student, other_classroom] + other_student_activities
        other_keys = [e.key() for e in others]

        ### Aggregate initial state

        # Assume and simulate that enough time passes between data recording
        # and cron execution that entities become consistent.
        db.get(student_keys)
        db.get(other_keys)

        cron.aggregate()

        # Every student have the same aggregation data for both activities
        # because no one has done anything yet. So just loop and check against
        # the same reference.
        for s in db.get(student_keys):
            self.assertFalse(s.certified)
            correct_stats = {'progress': None}
            self.assertEqual(s.aggregation_data[1], correct_stats)
            self.assertEqual(s.aggregation_data[2], correct_stats)

        # Both activities should be the same also
        a1, a2 = db.get([a.key() for a in student_activities])
        correct_stats = {
            'total_students': 7,
            'certified_students': 0,
            'certified_study_eligible_dict': {
                'n': 0,
                'completed': 0,
                'makeup_eligible': 0,
                'makeup_ineligible': 0,
                'uncoded': 0
            },
        }
        self.assertEqual(a1.aggregation_data, correct_stats)
        self.assertEqual(a2.aggregation_data, correct_stats)

        # The other activities should look like this (this is the last time
        # we'll have to check it because we won't be changing it any more):
        a1, a2 = db.get([a.key() for a in other_student_activities])
        correct_stats = {
            'total_students': 1,
            'certified_students': 0,
            'certified_study_eligible_dict': {
                'n': 0,
                'completed': 0,
                'makeup_eligible': 0,
                'makeup_ineligible': 0,
                'uncoded': 0
            },
        }
        self.assertEqual(a1.aggregation_data, correct_stats)
        self.assertEqual(a2.aggregation_data, correct_stats)

        # Check cohort (has our seven plus one other)
        cohort = db.get(cohort.key())
        correct_cohort_stats = {
            'unscheduled': 2, 'scheduled': 0, 'behind': 0, 'completed': 0,
            'incomplete_rosters': 2,
            'total_students': 8,
            'certified_students': 0,
            'certified_study_eligible_dict': {
                'n': 0,
                'completed': 0,
                'makeup_eligible': 0,
                'makeup_ineligible': 0,
                'uncoded': 0
            },
        }
        self.assertEqual(cohort.aggregation_data[1], correct_cohort_stats)
        self.assertEqual(cohort.aggregation_data[2], correct_cohort_stats)

        ### Pretend the school admin just certified some students and aggregate
        ### again.

        # NOT changing mystery_finisher proves that the aggregator re-queries
        # for unchanged users associated with the same activity.
        certified_students = [absentee, refusee, expelee, mr_perfect,
                              non_finisher]
        for s in certified_students:
            s.certified = True
        db.put(certified_students)

        # Assume and simulate that enough time passes between data recording
        # and cron execution that entities become consistent.
        db.get(student_keys)

        cron.aggregate()

        # Every student should be the same for both activities.
        for s in db.get(student_keys):
            correct_stats = {'progress': None}
            self.assertEqual(s.aggregation_data[1], correct_stats)
            self.assertEqual(s.aggregation_data[2], correct_stats)

        # Both activities should be the same also
        a1, a2 = db.get([a.key() for a in student_activities])
        correct_stats = {
            'total_students': 7,
            'certified_students': 5,
            'certified_study_eligible_dict': {
                'n': 5,
                'completed': 0,
                'makeup_eligible': 0,
                'makeup_ineligible': 0,
                'uncoded': 5
            },
        }
        self.assertEqual(a1.aggregation_data, correct_stats)
        self.assertEqual(a2.aggregation_data, correct_stats)

        # Check cohort
        cohort = db.get(cohort.key())
        correct_cohort_stats = {
            'unscheduled': 2, 'scheduled': 0, 'behind': 0, 'completed': 0,
            'incomplete_rosters': 2,
            'total_students': 8,
            'certified_students': 5,
            'certified_study_eligible_dict': {
                'n': 5,
                'completed': 0,
                'makeup_eligible': 0,
                'makeup_ineligible': 0,
                'uncoded': 5
            },
        }
        self.assertEqual(cohort.aggregation_data[1], correct_cohort_stats)
        self.assertEqual(cohort.aggregation_data[2], correct_cohort_stats)

        ### Simulate the first session, with two students absent and one who
        ### doesn't finish. Also schedule the first activity.

        absentee.s1_status_code = 'A'  # code for absent
        refusee.s1_status_code = 'PR'  # code for parent refusal
        expelee.s1_status_code = 'E'  # code for expelled
        wrong_name.s1_status_code = 'MWN'  # code for merge: wrong name
        db.put([absentee, refusee, expelee, wrong_name])

        progress_pds = []
        pd_params = {
            'variable': 's1__progress',
            'program': self.program.id,
            'activity': student_activities[0].id,
            'activity_ordinal': 1,
        }
        # Progress on activity 1 for those who finished.
        for s in [mr_perfect, mystery_finisher, wrong_name]:
            pd_params['value'] = '100'
            pd_params['scope'] = s.id
            progress_pds.append(Api(s).create('pd', pd_params))
        # Progress on activity 1 for those who didn't finish.
        pd_params['value'] = '50'
        pd_params['scope'] = non_finisher.id
        progress_pds.append(Api(non_finisher).create('pd', pd_params))

        a1.scheduled_date = datetime.date.today()
        a1.put()

        # Assume and simulate that enough time passes between data recording
        # and cron execution that entities become consistent.
        db.get([pd.key() for pd in progress_pds] +
               [absentee.key(), refusee.key(), expelee.key(), a1.key()])

        cron.aggregate()

        # Check that user stats are right.
        correct_stats = [
            {'progress': 100},  # mystery_finisher
            {'progress': None},  # absentee
            {'progress': None},  # refusee
            {'progress': None},  # expelee
            {'progress': 100},  # mr_perfect
            {'progress': 50},  # non_finisher
            {'progress': 100},  # wrong_name
        ]
        for index, s in enumerate(students):
            s = db.get(s.key())
            self.assertEqual(s.aggregation_data[1], correct_stats[index])

        # Check that activity stats are right.
        a1 = db.get(student_activities[0].key())
        correct_stats = {
            # Total has decreased b/c MWN students are dropped from the counts
            # completely. This is because they're not really a person, they're
            # a duplicate representation of a different real person.
            'total_students': 6,
            'certified_students': 5,
            'certified_study_eligible_dict': {
                'n': 4,
                'completed': 1,
                'makeup_eligible': 1,
                'makeup_ineligible': 1,
                'uncoded': 1
            },
        }
        self.assertEqual(a1.aggregation_data, correct_stats)
        # Activity 2 shouldn't register any of the progress we've made on
        # activity 1.
        a2 = db.get(student_activities[1].key())
        correct_stats = {
            'total_students': 6,
            'certified_students': 5,
            'certified_study_eligible_dict': {
                'n': 5,
                'completed': 0,
                'makeup_eligible': 0,
                'makeup_ineligible': 0,
                'uncoded': 5
            },
        }
        self.assertEqual(a2.aggregation_data, correct_stats)

        # Check cohort (again, similar, but with a larger 'all' total).
        cohort = db.get(cohort.key())
        correct_cohort_stats = {
            1: {
                'unscheduled': 1, 'scheduled': 1, 'behind': 0, 'completed': 0,
                'incomplete_rosters': 2,
                'total_students': 7,
                'certified_students': 5,
                'certified_study_eligible_dict': {
                    'n': 4,
                    'completed': 1,
                    'makeup_eligible': 1,
                    'makeup_ineligible': 1,
                    'uncoded': 1
                },
            },
            2: {
                'unscheduled': 2, 'scheduled': 0, 'behind': 0, 'completed': 0,
                'incomplete_rosters': 2,
                'total_students': 7,
                'certified_students': 5,
                'certified_study_eligible_dict': {
                    'n': 5,
                    'completed': 0,
                    'makeup_eligible': 0,
                    'makeup_ineligible': 0,
                    'uncoded': 5
                },
            }
        }
        self.assertEqual(cohort.aggregation_data, correct_cohort_stats)

    def test_aggregate_handles_duplicates(self):
        """If multiple progress pd, aggregator chooses the largest one."""
        # Create w/o the api to intentionally create duplicates
        pd_id1 = 'Pd_1.' + self.student.id
        pd_id2 = 'Pd_2.' + self.student.id
        pd_id3 = 'Pd_3.' + self.student.id
        pd_id4 = 'Pd_4.' + self.student.id
        pd1 = Pd(key_name=pd_id1, id=pd_id1, parent=self.student,
                 scope=self.student.id, program=self.program.id,
                 activity_ordinal=1,
                 variable='s1__progress', value='66', public=True)
        pd2 = Pd(key_name=pd_id2, id=pd_id2, parent=self.student,
                 scope=self.student.id, program=self.program.id,
                 activity_ordinal=1,
                 variable='s1__progress', value='33', public=True)
        pd3 = Pd(key_name=pd_id3, id=pd_id3, parent=self.student,
                 scope=self.student.id, program=self.program.id,
                 activity_ordinal=2,
                 variable='s2__progress', value='100', public=True)
        pd4 = Pd(key_name=pd_id4, id=pd_id4, parent=self.student,
                 scope=self.student.id, program=self.program.id,
                 activity_ordinal=2,
                 variable='s2__progress', value='66', public=True)

        # Put them in a confusing order on purpose, to try to get the
        # aggregator to process them from largest to smallest.
        db.put([pd1, pd3])
        db.put([pd2, pd4])

        # Prove that there are duplicates.
        duplicates = self.student_api.get('pd', {}, ancestor=self.student)
        self.assertEquals(len(duplicates), 4)

        # Aggregate and check results.
        cron = Cron(self.internal_api)
        cron.aggregate()
        student = db.get(self.student.key())
        self.assertEquals(
            student.aggregation_data,
            {1: {'progress': 66}, 2: {'progress': 100}})
        # Student should also have COM for s2 b/c they hit 100.
        self.assertEquals(student.s2_status_code, 'COM')

    def test_aggregation_does_not_change_modified_time(self):
        cron = Cron(self.internal_api)

        # Create a fake set of data to aggregate: A cohort, classroom,
        # student activities, a student, and a pd value for that student.
        cohort = self.researcher_api.create('cohort', {
            'name': 'DGN 2015',
            'code': 'lion mackerel',
            'program': self.program.id,
            'school': self.school.id,
        })
        self.researcher_api.associate('set_owner', self.school_admin, cohort)
        classroom = self.school_admin_api.create('classroom', {
            'name': "English 201",
            'user': self.school_admin.id,
            'program': self.program.id,
            'cohort': cohort.id,
        })
        student_activities = self.school_admin_api.init_activities(
            'student', self.school_admin.id, self.program.id,
            cohort_id=cohort.id, classroom_id=classroom.id)
        db.get([cohort.key(), classroom.key()])
        db.get([a.key() for a in student_activities])
        student_params = {'user_type': 'student', 'classroom': classroom.id}
        student = self.public_api.create('user', student_params)
        student = db.get(student.key())
        pd_params = {
            'variable': 's1__progress',
            'program': self.program.id,
            'activity': student_activities[0].id,
            'activity_ordinal': 1,
            'value': 100,
            'scope': student.id,
        }
        pd = Api(student).create('pd', pd_params)
        db.get(pd.key())

        # First prove that modified times ARE set in this context for normal
        # writes. The student's progress has NOT been written to the user
        # entity yet.
        modified_before = student.modified
        time.sleep(0.1)
        student.first_name = 'mister'
        student.put()
        modified_after = db.get(student.key()).modified
        self.assertEquals(student.aggregation_data,
                          {1: {'progress': None}, 2: {'progress': None}})
        self.assertNotEqual(modified_before, modified_after)

        # Now aggregate, which should write the pd's progress value to the
        # user, but should NOT update the user's modified time.
        modified_before = modified_after
        time.sleep(0.1)
        cron.aggregate()
        student = db.get(student.key())
        modified_after = db.get(student.key()).modified
        self.assertEquals(student.aggregation_data,
                          {1: {'progress': 100}, 2: {'progress': None}})
        self.assertEquals(modified_before, modified_after)

    def test_aggregate_more_than_thirty_classrooms(self):
        """Aggregation uses an IN filter, which breaks App Engine when it has
        more than 30 elements in it. There should be code to handle this."""

        cron = Cron(self.internal_api)

        # To insulate the expected aggregation stats from changes to the
        # populate script, we'll create a separate cohort and classroom. For
        # larger things we'll rely on the stuff set by the populate script,
        # e.g. self.program.
        cohort = self.researcher_api.create('cohort', {
            'name': 'DGN 2015',
            'code': 'lion mackerel',
            'program': self.program.id,
            'school': self.school.id,
        })
        db.get(cohort.key())
        self.researcher_api.associate('set_owner', self.school_admin, cohort)

        # Create 31 different students in as many different classrooms.
        classrooms, student_activities, students = [], [], []
        for x in range(30):
            c = self.school_admin_api.create('classroom', {
                'name': "English " + str(x),
                'user': self.school_admin.id,
                'program': self.program.id,
                'cohort': cohort.id,
            })
            c = db.get(c.key())

            acts = self.school_admin_api.init_activities(
                'student', self.school_admin.id, self.program.id,
                cohort_id=cohort.id, classroom_id=c.id)
            acts = db.get([a.key() for a in acts])

            s = self.public_api.create('user', {'user_type': 'student',
                                                'classroom': c.id})
            classrooms.append(c)
            student_activities += acts
            students.append(s)

        # Bring them all into full db consistency.
        db.get([s.key() for s in students])

        cron.aggregate()

        # All activities should show one student.
        student_activities = db.get([a.key() for a in student_activities])
        correct_stats = {
            'total_students': 1,
            'certified_students': 0,
            'certified_study_eligible_dict': {
                'n': 0,
                'completed': 0,
                'makeup_eligible': 0,
                'makeup_ineligible': 0,
                'uncoded': 0
            },
        }
        for a in student_activities:
            self.assertEqual(a.aggregation_data, correct_stats)

    def test_aggregate_queues_tasks(self):
        cron = Cron(self.internal_api)
        queue = taskqueue.Queue(name='default')

        # Since this test inherits a populated stub datastore, some tasks
        # have already been queued. Set that as the baseline.
        baseline = queue.fetch_statistics().tasks

        # Now aggregate the entities that have been pre-populated, which
        # includes one classroom and one cohort. This should queue 3 tasks: one
        # classroom roster, one cohort roster, and one cohort schedule.
        cron.aggregate()

        post_aggregation = queue.fetch_statistics().tasks
        self.assertEqual(post_aggregation - baseline, 3)
