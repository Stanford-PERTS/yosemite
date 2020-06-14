"""URL Handlers are designed to be simple wrappers over our python API layer.
They generally convert a URL directly to an API function call.
"""

from google.appengine.api import mail   # ForgotPasswordHandler
from google.appengine.api import urlfetch  # UserAgentStringHandler
from google.appengine.ext import db
from string import ascii_uppercase      # ForgotPasswordHandler
import json
import logging
import random                           # ForgotPasswordHandler
import string                           # ForgotPasswordHandler
import time
import traceback
import urllib                           # ForgotPasswordHandler

from core import *
from named import *
from api import kind_to_class
from url_handlers import *
import util

# make sure to turn this off in production!!
# it exposes exception messages
debug = util.is_development()


class ApiHandler(BaseHandler):
    """Superclass for all api-related urls."""

    def dispatch(self):
        if self.datastore_connected():
            # Call the overridden dispatch(), which has the effect of running
            # the get() or post() etc. of the inheriting class.
            BaseHandler.dispatch(self)
        else:
            # Sometimes the datastore doesn't respond. I really don't know why.
            # Wait a bit and try again.
            attempts = int(self.request.get('connection_attempts', 0)) + 1
            if attempts <= 10:
                time.sleep(1)
                self.redirect(util.set_query_parameters(
                    self.request.url, connection_attempts=attempts))
            else:
                logging.error('Could not connect to datastore after 10 tries.')
                # This is an api call, so the most appropriate response is
                # devvy JSON text. It prompts devs as to what has happened and
                # possibly how to fix it. The success: false bit will tell any
                # javascript using the api to retry or show an appropriate
                # message to the user.
                self.response.headers['Content-Type'] = 'application/json; ' \
                                                        'charset=utf-8'

                self.response.write(json.dumps({
                    'success': False,
                    'message': "Intermittent error. Please try again.",
                    'dev_message': (
                        "This error occurs when pegasus cannot find a "
                        "particular entity, the unique DatastoreConnection "
                        "entity. It occurs intermittently under normal "
                        "operations for unknown reasons. However, it may occur if "
                        "no one has yet created the entity in question in the "
                        "first place. If you think this may be the case, visit "
                        "/initialize_connection as an app admin."),
                }))

    def do_wrapper(self, *args, **kwargs):
        """Wrap all api calls in a try/catch so the server never breaks when
        the client hits an api URL."""
        try:
            if 'connection_attempts' in kwargs:
                del kwargs['connection_attempts']
            self.write_json(self.do(*args, **kwargs))
        except Exception as error:
            trace = traceback.format_exc()
            # We don't want to tell the public about our exception messages.
            # Just provide the exception type to the client, but log the full
            # details on the server.
            logging.error("{}\n{}".format(error, trace))
            response = {
                'success': False,
                'message': error.__class__.__name__,
            }
            if debug:
                response['message'] = "{}: {}".format(error.__class__.__name__, error)
                response['trace'] = trace
            self.write_json(response)

    def write_json(self, obj):
        r = self.response
        r.headers['Content-Type'] = 'application/json; charset=utf-8'
        r.write(json.dumps(obj))


class CreateHandler(ApiHandler):
    def do(self, kind):
        params = util.get_request_dictionary(self.request)
        entity = self.api.create(kind, params)
        data = entity.to_dict()

        # Special case for activity management: when teachers create a
        # classroom for the first time, activity entities need to be created
        # for them.
        if kind == 'classroom':
            teacher_id = params['user']
            is_test = params['is_test'] if 'is_test' in params else False
            activities = self.api.init_activities(
                'student', teacher_id, params['program'],
                cohort_id=params['cohort'], classroom_id=entity.id,
                is_test=is_test)

            # If these activities are being created FOR the teacher by an admin
            # or researcher, we need to do extra work to make sure those
            # activities are owned by the teacher.
            if self.get_current_user().id != teacher_id:
                teacher = self.internal_api.get_from_path('user', teacher_id)
                for a in activities:
                    self.api.associate('set_owner', teacher, a)

            # Include the created activities with the new classroom so the
            # client gets them immediately. We've had problems with eventual
            # consistency here.
            data['_student_activity_list'] = [a.to_dict() for a in activities]

        return {'success': True, 'data': data}


