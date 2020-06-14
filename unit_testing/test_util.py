#"""Testing functions for the util module."""
# -*- coding: utf-8 -*-
# The above comment (WHICH MUST REMAIN ON LINE 2 OF THIS FILE) instructs
# python to interpret the source code in this file to be of the specified
# encoding. Important because we have unicode literals hard coded here.
# See http://legacy.python.org/dev/peps/pep-0263/

import re
import unittest

import unit_test_helper
import util


class UtilTestCase(unit_test_helper.PertsTestCase):
    def test_clean_string(self):
        """Test that clean_string() returns only lowercase a-z of type str."""
        strings_to_clean = [
            u'Nicholas',
            u'Nicolás',
            u'N1colas',
            u'N#$colas',
            u'Nichol"a"s',
            u'Nich\olas',
            '12345',  # Some schools want to use ids rather than last names
            'Nicholas',
            'N1colas',
            'N#$colas',
            'Nichol"a"s',
            "Nich\olas",
            # This guy *shouldn't* fail, but it won't return what we want it to
            # (This isn't a problem right now, because the front end is serving
            # us unicode objects, not strs.):
            'Nicolás',
        ]

        for index, test_string in enumerate(strings_to_clean):
            # Nothing but lowercase alphabetic characters and digits,
            # beginning to end.
            pattern = r'^[a-z0-9]+$'
            cleaned_string = util.clean_string(test_string)
            # re.match() will return None if the pattern doesn't match.
            self.assertIsNotNone(re.match(pattern, cleaned_string),
                                 'string index: {}'.format(index))

            # output must always be a string (not unicode)
            self.assertIsInstance(cleaned_string, str)
