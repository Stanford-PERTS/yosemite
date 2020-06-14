"""Test mapper functions of systematic update jobs."""
# -*- coding: utf-8 -*-
# The above comment (WHICH MUST REMAIN ON LINE 2 OF THIS FILE) instructs
# python to interpret the source code in this file to be of the specified
# encoding. Important because we have unicode literals hard coded here.
# See http://legacy.python.org/dev/peps/pep-0263/

import copy
import unittest

import mapreduce

from core import *
import map as map_module  # don't collide with native function map()
import phrase
import unit_test_helper


class SystematicUpdateTestCase(unit_test_helper.PertsTestCase):

    ### testing functions ###

    # See: http://docs.python.org/2/library/unittest.html#assert-methods

    def test_lower_case_login(self):
        """Check that the mapper function properly changes all possible values
        of a user's auth_id and login_email."""
        num_users = 100
        email_length = 20

        for x in range(num_users):
            # Generate a random user, sometimes with string data, sometimes
            # with None.
            chars = string.digits + string.letters + string.punctuation
            rand_str = ''.join(random.choice(chars) for x in range(20))
            email = rand_str + '@a.aa' if random.random() > 0.5 else None
            auth_id = 'direct_' + rand_str if random.random() > 0.5 else None
            user = User(login_email=email, auth_id=auth_id)

            # Set up a fake job context for the mapper
            conf = map_module.lower_case_login(submit_job=False)
            context = map_module.get_fake_context(conf)

            # Manipulate the user
            mapper = map_module.LowerCaseLoginMapper()
            user = mapper.do(context, user)

            # Check that the user has been manipulated properly
            if user.auth_id is not None:
                self.assertEquals(user.auth_id, user.auth_id.lower())
            if user.login_email is not None:
                self.assertEquals(user.login_email, user.login_email.lower())

    def test_deidentify(self):
        """Check that the mapper function properly hashes requested users."""
        # When running this for real, a secret random salt will be specified
        # by the adminstrator issuing the job. For this test, we'll use a
        # dummy value
        salt = u'salt'

        # Generate two (different) random cohort ids
        id1 = id2 = ''
        while id1 == id2:
            id1 = Cohort.generate_id(phrase.generate_phrase())
            id2 = Cohort.generate_id(phrase.generate_phrase())

        # Set up each way a user could be associated with an the cohort.
        loner = User(  # "loner" b/c no cohort associations
            first_name=u"William",
            last_name=u"Clinton",
            login_email=u"",
            stripped_first_name=util.clean_string(u"William"),
            stripped_last_name=util.clean_string(u"Clinton"),
            name=u"William",
            birth_date=datetime.date(1946, 8, 19),
            auth_id="",
            title="President",
            phone="(202) 456-1111",
            notes="This is Bill Clinton.",
            user_type="student",
        )
        standard = User(  # "standard" b/c one cohort association
            first_name=u"George",
            last_name=u"Bush",
            login_email=u"",
            stripped_first_name=util.clean_string(u"George"),
            stripped_last_name=util.clean_string(u"Bush"),
            name=u"George",
            birth_date=datetime.date(1946, 7, 6),
            auth_id="",
            title="President",
            phone="(202) 456-1111",
            notes="This is George Bush Jr.",
            assc_cohort_list=[id1],
            user_type="student",
        )
        dual = User(  # "dual" b/c two cohort associations
            first_name=u"Ban Ki-moon",
            last_name=u"\uBC18\uAE30\uBB38",
            login_email=u"",
            stripped_first_name=util.clean_string(u"Ban Ki-moon"),
            stripped_last_name=util.clean_string(u"\uBC18\uAE30\uBB38"),
            name=u"Ban",
            birth_date=datetime.date(1944, 6, 13),
            auth_id="google_123445345738",
            title="Secretary General",
            phone="(212) 963 1234",
            notes="This is Ban Ki-moon.",
            assc_cohort_list=[id1, id2],
            user_type="student",
        )
        adult = User(  # "adult" b/c user type teacher
            first_name=u"Barack",
            last_name=u"Obama",
            login_email=u"",
            stripped_first_name=util.clean_string(u"Barack"),
            stripped_last_name=util.clean_string(u"Obama"),
            name=u"Barack",
            birth_date=datetime.date(1961, 8, 4),
            auth_id="",
            title="President",
            phone="(202) 456-1111",
            notes="This is Barack Obama.",
            assc_cohort_list=[id1],
            user_type="teacher",
        )

        # Set up a fake job context for the mapper, requesting that all users
        # associated with the first cohort be deleted.
        conf = map_module.deidentify('assc_cohort_list', [id1], salt,
                                     submit_job=False)
        context = map_module.get_fake_context(conf)
        mapper = map_module.DeidentifyMapper()

        # Manipulate each user
        deidentified_loner = mapper.do(context, copy.deepcopy(loner))
        deidentified_standard = mapper.do(context, copy.deepcopy(standard))
        deidentified_dual = mapper.do(context, copy.deepcopy(dual))
        deidentified_adult = mapper.do(context, copy.deepcopy(adult))

        # Check that users not specified are not modified.
        self.assertEqual(loner, deidentified_loner)

        # Check that non-students are unchanged, even if they have the right
        # relationship.
        self.assertEqual(adult, deidentified_adult)

        # With modified users, these properties should be erased i.e. set to ''
        erased_properties = ['stripped_first_name', 'stripped_last_name',
                             'name', 'auth_id', 'title', 'phone', 'notes',
                             'auth_id']

        self.assertEqual(deidentified_standard.first_name,
                         mapper.hash(u"George", salt))
        self.assertEqual(deidentified_standard.last_name,
                         mapper.hash(u"Bush", salt))
        self.assertEqual(deidentified_standard.login_email,
                         mapper.hash(u"", salt))
        self.assertEqual(deidentified_standard.birth_date,
                         datetime.date(1946, 7, 1))

        for p in erased_properties:
            self.assertEqual(getattr(deidentified_standard, p), '')

        self.assertEqual(deidentified_dual.first_name,
                         mapper.hash(u"Ban Ki-moon", salt))
        self.assertEqual(deidentified_dual.last_name,
                         mapper.hash(u"\uBC18\uAE30\uBB38", salt))
        self.assertEqual(deidentified_dual.login_email,
                         mapper.hash(u"", salt))
        self.assertEqual(deidentified_dual.birth_date,
                         datetime.date(1944, 6, 1))

        for p in erased_properties:
            self.assertEqual(getattr(deidentified_dual, p), '')

        # If we run the process again, nothing should change b/c the job
        # should be idempotent.
        final_loner = mapper.do(context, copy.deepcopy(deidentified_loner))
        final_standard = mapper.do(context, copy.deepcopy(deidentified_standard))
        final_dual = mapper.do(context, copy.deepcopy(deidentified_dual))
        final_adult = mapper.do(context, copy.deepcopy(deidentified_adult))

        self.assertEqual(final_loner, deidentified_loner)
        self.assertEqual(final_standard, deidentified_standard)
        self.assertEqual(final_dual, deidentified_dual)
        self.assertEqual(final_adult, deidentified_adult)
