"""Collection of hard-coded settings."""

from collections import namedtuple

# For Run B of PATHS+ there's actually only one session. To make sure no one
# winds up anywhere weird, just point both sessions at the right survey.
default_qualtrics_links = {
    1: '',  # "HP17 Session 4 OFFICIAL"
    2: '',  # "HP17 Session 4 OFFICIAL" again!
}

unit_test_directory = 'unit_testing'

# Controls how out-of-balance we're willing to allow a stratification bucket
# to get before we use deterministic assignment, rather than random assignment.
stratification_balance_margin = 0.05

allowed_auth_types = ['direct', 'facebook', 'google']

# These are ranked! Higher types can impersonate lower types.
allowed_user_types = ['student', 'teacher', 'school_admin', 'researcher',
                      'god']

# This one isn't actually enforced anywhere yet.
allowed_activity_states = ['incomplete', 'completed', 'aborted']


# Who can create what type of object?
# (gods can create anything; they're excluded from this list)
user_type_can_create = {
    'public': ['user'],
    'student': ['pd', 'activity'],
    'teacher': ['pd', 'classroom', 'user', 'activity'],
    'school_admin': ['pd', 'classroom', 'user', 'activity'],
    'researcher': ['pd', 'classroom', 'user', 'activity', 'cohort', 'program',
                   'activity_template', 'school'],
}

user_type_can_delete = {
    'teacher': ['classroom', 'activity'],
    'school_admin': ['classroom', 'activity', 'user'],
    'researcher': ['classroom', 'user', 'activity', 'cohort', 'school'],
}

# todo: the above list doesn't even bother to list what god can do...
# probably this code should be parallel, which involves modifying the code
# that checks this list.
can_put_user_type = {
    # When students try to sign in but aren't recognized, we create an account
    # for them and let them in, so public has to be able to put students.
    # Also, to run the device test on the help page, we need to create a fake
    # teacher, so everyone, public on up, needs to be able to create teachers.
    'public': ['student', 'teacher'],
    'student': [],
    'teacher': ['teacher'],
    # In Yosemite, school_admins ("Deanna") can upload rosters of students,
    # which involves creating students. They can also create
    # test teachers via the browser test in the help page.
    'school_admin': ['student', 'teacher'],
    # Researchers can put school_admins so that they can promote users who
    # have signed up (and are teachers by default) to be school admins.
    # They can put students so they can create test student users to run
    # through program apps. There's no reason for them to create regular
    # students.
    'researcher': ['student', 'school_admin'],
    'god': ['student', 'teacher', 'school_admin', 'researcher', 'god'],
}

# some kinds require additional update validation, e.g., cohorts
# must have unique codes
kinds_requiring_put_validation = [
    'cohort', 'user',
]

# variables with special rules about filters to apply
kinds_with_get_filters = [
    'pd',
]

# These define the initial relationships between the created entity and the
# creating user.
creator_relationships = {
    'program': 'set_owner',
    'classroom': 'set_owner',
    'cohort': 'set_owner',
    'user': None,
    'activity': 'set_owner',
    'school': 'associate',
    'pd': None,  # pd visibility is based on cohort and program assc.
    'email': None,  # email is called via internal apis
    'qualtrics_link': None,
}

# These pd variables names, when generated within an activity (not, for
# instance, from the teacher panel or the dashboard), will get marked as
# public = True.
pd_whitelist = [
    'time', 'position_history', 'consent', 'condition',
    's1__qualtrics_link',
    's2__qualtrics_link',
    's1__progress',
    's2__progress',
    's3__progress',
    's4__progress',
    's5__progress',
    'checklist-teacher-1',
    'checklist-teacher-2',
    'checklist-teacher-3',
    'checklist-teacher-4',
    'checklist-teacher-5',
    'checklist-teacher-6',
    'checklist-teacher-7',
    'checklist-teacher-8',
    'checklist-teacher-9',
    'checklist-school_admin-1',
    'checklist-school_admin-2',
    'checklist-school_admin-3',
    'checklist-school_admin-4',
    'checklist-school_admin-5',
    'checklist-school_admin-6',
    'educator_agreement_accepted',
    'parent_info_confirmed',
    # This is used by the cross-site client test.
    'cross_site_test',
]

# certain types need to perform custom validation before creation
custom_create = ['pd']