class BatchPutPdHandler(ApiHandler):
    def do(self):
        """Accepts several pd at once as JSON via POST.

        Args:
            pd_batch: List of dictionaries, each with a 'variable' and 'value'
                property.
            ...: All other properties expected of a pd (e.g. user, cohort,
                activity), which will get applied to all the elements of the
                pd_batch list to create a set of pd entities.
        Example:
            {
              "pd_batch": [
                {
                  "variable": "s2__toi_1",
                  "value": 1
                },
                {
                  "variable": "s2__toi_2",
                  "value": 1
                }
              ],
              "activity": "Activity_QD6FnPKYkRjrGfSr0wT7",
              "activity_ordinal": 2,
              "program": "Program_M4OQDVDcS0WjvAn8ujR5",
              "scope": "User_NISmPygw44gxopWrivjg",
              "is_test": false,
            }
        """
        params = util.get_request_dictionary(self.request)
        # We're good at re-trying pds when there's a transaction collision,
        # so demote this to a warning rather than an error, so we don't get
        # so many useless emails.
        try:
            pds = self.api.batch_put_pd(params)
        except db.TransactionFailedError:
            logging.warning("TransactionFailedError: {}".format(params))
            return {'success': False, 'message': "TransactionFailedError"}
        else:
            return {'success': True, 'data': [pd.to_dict() for pd in pds]}


class BatchPutUserHandler(ApiHandler):
    def do(self):
        """Put many users of different names but similar relationships.

        Args:
            user_names: List of dictionaries, each with a 'first_name' and
                'last_name' property.
            ...: All other properties expected of a user (e.g. user_type), which
                will get applied to all the elements of the user_names list.
        Example:
            {
              "user_names": [
                {
                  "first_name": "Deanna",
                  "last_name": "Troi"
                },
                {
                  "first_name": "Beverly",
                  "last_name": "Crusher"
                }
              ],
              "user_type": "student",
              "classroom": "Classroom_XYZ"
            }
        """
        params = util.get_request_dictionary(self.request)
        users = self.api.batch_put_user(params)
        return {'success': True, 'data': [user.to_dict() for user in users]}


class UpdateHandler(ApiHandler):
    """Data updates work like updating a dictionary, entities keys are assigned
    new values.

    PERTS supports two types of data updates:
    * One entity, the normal case.
    * An entity and all of its children recursively, the rare case. This was
      developed to allow us to switch teachers to a different cohort if they
      accidentally joined the wrong one to begin with. see: #185. This type
      has special arguments:
      - recurse_children (bool): initiates recusive update
      - preview (bool): don't update, just show WOULD be changed.
    """
    def do(self, kind, id=None):
        params = util.get_request_dictionary(self.request)
        if 'recurse_children' in params and params['recurse_children'] is True:
            # This flag just serves to forks the update request to
            # recursive_update(); toss it b/c it's not data, really.
            del params['recurse_children']

            # This flag causes recursive_update() to do nothing except return
            # the entity ids it WOULD change.
            if 'preview' in params:
                preview = params['preview'] is True
                del params['preview']
            else:
                preview = False

            entities_changed = self.api.recursive_update(
                kind, id, params, preview=preview)
            data = [e.to_dict() for e in entities_changed]
        else:
            entity = self.api.update(kind, id, params)
            data = entity.to_dict()
        return {'success': True, 'data': data}


class UpdateByIdHandler(ApiHandler):
    def do(self, id):
        kind = get_kind(id)
        params = util.get_request_dictionary(self.request)
        entity = self.api.update(kind, id, params)
        return {'success': True, 'data': entity.to_dict()}


class SeeHandler(ApiHandler):
    def do(self, kind):
        data = self.api.see(kind, util.get_request_dictionary(self.request))
        return {'success': True, 'data': data}


class GetHandler(ApiHandler):
    def do(self, kind):
        params = util.get_request_dictionary(self.request)
        ancestor = None
        # If an ancestor is specified, look it up by id and pass it in.
        if 'ancestor' in params:
            ancestor_kind = get_kind(params['ancestor'])
            ancestor_klass = kind_to_class(ancestor_kind)
            ancestor = ancestor_klass.get_by_id(params['ancestor'])
            del params['ancestor']
        results = self.api.get(kind, params, ancestor=ancestor)
        return {'success': True, 'data': [e.to_dict() for e in results]}


class SeeByIdsHandler(ApiHandler):
    def do(self):
        ids = util.get_request_dictionary(self.request)['ids']
        results = self.api.see_by_ids(ids)
        return {'success': True, 'data': results}


class GetByIdsHandler(ApiHandler):
    def do(self):
        ids = util.get_request_dictionary(self.request)['ids']
        results = self.api.get_by_ids(ids)
        return {'success': True, 'data': [e.to_dict() for e in results]}


class RosterHandler(ApiHandler):
    def do(self):
        # The URL should specify either assc_classroom_list or assc_cohort_list
        params = util.get_request_dictionary(self.request)

        results, from_memcache = self.api.get_roster(
            params.get('assc_cohort_list', None) or
            params.get('assc_classroom_list', None))
        return {'success': True, 'from_memcache': from_memcache,
                'data': results}


