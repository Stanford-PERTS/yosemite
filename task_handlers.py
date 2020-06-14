"""URL Handlers designed to be simple wrappers over our tasks. See map.py."""

import json
import logging
import time
import traceback
import webapp2

from api import Api
import core
import util


debug = util.is_development()


class TaskWorker(webapp2.RequestHandler):
    def dispatch(self):
        self.api = Api(core.User.create(user_type='god'))
        # Call the overridden dispatch(), which has the effect of running
        # the get() or post() etc. of the inheriting class.
        webapp2.RequestHandler.dispatch(self)


class RosterWorker(TaskWorker):
    """Cache a roster.

    Triggered when classrooms or users are written, after clearing memcache, so
    the roster can be re-cached immediately without delaying the user's
    request.
    """
    def post(self, entity_id):
        # False means force the function to ignore whatever is currently in
        # memcache and to go straight to the datastore. Important if there are
        # several concurrent writes queued to the same roster.
        self.api.get_roster(entity_id, allow_memcache_retrieval=False)


class ScheduleWorker(TaskWorker):
    """Cache a schedule.

    See RosterWorker for comments.
    """
    def post(self, cohort_id):
        self.api.get_schedule(cohort_id, allow_memcache_retrieval=False)


webapp2_config = {
    'webapp2_extras.sessions': {
        # cam. I think this is related to cookie security. See
        # http://webapp-improved.appspot.com/api/webapp2_extras/sessions.html
        'secret_key': '8YcOZYHVrVCYIx972K3MGhe9RKlR7DOiPX2K8bB8',
    },
}

app = webapp2.WSGIApplication([
    ('/task/cache_roster/(.*)', RosterWorker),
    ('/task/cache_schedule/(.*)', ScheduleWorker),
], config=webapp2_config, debug=debug)
