"""Serve html documents to users."""

from google.appengine.api import users as app_engine_users
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib import units
import gae_mini_profiler
import jinja2  # templating engine
import json
import logging
import os
import textwrap  # PDF generation
import time
import urllib
import webapp2

import api
from core import *
import programs
from url_handlers import *
import util

debug = util.is_development()

# These pages are served without any awareness of user session or the
# datastore. They do NOT check for a datastore connection before running.
# They all use the HomePageHandler.
# These strings are included as parts of a regex for URL matching, so some
# globbing is supported.
public_home_pages = [
    'about',
    'challenge',
    'contact',
    'ctc',
    'participation',
    'PERTS',
    'programs',
    'publicity',
    'resources',
    'results',
    'team',
    'orientation/.*',
]


class ViewHandler(BaseHandler):
    """Superclass for page-generating handlers."""

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
                # Since this is a view, it's important to not display weird
                # devvy text to the user. The least harmful thing I can come
                # up with is showing them the home page.
                jinja_environment = jinja2.Environment(
                    autoescape=True,
                    loader=jinja2.FileSystemLoader('templates'),
                )
                self.response.write(
                    jinja_environment.get_template('home.html').render())

    def do_wrapper(self, *args, **kwargs):
        try:
            output = self.do(*args, **kwargs)
        except Exception as error:
            logging.error("{}".format(error))
            if debug:
                import traceback
                self.response.write('<pre>{}</pre>'.format(
                    traceback.format_exc()))
            else:
                self.response.write("We are having technical difficulties.")
            return
        if output is not None:
            # do methods might not put out rendering info
            # todo: they really should always do that. make sure they do then
            # remove this check
            template = output[0]
            params = output[1]
            if len(output) >= 3:
                template_directory = output[2]
            else:
                template_directory = 'templates'
            jinja_environment = jinja2.Environment(
                autoescape=True,
                loader=jinja2.FileSystemLoader(template_directory),
                # # These change jinja's template syntax
                # variable_start_string='[[',
                # variable_end_string=']]',
                # block_start_string='[%',
                # block_end_string='%]'
            )
            jinja_environment.globals['gae_mini_profiler_includes'] = (
                gae_mini_profiler.templatetags.profiler_includes)
            # Jinja environment filters:
            jinja_environment.filters['tojson'] = json.dumps
            # default parameters that all views get
            user = self.get_current_user()
            normal_user = self.get_current_user(method='normal')
            params['user'] = user
            params['normal_user'] = normal_user
            params['config'] = config
            params['currently_impersonating'] = user != normal_user
            params['connected_to_facebook'] = bool(self.facebook_cookie())
            if params['connected_to_facebook']:
                params['facebook_user'] = self.get_third_party_auth('facebook')
            else:
                params['facebook_user'] = None
            params['connected_to_google'] = app_engine_users.get_current_user()
            params['google_user'] = app_engine_users.get_current_user()
            params['google_admin'] = app_engine_users.is_current_user_admin()
            params['current_url'] = self.request.path + '?' + self.request.query_string
            params['is_localhost'] = util.is_localhost()
            if debug:
                params['session'] = json.dumps(self.session)
            # render
            html_str = jinja_environment.get_template(template).render(params)
            self.response.write(html_str)

    def http_not_found(self):
        """Return a 404.

        Example use:
        ```
        class FooHandler(ViewHandler):
            def do(self):
                return self.http_not_found()
        ```
        """
        # Trigger the actual HTTP 404 code
        self.error(404)
        # Describe a template to display, so we don't get the ugly browser
        # default.
        return '404.html', {}

    def access_restricted(self, disallowed_types):
        user = self.get_current_user()
        should_redirect = False
        if user.user_type == 'public':
            # empty string here means: encode forward slashes
            encoded_url = urllib.quote(self.request.url, '')
            self.redirect('/login?redirect=' + encoded_url)
            should_redirect = True
        elif user.user_type in disallowed_types:
            self.redirect('/404')
            should_redirect = True
        return should_redirect


class HomePageHandler(ViewHandler):
    """Very simple handler for static, public-facing pages."""
    def get(self, template_name):
        """Overrides the get method of url_handlers.BaseHandler, eliminating
        the datastore connection check and session management."""
        template = template_name + '.html'
        if not os.path.isfile('templates/' + template):
            template, params = self.http_not_found()
        jinja_environment = jinja2.Environment(
            autoescape=True,
            loader=jinja2.FileSystemLoader('templates'))
        html_str = jinja_environment.get_template(template).render()
        self.response.write(html_str)