class ScheduleHandler(ApiHandler):
    def do(self):
        # The URL should specify assc_cohort_list.
        params = util.get_request_dictionary(self.request)

        results, from_memcache = self.api.get_schedule(
            params['assc_cohort_list'])
        return {'success': True, 'from_memcache': from_memcache,
                'data': results}


class UnassociateHandler(ApiHandler):
    """Action is either 'unassociate' or 'disown'."""
    def do(self, action, from_kind, from_id, to_kind, to_id):
        from_klass = kind_to_class(from_kind)
        to_klass = kind_to_class(to_kind)
        from_entity = from_klass.get_by_id(from_id)
        to_entity = to_klass.get_by_id(to_id)
        logging.info("handler action {}".format(action))
        from_entity = self.api.unassociate(action, from_entity, to_entity)
        return {'success': True, 'data': from_entity.to_dict()}


class AssociateHandler(ApiHandler):
    """Action is either 'associate' or 'set_owner'."""
    def do(self, action, from_kind, from_id, to_kind, to_id):
        from_klass = kind_to_class(from_kind)
        to_klass = kind_to_class(to_kind)
        from_entity = from_klass.get_by_id(from_id)
        to_entity = to_klass.get_by_id(to_id)
        from_entity = self.api.associate(action, from_entity, to_entity)

        # We'll want to return this at the end.
        data = from_entity.to_dict()

        # Special case for activity management: when teachers associate with a
        # cohort or classroom for the first time, activity entities need to be
        # created for them.

        init_activities = (
            from_kind == 'user' and from_entity.user_type == 'teacher' and (
                (to_kind == 'cohort' and action == 'associate') or
                (to_kind == 'classroom' and action == 'set_owner')
            )
        )
        if init_activities:
            # To simulate a fresh call, refresh the user in the Api object.
            # This only applies when a user is associating *themselves* with a
            # cohort or classroom. Without this refresh, the new associations
            # created just above won't be there and permissions to associate
            # the new activities will be denied.
            if (self.api.user.id == from_id):
                self.api = Api(from_entity)

            # If the classroom or cohort being associated to is a testing
            # entity, then these activities should also be.
            kwargs = {'is_test': to_entity.is_test}
            program_id = to_entity.assc_program_list[0]
            if to_kind == 'cohort':
                kwargs['cohort_id'] = to_entity.id
                user_type = 'teacher'
            if to_kind == 'classroom':
                kwargs['cohort_id'] = to_entity.assc_cohort_list[0]
                kwargs['classroom_id'] = to_entity.id
                user_type = 'student'
            teacher_id = from_entity.id
            activities = self.api.init_activities(
                user_type, teacher_id, program_id, **kwargs)

            # If these activities are being created FOR the teacher by an admin
            # or researcher, we need to do extra work to make sure those
            # activities are owned by the teacher.
            if self.get_current_user() != from_entity:
                for a in activities:
                    self.api.associate('set_owner', from_entity, a)

            # Include the created activities with the modified entity so the
            # client gets them immediately. This allows client views to update
            # immediately if necessary.
            data['_teacher_activity_list'] = [a.to_dict() for a in activities]

        return {'success': True, 'data': data}


class DeleteHandler(ApiHandler):
    """Sets entity.deleted = True for given entity AND ALL ITS CHILDREN."""
    def do(self, id):
        success = self.api.delete(id)
        return {'success': success}


class ArchiveHandler(ApiHandler):
    """Sets entity.is_archived = True for given entity AND ALL ITS CHILDREN."""
    def do(self, action, id):
        undo = action == 'unarchive'
        success = self.api.archive(id, undo)
        return {'success': success}


class IdentifyHandler(ApiHandler):
    """For identifying students who are participating."""
    def do(self):
        # Make sure only public users make this call.
        user = self.get_current_user()
        if user.user_type != 'public':
            # Warn the javascript on the page that
            # there's a problem so it can redirect.
            return {'success': True, 'data': 'logout_required'}

        params = util.get_request_dictionary(self.request)
        # if there's a javascript stand-in for the calendar, there will be an
        # extraneous parameter that's just for display; remove it
        if 'display_birth_date' in params:
            del params['display_birth_date']
        # The client supplies the classroom and cohort ids, but we want the
        # entities.
        params['classroom'] = Classroom.get_by_id(params['classroom'])
        params['cohort'] = Cohort.get_by_id(params['cohort'])
        # user may not be there, so check separately
        user_id = self.request.get('user')
        if user_id:
            # the user has selected this among partial matches as themselves
            # check the id; if it's valid, log them in
            User.get_by_id(user_id)  # an invalid id will raise errors
            self.session['user'] = user_id
            data = {'exact_match': user_id,
                    'partial_matches': [],
                    'new_user': False}
        else:
            # the user has provided identifying info, attempt to look them up
            # see url_handlers.BaseHandler.identify() for structure of the
            # data returned
            data = self.identify(**params)
        return {'success': True, 'data': data}


