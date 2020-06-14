"""Provide example code for writing unit tests."""

import unittest


@unittest.skip("Remove this line in test.example.py to see examples.")
class ExampleTest(unittest.TestCase):
    """Collection of unit test examples, showcasing features.

    Read more about the kinds of assertions here:
    https://docs.python.org/2/library/unittest.html#unittest.TestCase
    """

    def test_true(self):
        """This should succeed but doesn't."""
        print "@@@ Look! Print statements are copied into failure details!"
        my_var = 2
        self.assertEqual(1, my_var,
                         "Handy debugging message: {}".format(my_var))

    @unittest.skip("demonstrating skipping")
    def test_skip_me_1(self):
        """A test to skip."""
        self.fail("shouldn't happen")

    @unittest.skipIf(1 > 0, "this is a reason why we skipped this test")
    def test_skip_me_2(self):
        """Another test to skip."""
        self.fail("shouldn't happen")

    @unittest.skipUnless(0 > 1, "this is a reason why we skipped this test")
    def test_skip_me_3(self):
        """Another test to skip."""
        self.fail("shouldn't happen")

    @unittest.expectedFailure
    def test_fail(self):
        """This test is designed to fail."""
        self.fail("this is supposed to fail")

    @unittest.expectedFailure
    def test_succeed(self):
        """This test is expected to fail but doesn't."""
        # Note that returning False doesn't make the test fail.
        return False

    def test_raise_exception(self):
        """This test raises an exception."""
        raise Exception("This is the exception message.")