class GenericHandler(ViewHandler):
    """Generic handler for simple pages that don't require a custom handler but
    DO require session management provided by BaseHandler."""
    def do(self, template_name):
        template = template_name + ".html"
        if os.path.isfile('templates/' + template):
            return template, {}
        else:
            return self.http_not_found()


class HomeHandler(ViewHandler):
    """The pegasus "home" page."""
    def do(self):
        user = self.get_current_user()

        # Since multiple different students may use the same computer, we want
        # to err on the side of signing them out too often, ensuring two
        # different people don't wind up using the same account.
        if user.user_type == 'student':
            self.redirect('/logout')

        return 'home.html', {}


class GodHandler(ViewHandler):
    """Who presumes to handle God?"""
    def do(self):
        # We want to avoid populating the same datastore twice. So attempt to
        # detect if the populate script has already been done.
        programs_exist = Program.all().count() > 0
        if self.access_restricted(
            ['researcher', 'school_admin', 'teacher', 'student', 'public']):
            return

        return 'god.html', {'programs_exist': programs_exist}


class TeacherHandler(ViewHandler):
    def do(self):
        if self.access_restricted(['student', 'public']): return

        # Originally did fancy logic to determine which program the teacher
        # should go to. In Yosemite, they just go to SP.
        self.redirect('/p/SP/teacher_panel')


class TestHandler(ViewHandler):
    def do(self):
        user = self.get_current_user()
        if user.user_type not in ['researcher', 'god']:
            self.response.write('You are not allowed to view this page.')
            return
        #   pass in CP1 for automated testing, unless it does not exist
        try:
            program = self.api.get('program', {'abbreviation': 'CP2'})[0]
        except:
            program = {'id': 0}
        return 'test.html', {
            'program': program,
        }


class BetaHandler(ViewHandler):
    def do(self):
        user = self.get_current_user()
        # This page contains the cross-site test, and so needs to create a
        # test user in the context of some program. Provide the id of the
        # test program for this purpose.
        programs = self.internal_api.get('program', {'abbreviation': 'TP1'})
        if len(programs) is 1:
            sp = programs[0]
        else:
            raise Exception("Problem loading TP1 program on help page.")
        return 'beta.html', {
            'user': user,
            'program_id': sp.id,
        }


class IdentifyHandler(ViewHandler):
    """Where participants enter. Different from authentication."""
    def do(self):
        user = self.get_current_user()
        page_action = self.request.get('page_action')
        if page_action == 'go_to_program':
            session_ordinal = self.request.get('session_ordinal')
            cohort_id = self.request.get('cohort')
            classroom_id = self.request.get('classroom')
            classroom = self.internal_api.get_from_path('classroom', classroom_id)
            program_id = classroom.assc_program_list[0]
            program = self.internal_api.get_from_path('program', program_id)
            request_params = {'cohort': cohort_id, 'classroom': classroom_id,
                              'session_ordinal': session_ordinal}
            # redirect the user to this activity within the program app
            url = '/p/{}/student?{}'.format(program.abbreviation,
                                            urllib.urlencode(request_params))
            self.redirect(url)
            return
        elif user.user_type != 'public':
            # Users arriving here are students who want to sign in. Don't let
            # existing sessions get in the way. Boot the current user.
            self.redirect('/logout?redirect=/go')
            return
        return 'identify.html', {
            'show_nav_bar': False,
            'show_loading_mask': True,
            'show_footer': False
        }


class RegistrationSurveyHandler(ViewHandler):
    """Once a teacher (or higher) has registered through one method or another,
    we need some basic information from them."""
    def do(self):
        if self.access_restricted(['student', 'public']): return

        user = self.get_current_user()

        # If they've already done it, don't make them do it again.
        if user.registration_complete:
            self.response.write("You've already completed registration.")
            return

        # Display a notice to users immediately after registering that they
        # have been sent an email. This notice is triggered by a request
        # variable b/c users may arrive at this survey again later and it
        # wouldn't make sense to show this to them at that later time.
        registration_email_sent = self.request.get(
            'registration_email_sent') == 'true'

        program_id = self.request.get('program')
        program = None
        if program_id:
            # Associate them with the program they've arrived with
            program = self.internal_api.get_from_path('program', program_id)
            self.internal_api.associate('associate', user, program)
        else:
            # Otherwise, attempt to look up their program
            if len(user.assc_program_list) > 0:
                program_id = user.assc_program_list[0]
            # if we still can't figure it out, the url is invalid
            else:
                return self.http_not_found()
        if not program:
            program = self.internal_api.get_from_path('program', program_id)

        return 'registration_survey.html', {
            'cohorts': self.api.see('cohort', {}),
            'program_id': program_id,
            'program': program,
            'registration_email_sent': registration_email_sent,
        }