class DeleteEverythingHandler(ApiHandler):
    """Delete absolutely everything. Only allowed while in development."""
    def do(self):
        self.api.delete_everything()
        del self.session['user']
        del self.session['impersonated_user']
        return {'success': True}


class PreviewReminders(ApiHandler):
    """ see core@reminders for details. """
    def do(self, abbreviation, user_type):
        r = self.api.get('program', {'abbreviation': abbreviation})
        if len(r) is not 1:
            raise Exception("Program {} not found.".format(abbreviation))
        program = r[0]
        data = self.api.preview_reminders(program, user_type)
        return {'success': True, 'data': data}


class ShowReminders(ApiHandler):
    """ see api@send_reminders for details. """
    def do(self):
        date = self.request.get('date')
        data = self.api.show_reminders(date)
        return {'success': True, 'data': data}


class SearchHandler(ApiHandler):
    """See core@indexer for details."""
    def do(self, query):
        start = self.request.get('start')
        end = self.request.get('end')

        if start and end:
            data = self.api.search(query, int(start), int(end))
        else:
            data = self.api.search(query)

        return {'success': True, 'data': data}


class StratifyHandler(ApiHandler):
    """Assign the user with the provided profile to a condition."""
    def do(self):
        p = util.get_request_dictionary(self.request)
        condition = self.api.stratify(p['program'], p['name'],
                                      p['proportions'], p['attributes'])
        return {'success': True, 'data': condition}


class StratifyJSONPHandler(ApiHandler):
    """Assign and save to pd a condition across domains via JSONP."""
    def do_wrapper(self, *args, **kwargs):
        params = {}
        try:
            if 'connection_attempts' in kwargs:
                del kwargs['connection_attempts']
            params = util.get_request_dictionary(self.request)
            # When using jQuery (as we do), params also includes the key '_',
            # which is a timestamp jQuery uses to prevent the browser from
            # caching this resource.
            condition = self.api.stratify(
                params['program'], params['name'], params['proportions'],
                params['attributes'])

            user = User.get_by_id(params['user'])
            pd = Api(user).create('pd', {
                'program': params['program'],
                'variable': 'condition',
                'value': condition,
                'scope_kind': 'user',
                'scope': params['user'],
            })
        except Exception as error:
            trace = traceback.format_exc()
            logging.error("Error while stratifying via JSONP: {}\n{}"
                          .format(error, trace))
            condition = '__ERROR__'

        r = self.response
        r.headers['Content-Type'] = 'application/javascript; charset=utf-8'
        jsonp = '{}("{}");'.format(params.get('callback', ''), condition)
        logging.info("Responding with: {}".format(jsonp))
        r.write(jsonp)


class LoginHandler(ApiHandler):
    """Users are sent to this page if they can't be automatically logged in via
    /api/authenticate. Provides choices for three kinds of authentication:
    google, facebook, and username/password."""
    def do(self):
        auth_type = self.request.get('auth_type')
        username = self.request.get('username') or None  # for direct auth
        password = self.request.get('password') or None  # for direct auth

        if auth_type not in config.allowed_auth_types:
            raise Exception("Bad auth_type: {}.".format(auth_type))
        auth_response = self.authenticate(auth_type, username=username,
                                          password=password)
        # interpret the results of authentication
        if isinstance(auth_response, User):
            # simple case, user was returned, send them on their way
            data = 'signed_in'
        elif auth_response is False:
            # all the credentials were present, but they weren't valid
            # does this email exist for some OTHER auth type?
            matches = self.internal_api.get('user', {'login_email': username})
            if len(matches) is 1:
                # The is the user object we think the human user is trying to
                # log in with.
                intended_user = matches[0]
                if auth_type == intended_user.auth_type():
                    # The user is using the right auth type, and their email
                    # checks out; the password is just wrong.
                    data = 'invalid_credentials'
                else:
                    # The user exists, but with a different auth type than what
                    # they're using. Advise them to try something else.
                    data = 'wrong_auth_type ' + intended_user.auth_type()
            else:
                data = 'invalid_credentials'
        elif auth_response is None:
            # some credentials are missing
            if auth_type == 'google':
                raise Exception("No google account found.")
            elif auth_type == 'direct':
                raise Exception("Missing username and password.")
            elif auth_type == 'facebook':
                raise Exception("Missing facebook cookie.")
        return {'success': True, 'data': data}


