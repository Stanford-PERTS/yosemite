"""Test the program app.

Depends on the presence of the TP1 program folder, /programs/TP1, and
corresponding data (e.g. config.py, teacher.html, student.html).
"""

import unittest
import webtest

from api import Api
from core import *
import page_handlers
import unit_test_helper


class ProgramAppTestCase(unit_test_helper.PertsTestCase):
    def set_up(self):
        # Load our page handler webapp and wrap it with WebTest's TestApp.
        self.testapp = webtest.TestApp(page_handlers.app)

        # db with well-behaved strong consistency
        self.testbed.init_datastore_v3_stub()

        self.init_context()

    def init_context(self):
        # public api
        self.p_api = Api(User(user_type='public'))

        # This closely follows the pattern of the populate script in god.html
        self.researcher = User(user_type='researcher')
        self.researcher.put()
        self.r_api = Api(self.researcher)
        self.teacher = User.create(user_type='teacher')
        self.teacher.put()
        self.t_api = Api(self.teacher)

        self.school = self.r_api.create('school', {'name': 'DGN'})
        self.program = self.r_api.create('program', {
            'name': 'Test Program',
            'abbreviation': 'TP1',
        })
        self.bad_program = self.r_api.create('program', {
            'name': 'Bad Program',
            'abbreviation': 'TP2',
        })
        self.cohort = self.r_api.create('cohort', {
            'name': 'DGN 2014',
            'code': 'trout viper',
            'program': self.program.id,
            'school': self.school.id,
        })
        self.bad_cohort = self.r_api.create('cohort', {
            'name': 'bad cohort',
            'code': 'king dolphin',
            'program': self.bad_program.id,
            'school': self.school.id,
        })
        self.r_api.associate('associate', self.teacher, self.cohort)
        self.classroom = self.t_api.create('classroom', {
            'name': "English 101",
            'user': self.teacher.id,
            'program': self.program.id,
            'cohort': self.cohort.id,
        })
        # the researcher has to create this one, since the teacher is only
        # associated with the "good" program.
        self.bad_classroom = self.r_api.create('classroom', {
            'name': "English 101",
            'user': self.teacher.id,
            'program': self.bad_program.id,
            'cohort': self.bad_cohort.id,
        })

        # Identify a student into a classroom. See
        # url_handlers._create_student()
        self.student = self.p_api.create('user', {
            'user_type': 'student',
            'classroom': self.classroom.id,
        })
        self.student.put()

    @unittest.skip("Throwing errors in production. Issue #260.")
    def test_malformed_urls(self):
        correct_urls = [
            '/p/TP1/teacher?cohort={}'.format(self.cohort.id),
            '/p/TP1/student?cohort={}&classroom={}'.format(
                self.cohort.id, self.classroom.id),
        ]

        for url in correct_urls:
            response = self.testapp.get(url)
            self.assertEqual(response.status_int, 200, msg=url)

        # Now we test a bunch of urls that return 404s. 404s in webtest raises
        # an exception, which we can assert.

        malformed_urls = [
            # urls with no arguments shouldn't work
            '/p/TP1/student',
            '/p/TP1/teacher',
            # student missing classroom
            '/p/TP1/student?cohort={}'.format(self.cohort.id),
            # student missing cohort
            '/p/TP1/student?classroom={}'.format(self.classroom.id),
            # teacher, mis-associated cohort
            '/p/TP1/teacher?cohort={}'.format(self.bad_cohort.id),
            # student, mis-associated cohort
            '/p/TP1/teacher?cohort={}&classroom={}'.format(
                self.bad_cohort.id, self.classroom.id),
            # student, mis-associated classroom
            '/p/TP1/student?cohort={}&classroom={}'.format(
                self.cohort.id, self.bad_classroom.id),
            # teacher, non-existent cohort
            '/p/TP1/teacher?cohort=DNE',
            # student, non-existent cohort
            '/p/TP1/student?cohort={}&classroom={}'.format(
                'DNE', self.classroom.id),
            # student, non-existent classroom
            '/p/TP1/student?cohort={}&classroom={}'.format(
                self.cohort.id, 'DNE'),
            # student, both non-existent
            '/p/TP1/student?cohort={}&classroom={}'.format(
                'DNE', 'DNE'),
        ]

        for url in malformed_urls:
            self.assertRaises(webtest.AppError, self.testapp.get, url)
