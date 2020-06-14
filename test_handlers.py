"""URL Handlers are designed to be simple wrappers over our python unit tests.
Makes calling the set of tests you want easy.
"""

from StringIO import StringIO
import codecs
import json
import logging
import sys
import traceback
import unittest  # python unit testing library
import webapp2

import config
import unit_testing  # PERTS unit test cases
from url_handlers import BaseHandler
import util


debug = util.is_development()


class TestHandler(webapp2.RequestHandler):
    """Superclass for all unit test urls."""
    def get(self, *args, **kwargs):
        """Handles all test requests, sets up unit test handlers.

        - Jsons output
        - loggs exception traces
        """

        # mark the start time of the request
        util.profiler.clear()
        util.profiler.add_event('START')

        try:
            self.write_json(self.do(*args, **kwargs))
        except Exception as error:
            trace = traceback.format_exc()
            logging.error("{}\n{}".format(error, trace))
            response = {
                'success': False,
                'message': error.__class__.__name__,
                'trace': trace,
            }
            self.write_json(response)

    # Forward POST requests to the get handler, just like in BaseHandler.
    # BaseHandler.getattr(BaseHandler, 'post') doesn't work here, dunno why.
    post = BaseHandler.__dict__['post']

    def test_case_to_dict(self, test_case):
        """Helps with outputting test case results in JSON."""
        # The id is python dot notation for the test method, e.g.
        # test_api_get.ApiGetTest.test_me
        # But, because we use two different discovery methods
        # (loadTestsFromNames() and discover()), they're not precisely the
        # same. This little trick should standardize them.
        test_id = test_case.id()
        bad_prefix = config.unit_test_directory + '.'
        if test_id[:len(bad_prefix)] == bad_prefix:
            test_id = test_id[len(bad_prefix):]
        return {
            'test': test_id,
            # First line of the test method's docstring.
            'description': test_case.shortDescription(),
        }

    def test_result_to_dict(self, test_result, print_statements=''):
        """Helps with outputting test results in JSON.

        See
        https://docs.python.org/2/library/unittest.html#unittest.TestResult"""

        # The structures we're converting to JSON are a weird and variable.
        # Wrangle them into something fully JSON-serializable.
        def stringify(results):
            """Convert all the informative properties of a unittest.TestResult
            object into something our JSON APIs can return."""
            to_return = []

            if len(results) is 0:
                return to_return

            if isinstance(results[0], tuple):
                for test_case, details in results:
                    test_info = self.test_case_to_dict(test_case)
                    test_info['details'] = details
                    to_return.append(test_info)
            elif isinstance(results[0], unittest.TestCase):
                to_return = [self.test_case_to_dict(tc) for tc in results]

            return to_return

        # Run our stringify function on all the weird properties to make a nice
        # dictionary.
        result_dict = {
            'errors': stringify(test_result.errors),
            'failures': stringify(test_result.failures),
            'skipped': stringify(test_result.skipped),
            'expected_failures': stringify(test_result.expectedFailures),
            'unexpected_successes': stringify(test_result.unexpectedSuccesses),
            'tests_run': test_result.testsRun,
            'stdout': print_statements,
        }

        # The was_successful function doesn't do exactly what you expect. It
        # returns True even if there are unexpected successes. Fix it.
        success = (test_result.wasSuccessful() and
                   len(result_dict['unexpected_successes']) is 0)
        result_dict['was_successful'] = success

        return result_dict

    def run_test_suite(self, test_suite):
        test_result = unittest.TestResult()

        # To capture print statements while running tests (useful for
        # debugging), replace the normal stdout with our own stream.
        original_stdout = sys.stdout
        sys.stdout = StringIO()

        # Run the tests
        test_result = test_suite.run(test_result)

        # Then capture printed statements so we can return them
        print_statements = sys.stdout.getvalue()

        # Write them to a utf-8 capable std out so we can read them in the logs
        # like normal, if we want to. Normal stdout can't write unicode, see:
        # http://stackoverflow.com/questions/1473577/writing-unicode-strings-via-sys-stdout-in-python
        utf8_stdout = codecs.getwriter('UTF-8')(original_stdout)
        utf8_stdout.write(print_statements)

        # and put things back the way we found them.
        sys.stdout = original_stdout

        return test_result, print_statements

    def write_json(self, obj):
        r = self.response
        r.headers['Content-Type'] = 'application/json; charset=utf-8'
        r.write(json.dumps(obj))


class AllHandler(TestHandler):
    """Run every test we have."""
    def do(self):
        test_loader = unittest.loader.TestLoader()
        test_suite = test_loader.discover(config.unit_test_directory)
        test_result, print_statements = self.run_test_suite(test_suite)
        result_dict = self.test_result_to_dict(test_result, print_statements)

        return {'success': True, 'data': result_dict}


class SomeHandler(TestHandler):
    """Run the named tests.

    Use python dot notation to name the tests, see:
    https://docs.python.org/2/library/unittest.html#unittest.TestLoader.loadTestsFromName

    Requires the request variable 'name' for a single name or 'name_json' for
    a list of names. The presence of the second overrides the first.
    """
    def do(self):
        params = util.get_request_dictionary(self.request)
        if isinstance(params[u'name'], unicode):
            test_names = [params[u'name']]
        elif isinstance(params[u'name'], list):
            test_names = params[u'name']
        else:
            raise Exception("Invalid name: {}.".format(params['name']))

        test_loader = unittest.loader.TestLoader()
        test_suite = test_loader.loadTestsFromNames(test_names, unit_testing)
        test_result, print_statements = self.run_test_suite(test_suite)
        result_dict = self.test_result_to_dict(test_result, print_statements)

        return {'success': True, 'data': result_dict}

webapp2_config = {
    # nothing to configure
}


app = webapp2.WSGIApplication([
    ('/unit_test/all/?', AllHandler),
    ('/unit_test/some/?', SomeHandler),
], config=webapp2_config, debug=debug)