class RegisterHandler(ApiHandler):
    """Called from the third form on the login page, "I want to sign up", i.e.
    for direct auth_type users. Third-party auth_type users are handled in
    page_handlers.LoginHandler"""
    def do(self):
        auth_type = self.request.get('auth_type')
        username = self.request.get('username') or None
        password = self.request.get('password') or None
        user, user_is_new = self.register(auth_type, username, password)
        if user is False:
            data = 'wrong_auth_type'
        else:
            data = {'user': user.to_dict(), 'user_is_new': user_is_new}
        return {'success': True, 'data': data}


class ChangePasswordHandler(ApiHandler):
    """For logged in users to change their password; requires them knowing
    they're existing password."""
    def do(self):
        new_password = self.request.get('new_password') or None
        auth_response = self.authenticate(
            auth_type='direct', username=self.request.get('username'),
            password=self.request.get('current_password'))
        if auth_response is False or auth_response is None:
            return {'success': True, 'data': 'invalid_credentials'}
        user = auth_response
        user.hashed_password = hash_password(new_password)
        user.put()

        # Alert the user that their password has been changed.
        email = Email.create(
            to_address=user.login_email,
            reply_to=config.from_yosemite_email_address,
            from_address=config.from_yosemite_email_address,
            subject=config.change_password_subject,
            body=config.change_password_body)

        logging.info('api_handlers.ChangePasswordHandler')
        logging.info('sending an email to: {}'.format(user.login_email))

        Email.send(email)
        
        return {'success': True, 'data': 'changed'}


class ForgotPasswordHandler(ApiHandler):
    """For public users to send themselves reset-password emails."""
    def do(self):
        # ensure this email address belongs to a known user
        email = self.request.get('email').lower()

        # Look up users by auth_id because that's how they log in;
        result = self.internal_api.get('user', {'auth_id': 'direct_' + email})

        if len(result) is 1 and result[0].is_test is False:
            # then this email address is valid; proceed with send
            user = result[0]

            # deactivate any existing reset tokens
            self.api.clear_reset_password_tokens(user.id)

            # create a new token for them
            new_token = ResetPasswordToken.create(user=user.id)
            new_token.put()

            # and email them about it
            link = '/reset_password/' + new_token.token()
            email = Email.create(
                to_address=email,
                reply_to=config.from_yosemite_email_address,
                from_address=config.from_yosemite_email_address,
                subject=config.forgot_password_subject,
                body=config.forgot_password_body.format(link))

            logging.info('ForgotPasswordHandler sending an email to: {}'
                         .format(email))

            Email.send(email)
            return {'success': True, 'data': 'sent'}
        else:
            logging.info('ForgotPasswordHandler invalid email: {}'
                         .format(email))
            return {'success': True, 'data': 'not_sent'}


class ResetPasswordHandler(ApiHandler):
    """Uses the tokens in reset password email links to change passwords."""
    def do(self):
        token = self.request.get('token')
        new_password = self.request.get('new_password')

        # Check the token
        user = self.api.check_reset_password_token(token)

        if user is None:
            return {'success': True, 'data': 'invalid_token'}

        # Change the user's password.
        user.hashed_password = hash_password(new_password)
        user.put()

        # Clear existing tokens.
        self.api.clear_reset_password_tokens(user.id)

        # Alert the user that their password has been changed.
        email = Email.create(
            to_address=user.login_email,
            reply_to=config.from_yosemite_email_address,
            from_address=config.from_yosemite_email_address,
            subject=config.change_password_subject,
            body=config.change_password_body)
        
        logging.info('api_handlers.ResetPasswordHandler')
        logging.info('sending an email to: {}'.format(user.login_email))
        
        Email.send(email)

        return {'success': True, 'data': 'changed'}


class ProgramOutlineHandler(ApiHandler):
    def do(self, program_id):
        data = self.api.program_outline(program_id)
        return {'success': True, 'data': data}


class LoggingHandler(ApiHandler):
    def do(self, severity):
        # Provide a secret back door so compute engine instances can easily
        # register errors with our app.
        secret = 'FrreHPFA0xSp2yutktBx'
        # Otherwise restrict logging to signed-in users.
        user = self.get_current_user()

        if user.user_type != 'public' or self.request.get('_secret') == secret:
            logger = getattr(logging, severity)
            # Make an entry about the user who sent the log.
            logger('/api/log user: {} {} {}'.format(
                user.user_type, user.id, user.login_email))
            # Make entries out of any extra request data sent in.
            for arg in self.request.arguments():
                # ignore the secret parameter
                if arg == '_secret':
                    continue
                # process lists intelligently
                if arg[-2:] == '[]':
                    value = self.request.get_all(arg)
                # basic key-value
                else:
                    value = self.request.get(arg)
                # value might be unicode, so the string into which we
                # interpolate must be unicode.
                logger(u'/api/log {}: {}'.format(arg, value))
        return {'success': True}


