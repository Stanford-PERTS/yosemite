# Use this as a template for future programs. Any less data will cause problems
# with generating activity entities, etc.
# student_config = {
#     'outline': [
#         {
#             'id': 'session_1',
#             'name': 'Session 1',
#             'type': 'activity',
#             'activity_ordinal': 1,
#             'nodes': [],
#         },
#     ]
# }

# teacher_config = {
#     'outline': [
#         {
#             'id': 'session_1',
#             'name': 'Session 1',
#             'type': 'activity',
#             'activity_ordinal': 1,
#             'nodes': [],
#         },
#     ]
# }

# WARNING! If you change the names of activities here, existing activities
# on the platform will not see your changes automatically. You must go find
# the activity refresh button and push it!


# Email greetings, bodies, and closings are first parsed by jinja, with the
# relevant user, classroom, and activity available. The emailer then parses
# the resulting text as markdown (https://pypi.python.org/pypi/Markdown).
standard_email_greeting = """Dear {{user.first_name}},

This is a reminder that """

# Hanging spaces are intentional!
# http://markdown-guide.readthedocs.org/en/latest/basics.html#line-return
standard_email_closing = """

If you haven't already done so, please [log in to studentspaths.org][1], click
on "Home" in the upper right-hand corner, select "Documents," and then download
"Session Instructions" and the "Student Sign-in Cards" for the appropriate
session.  Remember that the Student Sign-in Cards should be printed on the
perforated name cards provided to you during the Site Visit.  (The "Session
Instructions" can be printed normally.)  Provide these materials to the
instructor(s) listed above, along with your verbal encouragement.  Should there
be any questions you're not able to answer, please don't hesitate to contact us
at the number below.

[1]: https://www.studentspaths.org/login "PATHS+ log in page"

It is very important to keep to the schedule, but if necessary, please work
with teachers to reschedule so that all project-related activities can be
completed on time.

Warm regards,  
The Students' PATHS+ Team"""
# 1-844-225-6089"""