# These status codes are set manually by teachers on the roster page. All of
# them imply non-participation, but have different ways of being counted in
# the reporting interfaces. They originate with a third-party organization
# collaborating on Yosemite (ICF), and we got their definitions directly from
# them. For more detail, see the "Status Definitions" sheet on the Yosemite
# UI Mockups:
# https://docs.google.com/spreadsheets/d/1K3U5oRtjaZfirRg2AuDOA5OM8brm5d2YSPPOUVrcWjU/edit#gid=1023588647
status_codes = {
    'A': {'label': 'Absent', 'study_eligible': True,
          'makeup_eligible': True, 'counts_as_completed': False,
          'exclude_from_counts': False},
    'SR': {'label': 'Student Refusal', 'study_eligible': True,
           'makeup_eligible': True, 'counts_as_completed': False,
           'exclude_from_counts': False},
    'NFR': {'label': 'No Form Returned', 'study_eligible': True,
            'makeup_eligible': True, 'counts_as_completed': False,
            'exclude_from_counts': False},
    'ISS': {'label': 'In School Suspension', 'study_eligible': True,
            'makeup_eligible': True, 'counts_as_completed': False,
            'exclude_from_counts': False},
    'TRI': {'label': 'Technology-related Issue', 'study_eligible': True,
            'makeup_eligible': True, 'counts_as_completed': False,
            'exclude_from_counts': False},
    'PR': {'label': 'Parent Refusal', 'study_eligible': True,
           'makeup_eligible': False, 'counts_as_completed': False,
           'exclude_from_counts': False},
    'COM': {'label': 'Completed', 'study_eligible': True,
            'makeup_eligible': False, 'counts_as_completed': True,
            'exclude_from_counts': False},
    'CLR': {'label': 'Completed by Linked Record', 'study_eligible': True,
            'makeup_eligible': False, 'counts_as_completed': True,
            'exclude_from_counts': False},
    'CCI': {'label': 'Cannot Complete Independently', 'study_eligible': False,
            'makeup_eligible': False, 'counts_as_completed': False,
            'exclude_from_counts': False},
    'DC': {'label': 'Dropped Class', 'study_eligible': False,
           'makeup_eligible': False, 'counts_as_completed': False,
           'exclude_from_counts': False},
    'DS': {'label': 'Dropped School', 'study_eligible': False,
           'makeup_eligible': False, 'counts_as_completed': False,
           'exclude_from_counts': False},
    'E': {'label': 'Expelled', 'study_eligible': False,
          'makeup_eligible': False, 'counts_as_completed': False,
          'exclude_from_counts': False},
    'EA': {'label': 'Extended Absence', 'study_eligible': False,
           'makeup_eligible': False, 'counts_as_completed': False,
           'exclude_from_counts': False},
    'H': {'label': 'Homebound', 'study_eligible': False,
          'makeup_eligible': False, 'counts_as_completed': False,
          'exclude_from_counts': False},
    'MA': {'label': 'Moved Away', 'study_eligible': False,
           'makeup_eligible': False, 'counts_as_completed': False,
           'exclude_from_counts': False},
    'OGR': {'label': 'Out of Grade Range', 'study_eligible': False,
            'makeup_eligible': False, 'counts_as_completed': False,
            'exclude_from_counts': False},
    'OSS': {'label': 'Out of School Suspension', 'study_eligible': False,
            'makeup_eligible': False, 'counts_as_completed': False,
            'exclude_from_counts': False},
    'TAC': {'label': 'Took in Another Class', 'study_eligible': False,
            'makeup_eligible': False, 'counts_as_completed': False,
            'exclude_from_counts': False},
    'DIS': {'label': 'Discard: Incorrect Sign-in', 'study_eligible': False,
            'makeup_eligible': False, 'counts_as_completed': False,
            'exclude_from_counts': True},
    'MWN': {'label': 'Link to Primary Record', 'study_eligible': False,
            'makeup_eligible': False, 'counts_as_completed': False,
            'exclude_from_counts': True},
}

# defines where users go after login, and what the "home" button does
user_home_page = {
    'god': '/d',
    'researcher': '/d',
    'school_admin': '/d',
    # For Yosemite, this just points at SP.
    # @todo: in future versions, point to a program-agonstic
    # CohortChooserController so any cohort can be selected in any program.
    'teacher': '/teacher',
    # students: not allowed at the login page
    'public': '/',
}

