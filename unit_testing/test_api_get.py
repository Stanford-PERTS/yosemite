import webapp2
import webtest
import unittest
import json
from google.appengine.ext import testbed
from google.appengine.api import users as app_engine_users

from api_handlers import GetHandler

from core import *


class ApiGetTest(unittest.TestCase):
    pass
    # @todo: test this code, it should be able to hit api urls
    # def setUp(self):
    #     # Create a WSGI application.
    #     app = webapp2.WSGIApplication([('/api/get/(.*)', GetHandler)])
    #     # Wrap the app with WebTest's TestApp.
    #     self.testapp = webtest.TestApp(app)

    #     # the normal db and user stub stuff
    #     self.testbed = testbed.Testbed()
    #     self.testbed.activate()
    #     self.testbed.init_datastore_v3_stub()
    #     self.testbed.init_user_stub()

    # def tearDown(self):
    #     self.testbed.deactivate()

    # def init_god(self):
    #     g = User.create(user_type='god')
    #     g.put()
    #     return g

    # def test_get_user(self):
    #     g = self.init_god()
    #     response = self.testapp.get('/api/get/user?id=' + g.id)

    #     self.assertEqual(response.status_int, 200)
    #     self.assertEqual(response.content_type, 'text/json')

    #     # if there's a json syntax problem, this will correctly raise an excp.
    #     json_data = json.loads(response.normal_body)

    #     self.assertTrue(json_data[u'success'])

    #     data = json_data[u'data']
    
    #     user_dict = data[0]
    #     self.assertEqual(user_dict[u'id'], g.id)