class LoginHandler(ViewHandler):
    """Combination login and registration page. Google authentication will do
    either one, depending on whether your user already exists."""
    def do(self, program_abbreviation):
        user = self.get_current_user()

        # initialize variables
        registration_requested = self.request.get('registration_requested')
        redirect = str(self.request.get('redirect'))
        login_url = '/login'
        success_message = None
        error_message = None
        program_id = None
        program_name = None
        show_registration = False
        show_google_login = True

        # if a program was specified, look it up and adjust future redirects
        if program_abbreviation:
            program_abbreviation = program_abbreviation.upper()  # force upper case
            login_url += '/' + program_abbreviation
            # User has arrived via a program-specific link. Look up the program
            # to get its id (for association) and name (for a welcome message).
            results = self.internal_api.see(
                'program', {'abbreviation': program_abbreviation})
            if len(results) is 1:
                program = results[0]
                program_id = program['id']
                program_name = program['name']
                show_registration = True

        # Set up how the user will COME BACK from google login, which will be
        # used if they click the google login button.
        google_redirect = '{}?registration_requested=google'.format(login_url)
        if redirect:
            google_redirect += '&redirect={}'.format(redirect)
        if program_id:
            google_redirect += '&program={}'.format(program_id)
        google_login_url = app_engine_users.create_login_url(google_redirect)

        if registration_requested:
            # They're signed in with google or facebok, allow registration IF
            # they've arrive with a program id. If they're a new user AND
            # there's no program id, display a failure message.
            auth_response = self.authenticate(auth_type=registration_requested)
            if auth_response is None:
                error_message = 'Error during sign in. Please try again.'
                redirect = None
            elif auth_response is False and program_id is None:
                error_message = 'Unable to register.<br>Please use the registration link provided by your school.'
                redirect = None
            else:
                # OK to register and/or sign in; register() does both
                user, user_is_new = self.register(
                    auth_type=registration_requested)
                if user is False:
                    error_message = 'You already have a PERTS account with that email address.'
                    redirect = None
                else:
                    if user.user_type in ['teacher', 'school_admin'] and not user.registration_complete:
                        # Special case: force certain users to take additional
                        # registration steps. The registration_email_sent flag
                        # displays a confirmation that a registration email was
                        # sent.
                        redirect = '/registration_survey?'
                        if user_is_new:
                            redirect += 'registration_email_sent=true&'
                        if program_id:
                            redirect += 'program={}&'.format(program_id)

        # Any signed in user with a home page arriving at login should be
        # redirected to their home page.
        if (user is not False and user.user_type != 'public' and
            user.user_type in config.user_home_page):
            if not redirect:
                redirect = config.user_home_page[user.user_type]
            # else leave redirect set per the URL
            self.redirect(redirect)
            return

        # If user has just finished a password reset, show them a message.
        if self.request.get('password_reset_successful') == 'true':
            success_message = "Your password has been reset. Please use it to log in."
            show_google_login = False

        return 'login.html', {
            'show_registration': show_registration,
            'program_id': program_id,
            'program_name': program_name,
            'facebook_app_id': config.FACEBOOK_APP_ID,
            'google_login_url': google_login_url,
            'error_message': error_message,
            'success_message': success_message,
            'show_google_login': show_google_login,
        }


class LogoutHandler(ViewHandler):
    """Clears the user's session, closes connections to google, facebook."""
    def do(self):
        # The name of the login cookie is defined in
        # url_handlers.BaseHandler.session()
        self.response.delete_cookie('perts_login')
        # This cookie is created when logging in with a google account in
        # production.
        self.response.delete_cookie('SACSID')
        # This cookie is created when logging in with a google account with
        # the app engine sdk (on localhost).
        self.response.delete_cookie('dev_appserver_login')
        self._user = None
        self._impersonated_user = None
        # ultimately the user will wind up here
        redirect = self.request.get('redirect') or '/'
        self.redirect(redirect)