# These define what kinds of other entity ids must be passed in when an entity
# is created.
required_associations = {
    # Part of being identified as a student is choosing a classroom, so we can
    # insist that it is provided during creation.
    'student': ['classroom'],  # todo: add cohort here
    # A cohort is NOT required on creation for teachers and admins b/c that's
    # part of the registration survey, which doesn't happen right away.
    'teacher': [],
    'school_admin': [],
    'researcher': [],
    'god': [],
    'program': [],
    'activity': ['program', 'cohort'],
    'cohort': ['program', 'school'],
    'classroom': ['program', 'cohort', 'user'],
    'school': [],
    'pd': [],
    'email': [],
    'qualtrics_link': [],
}

# If certain ids are available when an entity is created, they also can be
# associated, but no error will be thrown if they're NOT present.
optional_associations = {
    'activity': ['classroom'],
    'teacher': ['cohort'],
}

# These encode the redunant, non-normalized associations between users and
# other entities. For instance, by associating a user to a classroom, that
# user is also automatically associated to the corresponding cohort, which
# continues to recursively trigger other associations. See api.Api.associate().
user_association_cascade = {
    'program': [],
    'cohort': ['program', 'school'],
    'classroom': ['cohort','program'],
}
# Same as above, but applied when disassociating from entities. The only
# difference currently is that the cascade does not continue to programs, b/c
# it makes little sense to have a user without a program association.
user_disassociation_cascade = {
    'program': [],
    'cohort': ['school'],
    'classroom': ['cohort',],
}
# todo: should this cascade apply to all entities, not just users?
# todo: how do we disassociate people?

CascadeInfo = namedtuple('CascadeInfo', ['kind', 'property'])
children_cascade = {
    # "cohorts which have a given program in their assc_program_list are
    # children of the program", etc.
    'program':   [CascadeInfo('cohort', 'assc_program_list')],
    'school':    [CascadeInfo('cohort', 'assc_school_list')],
    'cohort':    [CascadeInfo('classroom', 'assc_cohort_list'),
                  CascadeInfo('teacher_activity', 'assc_cohort_list')],
    'teacher':   [CascadeInfo('classroom', 'assc_user_list'),
                  CascadeInfo('teacher_activity', 'teacher'),
                  # The teacher panel creates pd for a teacher outside of
                  # any activity.
                  CascadeInfo('pd', 'scope')],
    'classroom': [CascadeInfo('student_activity', 'assc_classroom_list')],
    'activity':  [CascadeInfo('pd', 'activity')],
    'student':   [CascadeInfo('pd', 'scope')],
}

# at least 8 characters, ascii only
# http://stackoverflow.com/questions/5185326/java-script-regular-expression-for-detecting-non-ascii-characters
password_pattern = r'^[\040-\176]{8,}$'

# Facebook log in
FACEBOOK_APP_ID = 'VALID FB APP ID HERE'
FACEBOOK_APP_SECRET = 'VALID APP SECRET HERE'

# We want the entity store to ignore these properties, mostly because they
# can change in ways it doesn't expect, and it shouldn't be writing to them
# anyway. These properties will be prefixed with an underscore before being
# sent to the client.
client_private_properties = [
    'modified',
    'auth_id',
    'aggregated',
    'aggregation_data',
    'certified_aggregation_data',
    'student_activity_list',
]

# These properties should never be exposed to the client.
client_hidden_properties = [
    'hashed_password',
    'aggregation_json',  # b/c it's redundant with aggregated_data
]

boolean_url_arguments = [
    'is_archived',
    'is_test',
    'registration_complete',
    'force_create',  # /api/identify
    'reset_history',  # /api/stratify
    'escape_impersonation',  # used in program app path testing, see also api_handlers.ApiHandler
    'public',  # marks pds that can be sent to the client
    'recurse_children',  # used in api_handlers.UpdateHandler
    'preview',  # used in api_handlers.UpdateHandler and SystematicUpdateHandler
    'certified',  # used to certify students in roster
    'roster_complete',  # used to verify that all students on a roster have been entered
    'uploaded_by_admin',
]
integer_url_arguments = [
    'activity_ordinal',
    'fetch_size',
    'session_ordinal',  # used in QualtricsLink
]
# UTC timezone, in ISO date format: YYYY-MM-DD
date_url_arguments = [
    'birth_date',
    'scheduled_date',
]
time_url_arguments = [
    'scheduled_time',
]
# UTC timezone, in an ISO-like format (missing the 'T' character between
# date and time): YYYY-MM-DD HH:mm:SS
datetime_url_arguments = [
    'start_time',
    'roster_completed_datetime',
]
# Converted to JSON with json.dumps().
json_url_arugments = [
    'activities',
    'pd',
    'proportions',  # /api/stratify
    'attributes',  # /api/stratify
]
# These arguments are meta-data and are never applicable to specific entities
# or api actions. They appear in url_handlers.BaseHandler.get().
ignored_url_arguments = [
    'escape_impersonation',
    'impersonate',
    'connection_attempts',
]
# also, any normal url argument suffixed with _json will be interpreted as json

