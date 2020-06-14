from google.appengine.ext import db
import webapp2

import util


class DatastoreConnection(db.Model):
    @classmethod
    def initialize_connection(self):
        return DatastoreConnection.get_or_insert('connection')


class ConnectionHandler(webapp2.RequestHandler):
    def get(self):
        # Some poorly-behaved libraries screw with the default logging level,
        # killing our 'info' and 'warning' logs. Make sure it's set correctly
        # for our code.
        util.allow_all_logging()

        c = DatastoreConnection.initialize_connection()
        self.response.headers['Content-Type'] = 'text/plain; charset=utf-8'
        self.response.write(str(c) if c else 'None')

app = webapp2.WSGIApplication([('/initialize_connection', ConnectionHandler)])