class ActivitySyncHandler(ApiHandler):
    def do(self, program_id):
        message_dict = self.api.sync_program_activities(program_id)
        return {
            'success': True,
            'message': 'Teacher activities: {}\nStudent activities: {}'.format(
                message_dict['teacher'], message_dict['student'])
        }


class GenerateTestPdHandler(ApiHandler):
    def do(self):
        num_entities = int(self.request.get('num_entities'))
        for x in range(num_entities):
            user = self.get_current_user()
            rand = ''.join(random.choice(string.digits) for x in range(10))
            kwargs = {
                'program': 'test_program',
                'activity_ordinal': 1,
                'activity': 'test_activity',
                'cohort': 'test_cohort',
                'classroom': 'test_classroom',
                'user': user.id,
                'scope': 'user',
                'variable': rand,
                'value': rand,
            }
            Pd.create(user, **kwargs)
        return {'success': True}


class IsLoggedInHandler(ApiHandler):
    """Tells the browser if the user is currently logged in."""
    def do(self):
        return {
            'success': True,
            'data': self.get_current_user().user_type != 'public',
        }


class SystematicUpdateHandler(ApiHandler):
    """A way to gradually update a large set of entities in the datastore.

    Fetches sets of entities by their created time, and runs arbitrary code on
    them. Keeps track of its place with a named Timestamp entity.

    Todo:
    - figure out if this is a good place, organizationally, to put this code
    - use andrew's strip_names() function in the update method
    - actually test it with very pessimistic conditions
        - arbitrary timeouts
        - inconsistent reads
    - chat w/ Ben re: interaction of preview and start_time
    """
    def do(self, update_name):
        """The update name defines what kind of update to run. This will be
        used to:
        - Create a timestamp to track progress.
        - Query for entities based on configuration in
          config.systematic_update_settings, which must be defined.
        - Execute method of this class by the same name on each entity returned
          from the query. It must be defined. The method should take an entity
          and return and return either None (if the entity should not be
          updated) or a modified entity.

        Accepts parameters in request string:
        fetch_size (int) - how many entities to process at once
        start_time (str) - what "created" time to start searching for entities;
                           this overrides the normal "systematic" behavior
        preview (bool) - report on results without actually updating
        """
        from google.appengine.ext import db
        from datetime import datetime

        params = util.get_request_dictionary(self.request)

        # Check request string and apply defaults where necessary
        if 'fetch_size' in params:
            fetch_size = params['fetch_size']
        else:
            fetch_size = 100
        if 'start_time' in params:
            start_time = params['start_time']
        else:
            # Look up / create a timestamp to track progress
            ts = Timestamp.get_or_insert(update_name)
            start_time = ts.timestamp
        if 'preview' in params:
            preview = params['preview']
        else:
            preivew = False

        conf = config.systematic_update_settings[update_name]

        # Query for entities
        klass = kind_to_class(conf['kind'])
        query = klass.all()
        query.filter('created >', start_time)
        query.order('created')
        entity_list = query.fetch(fetch_size)

        before_snapshot = [e.to_dict() for e in entity_list]
            
        # Look up related method
        method = getattr(self, update_name)
        if not util.is_function(method):
            raise Exception("Invalid update name: method isn't callable.")

        # Execute the method on each entity
        modified_entities = []
        for entity in entity_list:
            # Check if this systematic update has been performed before
            if update_name in entity.systematic_updates:
                raise Exception(
                    "{} has already been performed on entity {}."
                    .format(update_name, entity.id))
            else:
                entity.systematic_updates.append(update_name)
            updated_entity = method(entity)
            if updated_entity is not None:
                modified_entities.append(updated_entity)

        # The entity variable is still set to the last one of the list;
        # use it to save our spot for next time.
        end_time = entity.created

        after_snapshot = [e.to_dict() for e in modified_entities]

        if not preview:
            db.put(modified_entities)

        if 'start_time' not in params:
            # Save progress
            ts.timestamp = end_time
            ts.put()

        return {'success': True, 'data': {
            'entities_queried': len(entity_list),
            'entities_modified': len(modified_entities),
            'start_time': start_time,
            'end_time': end_time,
            'entities before update': before_snapshot,
            'entities after update': after_snapshot,
        }}

    def lowercase_login(self, user_entity):
        """Method to execute on each user in the datastore.

        Returns None if user doesn't need updating. Otherwise returns modified
        user.
        """
        if user.user_type == 'student':
            # @todo: use andrew's strip_names() function here, when it
            # becomes available
            # user.first_name = strip_names(user.first_name)
            # user.last_name = strip_names(user.last_name)
            pass
        else:
            user.auth_id = user.auth_id.lower()
            user.login_email = user.login_email.lower()

        return user