class DashboardHandler(ViewHandler):
    """Shows many different views of data related to the user."""
    def do(self):
        if self.access_restricted(['teacher', 'student', 'public']): return
        return 'dashboard.html', {}


class ProgramHandler(ViewHandler):
    """Handles page requests for program apps."""
    def do(self, program_abbreviation, template_name):
        if self.access_restricted(['public']):
            return

        # We'll display a warning to the user if this is not true.
        valid_url = True

        # We'll want the program entity, for things like showing the program's
        # name.
        program = self.api.get('program',
                               {'abbreviation': program_abbreviation})[0]

        # The cohort is also a critical part of the app, otherwise we can't
        # record data.
        cohort = None
        cohort_id = self.request.get('cohort')
        # Validate the id. It should exist and match the program.
        if cohort_id == '':
            valid_url = False
        else:
            cohort = Cohort.get_by_id(cohort_id)
            if cohort is None:
                valid_url = False
            else:
                if program.id not in cohort.assc_program_list:
                    valid_url = False

        # The classroom is critical IF the user is a student.
        classroom = None
        classroom_id = self.request.get('classroom')
        if template_name == 'student' and cohort is not None:
            # Validate.
            if classroom_id == '':
                valid_url = False
            else:
                classroom = Classroom.get_by_id(classroom_id)
                if classroom is None:
                    valid_url = False
                else:
                    if cohort.id not in classroom.assc_cohort_list:
                        valid_url = False

        if not valid_url:
            return self.http_not_found()

        # get program app config
        if template_name in ['student', 'teacher']:
            app_config = Program.get_app_configuration(program_abbreviation,
                                                       template_name)
        else:
            app_config = {}

        template_path = 'programs/{}/{}.html'.format(
            program_abbreviation, template_name)
        template_directory = ''  # i.e. from the root of the app

        params = {
            'show_nav_bar': app_config.get('show_nav_bar', True),
            'show_main_nav': False,
            'show_footer': False,
            'program_name': program.name,
            'program_abbreviation': program.abbreviation,
            'template_name': template_name,
            'program_id': program.id,
            'cohort_id': cohort_id,
            'classroom_id': classroom_id,
            'config_json': json.dumps(app_config),
            'server_date_time': str(datetime.datetime.now()),
        }
        template_directory = ''  # i.e. from the root of the app
        return template_path, params, template_directory


class AccountHandler(ViewHandler):
    def do(self):
        return "account.html", {}


class DocumentsHandler(ViewHandler):
    def do(self):
        return "documents.html", {}


class TeacherPanelHandler(ViewHandler):
    """A program-customized ultra-simple interface for teachers."""
    def do(self, program_abbreviation):
        if self.access_restricted(['student', 'public']): return

        user = self.get_current_user()
        program = self.api.get('program', {'abbreviation': program_abbreviation})[0]
        pd_list = []
        cohort_id = self.request.get('cohort')
        if cohort_id:
            # Double check that the cohort and the program make sense together.
            cohort = Cohort.get_by_id(cohort_id)
            if program.id not in cohort.assc_program_list:
                logging.error("Program/cohort mismatch in teacher panel. "
                                 "Associations are screwy.")
            pd_list = self.api.get('pd', {
                'program': program.id,
            }, ancestor=user)  # strongly consistent query
        template_path = '/programs/{}/teacher_panel.html'.format(
            program_abbreviation)
        teacher_config = Program.get_app_configuration(program.abbreviation,
                                                       'teacher')
        params = {
            'program_id': program.id,
            'program_name': program.name,
            'program_abbreviation': program.abbreviation,
            'cohort_id': cohort_id,
            'pd_json': json.dumps([pd.to_dict() for pd in pd_list]),
            'program_outline_json': self.api.program_outline(program.id),
            'stratifier_json': json.dumps(
                teacher_config['stratifiers']['teacher_condition'])
        }
        template_directory = ''  # i.e. from the root of the app
        return template_path, params, template_directory


class EntityHandler(ViewHandler):
    """For viewing entity json."""
    def do(self):
        return 'entity.html', {}