# Converted by util.get_request_dictionary()
# Problem: we want to be able to set null values to the server, but
# angular drops these from request strings. E.g. given {a: 1, b: null}
# angular creates the request string '?a=1'
# Solution: translate javascript nulls to a special string, which
# the server will again translate to python None. We use '__null__'
# because is more client-side-ish, given that js and JSON have a null
# value.
# javascript | request string | server
# -----------|----------------|----------
# p = null;  | ?p=__null__    | p = None
url_values = {
    '__null__': None,
}

true_strings = ['true']

# governs how csv data caches are structured and updated
# @todo: remove this, it's not relevant now considering the compute_engine
# paradigm.
csv_cache_settings = {
    'pd_all': {
        # how uniqueness is determined in the csv
        'dict_keys': ['cohort', 'user', 'variable'],
        'columns': ['cohort', 'user', 'variable', 'value', 'activity_ordinal',
                    'created', 'activity'],
        # how many pds entities to check at once when updating
        'fetch_size': 500,
        # what kind of entities to check for modifications
        'kind': 'pd',
        # what property determines if the entity has modifications
        'newness_property': 'created',
    },
    'user_all': {
        # how uniqueness is determined in the csv
        'dict_keys': ['id'],
        'columns': ['id', 'user_type', 'first_name', 'last_name', 'modified',
                    'assc_cohort_list', 'assc_classroom_list',
                    'assc_school_list', 'owned_classroom_list'],
        # how many user entities to check at once when updating
        'fetch_size': 10,
        # what kind of entities to check for modifications
        'kind': 'user',
        # what property determines if the entity has modifications
        'newness_property': 'modified',
    },
}

systematic_update_settings = {
    'lowercase_login': {
        'kind': 'user',
    },
}


# Email settings
#
# Platform generated emails can only be sent from email addresses that have
# viewer permissions or greater on app engine.  So if you are going to change
# this please add the sender as an application viewer on
# https://appengine.google.com/permissions?app_id=s~pegasusplatform
#
# There are other email options if this doesn't suit your needs check the
# google docs.
# https://developers.google.com/appengine/docs/python/mail/sendingmail
from_yosemite_email_address = ""
# This address should forward to the development team
# I could not use the google groups because of limited permissions
to_dev_team_email_address = ""
# * spam prevention *
# time between emails
# if we exceed this for a give to address, an error will be logged
suggested_delay_between_emails = 1      # 1 day
# whitelist
# some addessess we spam, like our own
# * we allow us to spam anyone at a *@studentspaths.org domain so
# this is the best address for an admin
addresses_we_can_spam = [
    to_dev_team_email_address,
    ''
]

# Hard-coded emails

registration_email_from = ""
registration_email_subject = "Welcome to Students' PATHS!"
# Hanging spaces are intentional!
# http://markdown-guide.readthedocs.org/en/latest/basics.html#line-return
# Note: you must run a .format() on this string to interpolate the email
# address.
registration_email_body = """
Welcome!

You've created an account with the Students' PATHS study. We're excited to
work with you!

Please [sign in][1] using this email address ({}) and your password.

[1]: https://www.studentspaths.org/login "Students' PATHS log in page"

Yours truly,
The Students' PATHS Researchers
"""

forgot_password_subject = "Password reset requested."
# Hanging spaces are intentional!
# http://markdown-guide.readthedocs.org/en/latest/basics.html#line-return
# Note: you must run a .format() on this string to interpolate the token.
forgot_password_body = """
Greetings,

A password reset has been requested for your Students' PATHS account. Please
use [this link][1] to reset your password.

[1]: https://www.studentspaths.org{} "Temporary password reset link"

This link will expire in one hour.

Yours truly,
The Students' PATHS Researchers
"""

change_password_subject = "Your Students' PATHS password has been changed."
# Hanging spaces are intentional!
# http://markdown-guide.readthedocs.org/en/latest/basics.html#line-return
change_password_body = """
Greetings,

The password on your Students' PATHS account has been changed.

Yours truly,
The Students' PATHS Researchers
"""

admin_reminder_summary_subject = "{{ emails | length }} reminder emails sent today"

admin_reminder_summary_body = """
Dear ICF Administrators,

Any reminder emails sent to coordinators are below.

Mountainously Yours,
Denali
"""
