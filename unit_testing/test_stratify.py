"""Test randomized stratification."""

import collections
import random

import config
import util
import unit_test_helper


class StratiferTestCase(unit_test_helper.InconsistentTestCase):

    # See: http://docs.python.org/2/library/unittest.html#assert-methods

    def test_hash_dict(self):
        """History hashes are unique and reliable."""
        same1 = {'a': 1, 'b': 2, 'c': 3}
        same2 = {'b': 2, 'a': 1, 'c': 3}
        same3 = {'c': 3, 'b': 2, 'a': 1}
        different = {'a': 2, 'd': 7}
        self.assertEqual(util.hash_dict(same1), util.hash_dict(same2))
        self.assertEqual(util.hash_dict(same2), util.hash_dict(same3))
        self.assertEqual(util.hash_dict(same1), util.hash_dict(same3))
        self.assertNotEqual(util.hash_dict(same1), util.hash_dict(different))

    def init_candidate_tests(self):
        # Assume these are the desired proportions
        return {'treatment': 1, 'control': 1}

    def test_candidates_when_empty(self):
        """If no one has been assigned, return all conditions"""
        proportions = self.init_candidate_tests()
        history = {'treatment': 0, 'control': 0}
        conditions = self.internal_api.get_candidate_conditions(
            proportions, history)
        self.assertEqual(set(conditions), set(proportions.keys()))

    def test_candidates_when_balanced(self):
        """if all conditions are proportionally represented, return all"""
        proportions = self.init_candidate_tests()
        history = {'treatment': 5, 'control': 5}
        conditions = self.internal_api.get_candidate_conditions(
            proportions, history)
        self.assertEqual(set(conditions), set(proportions.keys()))

    def test_candidates_when_within_margin(self):
        """Even if the ratios aren't exact, if they're within the margin,
        randomize across all conditions."""
        # Specify the margin we're testing, so we can set up a specific case
        # that won't fail just because we adjust the margin setting in
        # in production.
        proportions = self.init_candidate_tests()
        history = {'treatment': 10, 'control': 12}
        conditions = self.internal_api.get_candidate_conditions(
            proportions, history, margin=0.05)
        self.assertEqual(set(conditions), set(proportions.keys()))

    def test_candidates_when_outside_margin(self):
        """If ratios are too far off, favor the underrepresented condition."""
        proportions = self.init_candidate_tests()
        # Two conditions have ideal ratios, we should get the third
        history = {'treatment': 10, 'control': 13}
        conditions = self.internal_api.get_candidate_conditions(
            proportions, history, margin=0.05)
        self.assertEqual(set(conditions), set(['treatment']))

    def test_stratification(self):
        """Stratifies 1000 users with various attributes within tolerances."""
        proportions = {'treatment': 1, 'control': 1}
        runs = 1000
        margin = 0.05

        name = 'student_condition'
        program_id = 'Program_XYZ'
        classrooms = ["Classroom_ABC",
                      "Classroom_DEF",
                      "Classroom_GHI",
                      "Classroom_JKL",
                      "Classroom_MNO"]

        classroom_totals = collections.defaultdict(lambda: 0)
        all_totals = {'treatment': 0, 'control': 0}
        for x in range(runs):
            classroom = classrooms[x % 5]
            condition = self.internal_api.stratify(
                program_id, name, proportions, {"classroom": classroom})
            classroom_totals[classroom + condition] += 1
            all_totals[condition] += 1

        classroom_runs = runs / len(classrooms)
        # print classroom_totals
        # print classroom_runs

        for condition in proportions.keys():
            self.assertLessEqual(all_totals[condition] / float(runs), 0.5 + margin)
            for classroom in classrooms:
                n = classroom_totals[classroom + condition]
                self.assertLessEqual(n / float(classroom_runs), 0.5 + margin)