class ImpersonateHandler(ViewHandler):
    def do(self):
        # Don't restrict any access except public; a legitimate user may be
        # impersonating a teacher or student and coming to this page in order
        # to STOP impersonating, and we need to let them do so.
        if self.access_restricted(['public']):
            return

        user = self.get_current_user()  # may be impersonated user
        normal_user = self.get_current_user(method='normal')

        # The impersonation page provides links relevant to the impersonated
        # user. Look up details so we can construct those links.
        cohort_ids = [id for id in user.assc_cohort_list]
        cohorts = self.api.get('cohort', {'id': cohort_ids})

        program_ids = list(set([c.assc_program_list[0] for c in cohorts]))
        programs = self.api.get('program', {'id': program_ids})
        program_dict = {p.id: p for p in programs}

        # Structure the information as a list of dictionaries, each dict with
        # the right URL and link description stuff.
        program_link_info = []
        for cohort in cohorts:
            info = {}
            program = program_dict[cohort.assc_program_list[0]]
            # both teachers and school_admins use the teacher program
            if user.user_type == 'student':
                # Assumes students are only in one classroom, so break if
                # that's not true.
                if len(user.assc_classroom_list) is not 1:
                    raise Exception(
                        "Problem with student's classroom associations: {}."
                        .format(user.id))
                info['user_type'] = 'student'
                info['link'] = '/p/{}/{}?classroom={}&cohort={}'.format(
                    program.abbreviation, info['user_type'],
                    user.assc_classroom_list[0], cohort.id)
            else:
                info['user_type'] = 'teacher'
                info['link'] = '/p/{}/{}?cohort={}'.format(
                    program.abbreviation, info['user_type'], cohort.id)
            info['program_name'] = program.name
            program_link_info.append(info)

        # With the necessary information wrangled, figure out what the page is
        # supposed to do: redirect, impersonate, etc.
        redirect_url = None
        page_action = self.request.get('page_action')
        if page_action == 'impersonate':
            target_id = self.request.get('target')
            target = self.internal_api.get_from_path('user', target_id)
            try:
                self.impersonate(target)
                redirect_url = str(self.request.get('redirect')) or '/impersonate'
            except PermissionDenied:
                redirect_url = '/impersonate?permission_denied=true'
        elif page_action == 'stop_impersonating':
            # clear the impersonated user
            self.stop_impersonating()
            redirect_url = '/impersonate'

        if redirect_url:
            self.redirect(redirect_url)
            return

        return 'impersonate.html', {'program_link_info': program_link_info}


class QualtricsSessionCompleteHandler(ViewHandler):
    """Publicly accessible "you're done" page that also saves progress 100.

    Takes 3 request parameters:
    * program - str, the program abbreviation (NOT id)
    * user - str, the user id
    * activity_ordinal - int, e.g. 1 for session 1, etc.
    """
    def do(self):
        # No call to self.access_restricted; publicly available page.

        params = util.get_request_dictionary(self.request)

        # Ignore certain calls that typically come from Qualtrics when people
        # are testing.
        is_preview = (params['program'] and params['user'] == '' and
                      params['activity_ordinal'] is None)
        if is_preview:
            logging.info("Interpreted as Qualtrics testing. Ignoring.")
            return 'qualtrics_session_complete.html', {'show_footer': False}

        if 'program' in params:
            params['program'] = params['program'].upper()

        try:
            program = self.check_params(params)
        except IdError:
            logging.error("User does not exist: {}.".format(params['user']))
            return self.http_not_found()
        except Exception as e:
            logging.error(e)
            return self.http_not_found()

        # Save a progress pd, value 100. Aggregation will make sure they get a
        # COM code.
        o = int(params['activity_ordinal'])
        self.internal_api.create('pd', {
            'program': program.id,
            'activity_ordinal': o,
            'scope': params['user'],
            'scope_kind': 'user',
            'variable': 's{}__progress'.format(o),
            'value': 100,
        })

        return 'qualtrics_session_complete.html', {'show_footer': False}

    def check_params(self, params):
        """Raises exceptions if there are problems with request data."""


        # Make sure all parameters are present.
        required = ['program', 'user', 'activity_ordinal']
        missing = set(required) - set(params.keys())
        if missing:
            raise Exception("Missing required parameters: {}.".format(missing))

        program_list = self.internal_api.get(
            'program', {'abbreviation': params['program']})
        if len(program_list) is not 1:
            raise Exception("Invalid program: {}.".format(params['program']))
        else:
            program = program_list[0]

        # User must exist and be associated with provided program.
        user = self.internal_api.get_from_path('user', params['user'])
        if user.assc_program_list[0] != program.id:
            raise Exception("Invalid program for user: {} {}."
                            .format(params['program'], params['user']))

        # Activity ordinal must be among the available program sessions.
        o = int(params['activity_ordinal'])
        student_program_outline = Program.get_app_configuration(
            program.abbreviation, 'student')['outline']
        modules_match = [module.get('activity_ordinal', None) is o
                         for module in student_program_outline]
        if not any(modules_match):
            raise Exception("Invalid activity_ordinal: {}.".format(o))

        return program


