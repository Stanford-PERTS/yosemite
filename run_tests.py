#!/usr/bin/python

# to run this from the command line, cd to project root directory and run
# $> python run_tests.py /usr/local/google_appengine test

import logging
import optparse
import os
import sys
import unittest2  # you may need to install this before running tests

USAGE = """%prog SDK_PATH TEST_PATH
Run unit tests for App Engine apps.

SDK_PATH    Path to the SDK installation
TEST_PATH   Path to package containing test modules"""


def main(sdk_path, test_path):
    sys.path.insert(0, sdk_path)
    import dev_appserver
    dev_appserver.fix_sys_path()
    suite = unittest2.loader.TestLoader().discover(test_path)
    unittest2.TextTestRunner(verbosity=2).run(suite)


if __name__ == '__main__':
    parser = optparse.OptionParser(USAGE)
    options, args = parser.parse_args()
    if len(args) != 2:
        logging.error(  'Error: Exactly 2 arguments required.' )
        parser.print_help()
        sys.exit(1)
    SDK_PATH = args[0]
    TEST_PATH = args[1]
    # PERTS code expects this to be set so we can detect deployed vs.
    # not deployed (SDK i.e. dev_appserver). See environment functions like
    # is_localhost() in util.py.
    # Also important for unit testing cloudstorage api, which checks this value to
    # decide if it will talk to a stub service or the real GCS.
    os.environ['SERVER_SOFTWARE'] = 'Development/X.Y'
    main(SDK_PATH, TEST_PATH)