student_config = {
    'show_nav_bar': False,

    'outline': [
        {
            'id': 'start',
            'name': 'Consent',
            'nodes': [
                'checkConsent()',
                'consent',
                'menuBranch()',
            ],
        },
        {
            'id': 'menu',
            'name': 'Student Menu',
            'nodes': [
                'menu',
            ],
        },
        {
            'id': 'demo_end',
            'name': 'Demo Over Message',
            'nodes': [
                'demo_end',
            ],
        },
        {
            'id': 'session_1',
            'name': 'Session 1',
            'type': 'activity',
            'activity_ordinal': 1,
            # if it is this day or after, then the session is open
            'date_open': '2018-01-01',
            # if it is this day or after, then the session is closed
            # i.e. the last day to finish is the day BEFORE this one
            'date_closed': '2020-12-31',
            'nodes': [
                # No randomization here! Session 4 has do distinction for
                # various conditions.
                'getQualtricsLinks()',
                'goToQualtrics(1)',
            ],
        },
        # For PATHS+, Runs B and C won't have a session 2
        # {
        #     'id': 'session_2',
        #     'name': 'Session 2',
        #     'type': 'activity',
        #     'activity_ordinal': 2,
        #     # This combines with the relative dates; users won't be allowed
        #     # in until the LATEST of the two dates.
        #     'date_open': '2017-01-01',
        #     'date_open_relative_to': ['student', 1],  # user type, ordinal
        #     'date_open_relative_interval': 7,  # days after
        #     # if it is this day or after, then the session is closed
        #     # i.e. the last day to finish is the day BEFORE this one
        #     'date_closed': '2018-12-31',
        #     'date_closed_relative_to': ['student', 1],  # user type, ordinal
        #     'date_closed_relative_interval': 63,  # days after
        #     'nodes': [
        #         # If, for any reason, a student's data wasn't set up right by
        #         # going through session 1, these functions should be called
        #         # again to make sure it's right for session 2. Consequently,
        #         # these functions should also be idempotent.
        #         'randomizeCondition()',
        #         'getQualtricsLinks()',
        #         # Now it's safe to go to Qualtrics.
        #         'goToQualtrics(2)',
        #     ],
        # },

    ],

    'stratifiers': {
        'student_condition': {'treatment': 1, 'control': 1},
        'all_treatment': {'treatment': 1},
        'all_control': {'control': 1},
    },


    # Email greetings, bodies, and closings are first parsed by jinja, with the
    # relevant user, classroom, and activity available. The emailer then parses
    # the resulting text as markdown (https://pypi.python.org/pypi/Markdown).
    'reminder_emails': [
        {
            'activity_ordinal': 1,
            'send_if_activity': 'incomplete',  # or 'aborted' or 'completed'
            # this means send three days before schedule date
            'relative_date_to_send': -3,
            'reply_to': '',
            'from_address': '',
            'subject': 'Your first student session is coming up in three days',
            'greeting': standard_email_greeting,
            'body': "*{{ classroom.name }}* has its first session in "
                    "three days, on "
                    "{{ activity.get_long_form_date_string() }}.",
            'closing': standard_email_closing,
        },
        {
            'activity_ordinal': 1,
            'send_if_activity': 'incomplete',  # or 'aborted' or 'completed'
            # this means send on the scheduled date
            'relative_date_to_send': 0,
            'reply_to': '',
            'from_address': '',
            'subject': 'Your first student session is today',
            'greeting': standard_email_greeting,
            'body': "*{{ classroom.name }}* has its first session "
                    "today, {{ activity.get_long_form_date_string() }}.",
            'closing': standard_email_closing,
        },
        {
            'activity_ordinal': 2,
            'send_if_activity': 'incomplete',  # or 'aborted' or 'completed'
            # this means send three days before schedule date
            'relative_date_to_send': -3,
            'reply_to': '',
            'from_address': '',
            'subject': 'Your second student session is coming up in three days',
            'greeting': standard_email_greeting,
            'body': "*{{ classroom.name }}* has its second session in "
                    "three days, on "
                    "{{ activity.get_long_form_date_string() }}.",
            'closing': standard_email_closing,
        },
        {
            'activity_ordinal': 2,
            'send_if_activity': 'incomplete',  # or 'aborted' or 'completed'
            # this means send on the scheduled date
            'relative_date_to_send': 0,
            'reply_to': '',
            'from_address': '',
            'subject': 'Your second student session is today',
            'greeting': standard_email_greeting,
            'body': "*{{ classroom.name }}* has its second session "
                    "today, {{ activity.get_long_form_date_string() }}.",
            'closing': standard_email_closing,
        },
    ]

}