class ResetPasswordHandler(ViewHandler):
    """A page with one purpose: users put new passwords into a field and
    submit them. No log in, no fanciness."""
    def do(self, token):
        # Check the token right away, so users don't find out it's bad AFTER
        # they fill out the form.
        user = self.api.check_reset_password_token(token)
        return 'reset_password.html', {
            'token': token,
            'token_valid': user is not None,
        }


class FourOhFourHandler(ViewHandler):
    """Doesn't handle real 404 errors, just the url /404."""
    def do(self):
        return self.http_not_found()


class SignInCardHandler(BaseHandler):
    """For rendering pdfs of student-customized labels.

    Tutorial: http://blog.notdot.net/2010/04/Generating-PDFs-on-App-Engine-Python-and-introducing-Mapvelopes
    Guide: http://reportlab.com/docs/reportlab-userguide.pdf
    """

    def do_wrapper(self):
        self.do()

    def do(self):
        cohort_id = self.request.get('cohort')
        session = int(self.request.get('session'))

        cohort = Cohort.get_by_id(cohort_id)
        roster, from_memcache = self.internal_api.get_roster(cohort_id)

        if len(roster) is 0:
            return self.blank_response()
        else:
            # Filter out uncertified students. By definition, we don't want
            # kids typing in their names this way.
            roster = [s for s in roster if s['certified']]

        # Batch students into classrooms, and then into sets of six (six b/c
        # that's how labels are laid out for printing).
        classroom_rosters = {}
        for s in roster:
            key = s['classroom_name']
            if key not in classroom_rosters:
                classroom_rosters[key] = []
            classroom_rosters[key].append(s)
        label_pages = {}
        for classroom_name, student_list in classroom_rosters.items():
            label_pages[classroom_name] = []
            student_index = 0
            while student_index < len(student_list):
                page = []
                for x in range(6):
                    if student_index < len(student_list):
                        page.append(student_list[student_index])
                    student_index += 1
                label_pages[classroom_name].append(page)

        self.response.headers['Content-Type'] = 'application/pdf'
        self.response.headers['Content-Disposition'] = 'attachment; filename=sign in cards - {}.pdf'.format(cohort.name)
        c = canvas.Canvas(self.response.out, pagesize=letter)

        # In normal CSS box model terminology.
        # PDF library has coordinates in "points", so we use provided
        # conversions to switch to inches.
        bottom_margin = 0.57 * units.inch
        left_margin = 0.25 * units.inch
        label_h_padding = 0.07 * units.inch
        label_v_padding = 0.1 * units.inch
        label_height = 2.8 * units.inch
        label_width = 3.86 * units.inch

        # Coordinate system has origin at bottom left. These offsets calculate
        # the upper left corner of each of six labels on a page where text
        # should start rendering.
        offsets = [
            # 1: top left
            (left_margin + label_h_padding,
             bottom_margin + 5 * label_v_padding + 3 * label_height),
            # 2: top right
            (left_margin + label_h_padding,
             bottom_margin + 3 * label_v_padding + 2 * label_height),
            # 3: center left
            (left_margin + label_h_padding,
             bottom_margin + 1 * label_v_padding + 1 * label_height),
            # 4: center right
            (left_margin + 3 * label_h_padding + label_width,
             bottom_margin + 5 * label_v_padding + 3 * label_height),
            # 5: bottom left
            (left_margin + 3 * label_h_padding + label_width,
             bottom_margin + 3 * label_v_padding + 2 * label_height),
            # 6: bottom right
            (left_margin + 3 * label_h_padding + label_width,
             bottom_margin + 1 * label_v_padding + 1 * label_height),
        ]

        for classroom_name, page_list in label_pages.items():
            for page in page_list:
                page_title = c.beginText()
                page_title.setTextOrigin(left_margin, 10.5 * units.inch)
                page_title.setFont("Times-Roman", 10)
                page_title.textLine("{}  -  Session {}"
                                    .format(classroom_name, session))
                c.drawText(page_title)
                for index, student in enumerate(page):
                    text = c.beginText()
                    text.setTextOrigin(*offsets[index])
                    text.setFont("Times-Roman", 16)
                    text.textLine("Students' PATHS+")
                    body_lines, highlighted_lines = self.get_label_text(cohort, session, student)
                    for index, line in enumerate(body_lines):
                        if (index in highlighted_lines):
                            text.setFont("Courier-Bold", 10)
                        else:
                            text.setFont("Times-Roman", 10)
                        text.textLine(line)
                    c.drawText(text)
                c.showPage()  # done with current page

        c.save()  # done with whole pdf; will be sent to client as download

    def get_label_text(self, cohort, session, student):
        # The interpolated values will set as courier bold by the
        # highlighted_lines variable above.
        wrapped_classroom_name = textwrap.wrap(student['classroom_name'], 32)
        body = (
            "  * Launch Google Chrome\n"
            "  * Go to the website provided by your teacher\n"
            "  * Enter your participation code:\n"
            "    {cohort_code} {session}\n"
            "  * Select your class:\n"
            "    " + "\n    ".join(wrapped_classroom_name) + "\n"
            "  * Enter your full first name:\n"
            "    {first_name}\n"
            "  * Enter your last name:\n"
            "    {last_name}\n"
            "  * Click \"Submit\"\n")

        body = body.format(
            cohort_code=cohort.code,
            session=session,
            classroom_name=student['classroom_name'],
            first_name=student['first_name'],
            last_name=student['last_name'],
        )

        highlighted_lines = [
            3,  # participation code
            6 + len(wrapped_classroom_name),  # first name
            8 + len(wrapped_classroom_name),  # last name
        ] + [5 + x for x in range(len(wrapped_classroom_name))]

        return body.split('\n'), highlighted_lines

    def blank_response(self):
        self.response.headers['Content-Type'] = 'text/plain'
        self.response.write("This school has no classrooms and/or students. "
            "Cannot display name cards.")