class ImportQualtricsLinksHandler(ApiHandler):

    def do(self, session_ordinal, filename):
        # There are only sessions 1 and 2 for Yosemite.
        # Fail gracefully if outside that scope.
        if session_ordinal is 1 or 2:
            links = self.api.import_links(filename, int(session_ordinal))
        else:
            links = 'No session corresponding to {}. Try 1 or 2.'.format(session_ordinal)
        return {
            'success': True,
            'links': links,
        }


class CheckClientTestHandler(ApiHandler):
    """Does server-side checks aren't normally allowed for public users."""
    def do(self):
        params = util.get_request_dictionary(self.request)
        cross_site_result = self.cross_site_test(**params['cross_site_test'])
        return {'success': True, 'data': {
            'cross_site_test': cross_site_result,
        }}

    def cross_site_test(self, code, user_id):
        """Checks whether Qualtrics has successfully recorded a pd."""
        user = User.get_by_id(user_id)
        logging.info("Test user: {}".format(user))
        if not user:
            return False

        pd_list = self.internal_api.get('pd', {'variable': 'cross_site_test'},
                                        ancestor=user)
        logging.info("Found pd: {}".format(pd_list))
        if len(pd_list) != 1:
            return False

        pd = pd_list[0]
        logging.info("Matching pd code. Looking for {}, found {}."
                     .format(code, pd.value))

        return pd.value == code


class RecordClientTestHandler(ApiHandler):
    """Record the results of javascript unit tests.

    Logs an error if there are failed tests.
    """
    def do(self):
        params = util.get_request_dictionary(self.request)
        if len(params['failed_tests']) is 0:
            logging.info(params)
        else:
            # There were failed tests, log an error (and generate an email).
            logging.error(params)
        # Don't freak out the user, either way.
        return {'success': True}


class GetQualtricsLinkHandler(ApiHandler):
    """Pull a unique URL from our collection of QualtricsLink entities."""
    def do(self, session_ordinal):
        return {'success': True,
                'data': QualtricsLink.get_link(int(session_ordinal))}


class CrossSiteGifHandler(BaseHandler):
    """Provides a way for PERTS javascript on other domains to access api.

    The general format is
    [normal api url]/cross_site.gif?[normal request parameters]

    Example:
    /api/put/pd/cross_site.gif?variable=s1__progress&?value=100&...
    /api/see/user/cross_site.gif?user_type=teacher  # not implemented

    Example as a qualtrics img tag:
    <img src="//www.studentspaths.org/api/put/pd/cross_site.gif?variable=s1__progress&value=25">

    Because this is a publicly-accessible URL, we need to build safety checks
    into each different kind of call. If we wind up using this a lot, we should
    find a more general authentication solution. For now, it just does put/pd,
    nothing else.
    """
    def do_wrapper(self, api_path):
        # Try to handle the request data, or log an error. Normally, inheriting
        # from ApiHandler would take care of this, but this doesn't return JSON
        # so we have to duplicate some code.
        try:
            params = util.get_request_dictionary(self.request)
            logging.info(params)

            if api_path == 'put/pd':
                self.put_pd(params)
            else:
                raise Exception(
                    "This cross-site api has not been implemented: {}."
                    .format('/api/' + api_path))

        except Exception as error:
            trace = traceback.format_exc()
            logging.error("{}\n{}".format(error, trace))

        # No matter what happens, return the gif.
        self.response.headers['Content-Type'] = 'image/gif'
        # A 1x1 transparent pixel in a base64 encoded string. See
        # http://stackoverflow.com/questions/2933251/code-golf-1x1-black-pixel
        gif_data = 'R0lGODlhAQABAAAAACwAAAAAAQABAAACAkwBADs='.decode('base64')
        self.response.out.write(gif_data)

    def put_pd(self, params):
        """Do security checks on potentially malicious pd params, then put."""
        # Be careful b/c this data is coming from an external site.

        # Also strategize about what kind of errors to log/raise. It's very
        # common, for instance, for calls to come in with the right fields but
        # blank data b/c someone is testing qualtrics and we can safely ignore
        # that. But non-blank data that's malformed might signal there's
        # something wrong we need to solve.

        # This specific set of data is expected from opening any page in
        # Qualtrics without having gone through identify first. Do nothing.
        blank_testing_params = {'program': '', 'scope': '', 'variable': '',
                                'value': ''}
        is_preview = (
            params['program'] == '' and params['scope'] == '' and
            params['value'].isdigit() and 'activity_ordinal' not in params)

        if params == blank_testing_params or is_preview:
            logging.info("Interpreted call as Qualtrics testing. Ignoring.")
            return

        # In non-testing calls, Qualtrics should always attempt to send back
        # these parameters. If we don't have them, or if they're blank, then
        # the qualtrics javascript is wrong, and that's bad.
        expected_keys = set(['program', 'scope', 'variable', 'value',
                             'activity_ordinal'])
        keys_are_missing = set(params.keys()) != expected_keys
        values_are_blank = any([v == '' for v in params.values()])
        if keys_are_missing or values_are_blank:
            raise Exception("Parameters missing: {}".format(params))

        # If we have data, we expected it to make sense. Look stuff up and
        # check coherence.
        scope_results = self.internal_api.get_by_ids([params['scope']])
        if len(scope_results) is 0:
            raise Exception('Scope entity not found: {}.'.format(params['scope']))
        scope_entity = scope_results[0]

        if not isinstance(scope_entity, User):
            raise Exception(
                "CrossSiteGifHandler can only accept user-scope pds. "
                "Received scope entity: {}.".format(scope_entity))

        user = scope_entity
        if user.user_type == 'public':
            raise Exception("User type public cannot put pd cross site.")

        # Create an api for the validated user, and record the pd.
        api = Api(user)
        pd = api.create('pd', params)

        logging.info("Created pd {}".format(pd.to_dict()))


