"""Testing accessory functions of api.py."""

import unittest

from api import Api
from core import *
from cron import Cron
from named import *
import unit_test_helper


class ApiUtilTestCase(unit_test_helper.PertsTestCase):
    def set_up(self):
        # We don't need to model consistency here. This version of the
        # datastore always returns consistent results.
        self.testbed.init_datastore_v3_stub()