webapp2_config = {
    'webapp2_extras.sessions': {
        # cam. I think this is related to cookie security. See
        # http://webapp-improved.appspot.com/api/webapp2_extras/sessions.html
        'secret_key': '8YcOZYHVrVCYIx972K3MGhe9RKlR7DOiPX2K8bB8',
        # @todo: seem like obvious choices, read more and implement generally
        # https://webapp-improved.appspot.com/api/webapp2_extras/sessions.html
        # 'cookie_args': {
        #     'secure': True,
        #     'httponly': True,
        # }
    },
}

app = webapp2.WSGIApplication([
    ('/', HomeHandler),
    ('/god/?', GodHandler),
    ('/go/?', IdentifyHandler),
    ('/teacher/?', TeacherHandler),
    ('/start/?', IdentifyHandler),
    ('/beta', BetaHandler),
    ('/registration_survey/?', RegistrationSurveyHandler),
    ('/d/?', DashboardHandler),
    ('/done', QualtricsSessionCompleteHandler),
    ('/p/(.*)/teacher_panel/?', TeacherPanelHandler),
    ('/p/(.*)/(.*)/?', ProgramHandler),     # e.g. /p/TP1/student
    ('/sign_in_cards/?', SignInCardHandler),
    ('/entity/?', EntityHandler),           # for viewing entity json
    ('/login/?(.*)', LoginHandler),
    ('/logout/?', LogoutHandler),
    ('/impersonate/?', ImpersonateHandler),
    ('/test/?', TestHandler),
    ('/documents/?', DocumentsHandler),
    ('/account/?', AccountHandler),
    ('/reset_password/(.*)', ResetPasswordHandler),
    ('/404/?', FourOhFourHandler),
    ('/({})/?'.format('|'.join(public_home_pages)), HomePageHandler),
    # GenericHandler line *must* go last.
    # All other handlers above this line.
    ('/(.*)', GenericHandler),
], config=webapp2_config, debug=debug)

# /           public home page
# /go         student entry
# /start      ALSO student entry (linked from perts.net)
# /login
# /logout
# /register   teacher registration
# /p          program apps
# /p/TP1/student#position
# /d          dashboards: for logged in teachers, admins, and researchers not doing a program

# /d#[level]/[id]/[page]
# /d#user/[id]/cohort_progress_list
# /d#user/[id]/account

# /god        crazy god powers
# /impersonate