webapp2_config = {
    'webapp2_extras.sessions': {
        # cam. I think this is related to cookie security. See
        # http://webapp-improved.appspot.com/api/webapp2_extras/sessions.html
        'secret_key': '8YcOZYHVrVCYIx972K3MGhe9RKlR7DOiPX2K8bB8',
    },
}


app = webapp2.WSGIApplication([
    ('/api/(.*)/cross_site.gif', CrossSiteGifHandler),
    ('/api/see/(.*)', SeeHandler),
    ('/api/get/(.*)', GetHandler),
    ('/api/see_by_ids/?', SeeByIdsHandler),
    ('/api/get_by_ids/?', GetByIdsHandler),
    ('/api/get_roster/?', RosterHandler),
    ('/api/get_schedule/?', ScheduleHandler),
    ('/api/put/([^/]*)/?', CreateHandler),
    ('/api/put/(.*?)/(.*)', UpdateHandler),
    ('/api/put_by_id/(.*)', UpdateByIdHandler),
    ('/api/batch_put_pd', BatchPutPdHandler),
    ('/api/batch_put_user', BatchPutUserHandler),
    ('/api/(associate|set_owner)/(.*?)/(.*?)/(.*?)/(.*)', AssociateHandler),
    ('/api/(unassociate|disown)/(.*?)/(.*?)/(.*?)/(.*)', UnassociateHandler),
    ('/api/delete_everything', DeleteEverythingHandler),
    ('/api/delete/(.*)', DeleteHandler),
    ('/api/(archive|unarchive)/(.*)', ArchiveHandler),
    ('/api/identify/?', IdentifyHandler),
    ('/api/preview_reminders/([^\/]*)/([^\/]*)/?', PreviewReminders),
    ('/api/show_reminders/?', ShowReminders),
    ('/api/search/(.*)/?', SearchHandler),
    ('/api/stratify/?', StratifyHandler),
    ('/api/stratify/jsonp/?', StratifyJSONPHandler),
    ('/api/login/?', LoginHandler),
    ('/api/register/?', RegisterHandler),
    ('/api/change_password/?', ChangePasswordHandler),
    ('/api/forgot_password/?', ForgotPasswordHandler),
    ('/api/reset_password/?', ResetPasswordHandler),
    ('/api/program_outline/(.*)', ProgramOutlineHandler),
    ('/api/log/(.*)', LoggingHandler),
    ('/api/sync_program_activities/(.*)', ActivitySyncHandler),
    ('/api/generate_test_pd/?', GenerateTestPdHandler),
    ('/api/is_logged_in/?', IsLoggedInHandler),
    ('/api/import_qualtrics/(.*)/(.*)', ImportQualtricsLinksHandler),
    ('/api/get_qualtrics_link/(.*)', GetQualtricsLinkHandler),
    ('/api/check_client_test/?', CheckClientTestHandler),
    ('/api/record_client_test/?', RecordClientTestHandler),
    # disabled until the systematic updater is ready
    # ('/api/systematic_update/(.*)', SystematicUpdateHandler),
], config=webapp2_config, debug=debug)