teacher_config = {
    'outline': [
        {
            'id': 'start',
            'name': 'Consent',
            'nodes': [
                'checkConsent()',
                'consent',
                'menuBranch()',
            ],
        },
        {
            'id': 'menu',
            'name': 'Teacher Menu',
            'nodes': [
                'menu',
            ],
        },
        {
            'id': 'demo_end',
            'name': 'Demo Over Message',
            'nodes': [
                'demo_end',
            ],
        },
        {
            'id': 'session_1',
            'name': 'Session 1',
            'type': 'activity',
            'activity_ordinal': 1,
            'date_open': '2014-01-13',
            # if it is this day or after, then the session is closed
            # i.e. the last day to finish is the day BEFORE this one
            'date_closed': '2014-06-15',
            'date_open_relative_to': ['student', 1],  # user type, ordinal
            'date_open_relative_interval': 1,  # days after
            'nodes': [
                'markProgress(0)',
                'randomizeCondition()',
                'student_session',
                'intro',
                'professional_development',
                'teacher_experience',
                'toi',
                'markProgress(25)',
                'mistakes_feelings',
                'mistakes_promo',
                'math_anx',
                'work_orientation',
                'teacher_burnout',
                'demographics',
                'markProgress(50)',
                'conditionBranch(session_1)',
                'treatment',
                'activity',
                'markProgress(100)',
                'goToGoodbye(session_1)',
                'control',
                'markProgress(100)',
                'goodbye',
            ],
        },
        {
            'id': 'session_2',
            'name': 'Session 2',
            'type': 'activity',
            'activity_ordinal': 2,
            'date_open': '2014-01-13',
            # if it is this day or after, then the session is closed
            # i.e. the last day to finish is the day BEFORE this one
            'date_closed': '2014-06-15',
            'date_open_relative_to': ['teacher', 1],  # user type, ordinal
            'date_open_relative_interval': 1,  # days after
            'nodes': [
                'markProgress(0)',
                'activityFollowup',
                'feedbackBranch1(session_2)',
                'activityYes',
                'feedbackBranch2(session_2)',
                'activityNo',
                'treatment',
                'markProgress(50)',
                'activity',
                'markProgress(100)',
                'goodbye',
            ],
        },
        {
            'id': 'session_3',
            'name': 'Session 3',
            'type': 'activity',
            'activity_ordinal': 3,
            'date_open': '2014-01-13',
            # if it is this day or after, then the session is closed
            # i.e. the last day to finish is the day BEFORE this one
            'date_closed': '2014-06-15',
            'date_open_relative_to': ['teacher', 2],  # user type, ordinal
            'date_open_relative_interval': 1,  # days after
            'nodes': [
                'markProgress(0)',
                'activityFollowup',
                'feedbackBranch1(session_3)',
                'activityYes',
                'feedbackBranch2(session_3)',
                'activityNo',
                'treatment',
                'markProgress(50)',
                'activity',
                'markProgress(100)',
                'goodbye',
            ],
        },
        {
            'id': 'session_4',
            'name': 'Session 4',
            'type': 'activity',
            'activity_ordinal': 4,
            'date_open': '2014-01-13',
            # if it is this day or after, then the session is closed
            # i.e. the last day to finish is the day BEFORE this one
            'date_closed': '2014-06-15',
            'date_open_relative_to': ['teacher', 3],  # user type, ordinal
            'date_open_relative_interval': 1,  # days after
            'nodes': [
                'markProgress(0)',
                'activityFollowup',
                'feedbackBranch1(session_4)',
                'activityYes',
                'feedbackBranch2(session_4)',
                'activityNo',
                'treatment',
                'markProgress(50)',
                'activity',
                'markProgress(100)',
                'goodbye',
            ],
        },
        {
            'id': 'session_5',
            'name': 'Follow up',
            'type': 'activity',
            'activity_ordinal': 5,
            'date_open': '2014-01-13',
            # if it is this day or after, then the session is closed
            # i.e. the last day to finish is the day BEFORE this one
            'date_closed': '2014-06-15',
            'date_open_relative_to': ['teacher', 1],  # user type, ordinal
            'date_open_relative_interval': 21,  # days after
            'nodes': [
                'markProgress(0)',
                'conditionBranch(session_5)',
                'activityFollowup',
                'feedbackBranch1(session_5)',
                'activityYes',
                'feedbackBranch2(session_5)',
                'activityNo',
                'treatment',
                'toi',
                'mistakes_feelings',
                'mistakes_promo',
                'work_orientation',
                'teacher_burnout',
                'teacher_talk',
                'user_feedback',
                'markProgress(100)',
                'goToGoodbye(session_5)',
                'markProgress(100)',
                'goodbye',
            ],
        },
    ],
    'stratifiers': {
        'teacher_condition': {'treatment': 1, 'control': 1},
        'all_treatment': {'treatment': 1},
        'all_control': {'control': 1},
    },

    'reminder_emails': [
        {
            'activity_ordinal': 1,
            'send_if_activity': 'incomplete',  # or 'aborted' or 'completed'
            # this means send three days before schedule date
            'relative_date_to_send': -3,
            'reply_to': '',
            'from_address': '',
            'subject': 'You have a teacher session coming up in 3 days',
            'body': "Dear {{user.first_name}},"
                "\n\n"
                "This is a reminder that you have a Teacher Session in 3 days, {{ activity.scheduled_date }}. "
                "Please visit the teacher dashboard at <a href='https://www.studentspaths.org/login'>www.studentspaths.org/login</a> "
                "to download the instructions or to reschedule your class."
                "\n\n"
                "Warm regards,"
                "\n\n"
                "The PERTS Team"
        },
        {
            'activity_ordinal': 1,
            'send_if_activity': 'incomplete',  # or 'aborted' or 'completed'
            # this means send on the scheduled date
            'relative_date_to_send': -0,
            'reply_to': '',
            'from_address': '',
            'subject': 'You have a teacher session scheduled for today',
            'body': "Dear {{user.first_name}},"
                "\n\n"
                "This is a reminder that you have a Teacher Session today, {{ activity.scheduled_date }}. "
                "Please visit the teacher dashboard at <a href='https://www.studentspaths.org/login'>www.studentspaths.org/login</a> "
                "to download the instructions or to reschedule your class."
                "\n\n"
                "Warm regards,"
                "\n\n"
                "The PERTS Team"
        },
        {
            'activity_ordinal': 2,
            'send_if_activity': 'incomplete',  # or 'aborted' or 'completed'
            # this means send three days before schedule date
            'relative_date_to_send': -3,
            'reply_to': '',
            'from_address': '',
            'subject': 'You have a teacher session coming up in 3 days',
            'body': "Dear {{user.first_name}},"
                "\n\n"
                "This is a reminder that you have a Teacher Session in 3 days, {{ activity.scheduled_date }}. "
                "Please visit the teacher dashboard at <a href='https://www.studentspaths.org/login'>www.studentspaths.org/login</a> "
                "to download the instructions or to reschedule your class."
                "\n\n"
                "Warm regards,"
                "\n\n"
                "The PERTS Team"
        },
        {
            'activity_ordinal': 2,
            'send_if_activity': 'incomplete',  # or 'aborted' or 'completed'
            # this means send on the scheduled date
            'relative_date_to_send': -0,
            'reply_to': '',
            'from_address': '',
            'subject': 'You have a teacher session scheduled for today',
            'body': "Dear {{user.first_name}},"
                "\n\n"
                "This is a reminder that you have a Teacher Session today, {{ activity.scheduled_date }}. "
                "Please visit the teacher dashboard at <a href='https://www.studentspaths.org/login'>www.studentspaths.org/login</a> "
                "to download the instructions or to reschedule your class."
                "\n\n"
                "Warm regards,"
                "\n\n"
                "The PERTS Team"
        },
        {
            'activity_ordinal': 3,
            'send_if_activity': 'incomplete',  # or 'aborted' or 'completed'
            # this means send three days before schedule date
            'relative_date_to_send': -3,
            'reply_to': '',
            'from_address': '',
            'subject': 'You have a teacher session coming up in 3 days',
            'body': "Dear {{user.first_name}},"
                "\n\n"
                "This is a reminder that you have a Teacher Session in 3 days, {{ activity.scheduled_date }}. "
                "Please visit the teacher dashboard at <a href='https://www.studentspaths.org/login'>www.studentspaths.org/login</a> "
                "to download the instructions or to reschedule your class."
                "\n\n"
                "Warm regards,"
                "\n\n"
                "The PERTS Team"
        },
        {
            'activity_ordinal': 3,
            'send_if_activity': 'incomplete',  # or 'aborted' or 'completed'
            # this means send on the scheduled date
            'relative_date_to_send': -0,
            'reply_to': '',
            'from_address': '',
            'subject': 'You have a teacher session scheduled for today',
            'body': "Dear {{user.first_name}},"
                "\n\n"
                "This is a reminder that you have a Teacher Session today, {{ activity.scheduled_date }}. "
                "Please visit the teacher dashboard at <a href='https://www.studentspaths.org/login'>www.studentspaths.org/login</a> "
                "to download the instructions or to reschedule your class."
                "\n\n"
                "Warm regards,"
                "\n\n"
                "The PERTS Team"
        },
        {
            'activity_ordinal': 4,
            'send_if_activity': 'incomplete',  # or 'aborted' or 'completed'
            # this means send three days before schedule date
            'relative_date_to_send': -3,
            'reply_to': '',
            'from_address': '',
            'subject': 'You have a teacher session coming up in 3 days',
            'body': "Dear {{user.first_name}},"
                "\n\n"
                "This is a reminder that you have a Teacher Session in 3 days, {{ activity.scheduled_date }}. "
                "Please visit the teacher dashboard at <a href='https://www.studentspaths.org/login'>www.studentspaths.org/login</a> "
                "to download the instructions or to reschedule your class."
                "\n\n"
                "Warm regards,"
                "\n\n"
                "The PERTS Team"
        },
        {
            'activity_ordinal': 4,
            'send_if_activity': 'incomplete',  # or 'aborted' or 'completed'
            # this means send on the scheduled date
            'relative_date_to_send': -0,
            'reply_to': '',
            'from_address': '',
            'subject': 'You have a teacher session scheduled for today',
            'body': "Dear {{user.first_name}},"
                "\n\n"
                "This is a reminder that you have a Teacher Session today, {{ activity.scheduled_date }}. "
                "Please visit the teacher dashboard at <a href='https://www.studentspaths.org/login'>www.studentspaths.org/login</a> "
                "to download the instructions or to reschedule your class."
                "\n\n"
                "Warm regards,"
                "\n\n"
                "The PERTS Team"
        },
        {
            'activity_ordinal': 5,
            'send_if_activity': 'incomplete',  # or 'aborted' or 'completed'
            # this means send three days before schedule date
            'relative_date_to_send': -3,
            'reply_to': '',
            'from_address': '',
            'subject': 'You have a teacher session coming up in 3 days',
            'body': "Dear {{user.first_name}},"
                "\n\n"
                "This is a reminder that you have a Teacher Session in 3 days, {{ activity.scheduled_date }}. "
                "Please visit the teacher dashboard at <a href='https://www.studentspaths.org/login'>www.studentspaths.org/login</a> "
                "to download the instructions or to reschedule your class."
                "\n\n"
                "Warm regards,"
                "\n\n"
                "The PERTS Team"
        },
        {
            'activity_ordinal': 5,
            'send_if_activity': 'incomplete',  # or 'aborted' or 'completed'
            # this means send on the scheduled date
            'relative_date_to_send': -0,
            'reply_to': '',
            'from_address': '',
            'subject': 'You have a teacher session scheduled for today',
            'body': "Dear {{user.first_name}},"
                "\n\n"
                "This is a reminder that you have a Teacher Session today, {{ activity.scheduled_date }}. "
                "Please visit the teacher dashboard at <a href='https://www.studentspaths.org/login'>www.studentspaths.org/login</a> "
                "to download the instructions or to reschedule your class."
                "\n\n"
                "Warm regards,"
                "\n\n"
                "The PERTS Team"
        },
        {
            'activity_ordinal': 1,
            'send_if_activity': 'incomplete',  # or 'aborted' or 'completed'
            # this means send three days before schedule date
            'relative_date_to_send': -3,
            'reply_to': '',
            'from_address': '',
            'subject': 'You have a student session coming up in 3 days',
            'body': "Dear {{user.first_name}},"
                "\n\n"
                "This is a reminder that you have a Teacher Session in 3 days, {{ activity.scheduled_date }}. "
                "Please visit the teacher dashboard at <a href='https://www.studentspaths.org/login'>www.studentspaths.org/login</a> "
                "to download the instructions or to reschedule your class."
                "\n\n"
                "Warm regards,"
                "\n\n"
                "The PERTS Team"
        },
    ]
}
