"""URL Handlers are designed to be simple wrappers over our python cron module.
They generally convert a URL directly to an cron function call.
See cron.Cron
"""

from google.appengine.api import app_identity
from google.appengine.api import urlfetch
import httplib
import json
import logging
import traceback

from core import PermissionDenied
from cron import Cron
from url_handlers import *
import test_handlers
import util


debug = util.is_development()


class CronHandler(BaseHandler):
    """Superclass for all cron-related urls."""

    def do_wrapper(self, *args, **kwargs):
        """Do setup for cron handlers.

        - Jsons output
        - logs exception traces
        - Initializes Api-like Cron object
        """
        # Cron jobs should not be bothered with permissions. Give god access.
        self.cron = Cron(self.internal_api)

        try:
            self.write_json(self.do(*args, **kwargs))
        except Exception as error:
            trace = traceback.format_exc()
            logging.error("{}\n{}".format(error, trace))
            response = {
                'success': False,
                'message': '{}: {}'.format(error.__class__.__name__, error),
                'trace': trace,
            }
            self.write_json(response)

    def write_json(self, obj):
        r = self.response
        r.headers['Content-Type'] = 'application/json; charset=utf-8'
        r.write(json.dumps(obj))


class AggregateHandler(CronHandler):
    """See named@Aggregator for details."""
    def do(self):
        return {'success': True, 'data': self.cron.aggregate()}


class UpdateCsvCacheHandler(CronHandler):
    """Process all participant data."""
    def do(self):
        messages = {'success': True}
        messages['pd_all'] = self.cron.update_csv_cache('pd_all')
        messages['user_all'] = self.cron.update_csv_cache('user_all')
        return messages


class IndexHandler(CronHandler):
    """See named@indexer for details."""
    def do(self):
        data = self.cron.index()
        return {'success': True, 'data': data}


class CheckForErrorsHandler(CronHandler):
    """See named@errorChecker for details."""
    def do(self):
        data = self.cron.check_for_errors()
        return {'success': True, 'data': data}


class SendPendingEmail(CronHandler):
    """See core@email for details."""
    def do(self):
        data = self.cron.send_pending_email()
        return {'success': True, 'data': data}


class SendReminders(CronHandler):
    """ see cron@send_reminders for details. """
    def do(self):
        # Permissions
        # Anyone should be able to send_reminders, its an idempotent
        # function, so it can be called many times without concern.
        # However, it reports some sentive information like email
        # addresses, that only gods should be able to see.  Therefore
        # if this is called by anyone else it will not return all of
        # the data.
        try:
            data = self.cron.send_reminders()
        except PermissionDenied:
            data = "Reminders sent.  Sign in as god to see full report."
            self.cron.send_reminders()

        return {'success': True, 'data': data}


class StartGceHandler(CronHandler):
    """Initiates Instance 'X' which serializes PD data by cohort and
    saves serialized strings in GCS bucket. Cron Job, runs every X minutes."""
    def do(self, instance_name):
        # If this handler is given no_shutdown=true, the instance will be
        # launched with a different startup script that does NOT automatically
        # shut down the instance. This way it can be logged into for debugging.
        no_shutdown = self.request.get('no_shutdown') in config.true_strings
        auto_shutdown = not no_shutdown
        message = self.cron.start_gce_instance(instance_name,
                                               auto_shutdown=auto_shutdown)
        return {'success': True, 'message': message}


class DeleteGceHandler(CronHandler):
    """Fetches statuses of currently running GCE Instances.
    If instance returns status 'TERMINATED' then executes instance shutdown.
    Cron Job, to be run every X minutes."""
    def do(self):
        messages = {'success': True}
        messages['GCE'] = self.cron.delete_gce_instances()

        return messages


class BackupToGcsHandler(CronHandler):
    def do(self):
        access_token, _ = app_identity.get_access_token(
            'https://www.googleapis.com/auth/datastore')
        app_id = app_identity.get_application_id()

        entity_filter = {
            'kinds': self.request.get_all('kind'),
            'namespace_ids': self.request.get_all('namespace_id')
        }
        request = {
            'project_id': app_id,
            'output_url_prefix': 'gs://{}'.format(self.request.get('bucket')),
            'entity_filter': entity_filter
        }
        headers = {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + access_token
        }
        url = 'https://datastore.googleapis.com/v1/projects/{}:export'.format(
            app_id)

        try:
            result = urlfetch.fetch(
                url=url,
                payload=json.dumps(request),
                method=urlfetch.POST,
                deadline=60,
                headers=headers)
            if result.status_code == httplib.OK:
                logging.info(result.content)
            elif result.status_code >= 500:
                logging.error(result.content)
            else:
                logging.warning(result.content)
            self.response.status_int = result.status_code
        except urlfetch.Error:
            raise Exception('Failed to initiate export.')

        self.response.write("Export initiated.")


class CleanGcsBucketHandler(CronHandler):
    """Empties out a URL-specified GCS bucket,"""
    def do(self, bucket):
        messages = {'success': True}
        messages[bucket] = self.cron.clean_gcs_bucket(bucket)

        return messages


class UnitTestHandler(CronHandler):
    """Runs our unit tests in production. Raises an excpetion if they fail."""
    def do(self):
        # Wrap the existing code that calls all unit tests so that an exception
        # is raised on failure.
        handler = test_handlers.AllHandler()
        response = handler.do()
        # All we care about is the 'was_successful' flag, which is only true
        # if all tests pass.
        if response['data']['was_successful']:
            return {'success': True}
        else:
            raise Exception("Unit test failed in production.\n{}".format(
                response['data']))


webapp2_config = {
    'webapp2_extras.sessions': {
        # cam. I think this is related to cookie security. See
        # http://webapp-improved.appspot.com/api/webapp2_extras/sessions.html
        'secret_key': '8YcOZYHVrVCYIx972K3MGhe9RKlR7DOiPX2K8bB8',
    },
}

app = webapp2.WSGIApplication([
    ('/cron/aggregate', AggregateHandler),
    ('/cron/index', IndexHandler),
    ('/cron/check_for_errors', CheckForErrorsHandler),
    ('/cron/send_pending_email', SendPendingEmail),
    ('/cron/send_reminders', SendReminders),
    ('/cron/update_csv_cache', UpdateCsvCacheHandler),
    ('/cron/start_gce_instance/(.*)', StartGceHandler),
    ('/cron/delete_gce_instances', DeleteGceHandler),
    ('/cron/clean_gcs_bucket/(.*)', CleanGcsBucketHandler),
    ('/cron/run_unit_tests', UnitTestHandler),
    ('/cron/backup', BackupToGcsHandler),
], config=webapp2_config, debug=debug)
