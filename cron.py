"""Cron job code."""

from csv_file import CsvFile
from google.appengine.ext import db
from google.appengine.api import memcache
import collections
import copy
import pickle
import pprint
import sys
import time

from core import *
from named import *


class Cron:
    """A collection of functions and a permission scheme for running cron jobs.

    Very similar to api.Api."""

    def __init__(self, api):
        """Requires an api object with the appropriate level of permissions.
        Generally this should be god-level.
        See cron_handlers.CronHandler.do_wrapper()"""
        self.api = api

    def aggregate(self):
        """Aggregate participant data by activity and user.

        Must be called with internal_api for full permissions. See
        core@Aggregate for full description.
        """
        profiler.clear()

        aggregator = Aggregator.get_or_insert('the aggregator')

        profiler.add_event('Agg to users')
        changed_users = aggregator.aggregate_to_users()
        profiler.add_event('Agg to activities')
        changed_activities = aggregator.aggregate_to_activities(changed_users)
        profiler.add_event('Agg to cohorts')
        changed_cohorts = aggregator.aggregate_to_cohorts(changed_activities)

        profiler.add_event('Complete')
        
        # Don't put the aggregator until end in case of error.
        aggregator.put()

        output = {
            'updated_users': len(changed_users),
            'user_ids': [u.id for u in changed_users],
            'updated_activities': len(changed_activities),
            'activity_ids': [a.id for a in changed_activities],
            'updated_cohorts': len(changed_cohorts),
            'cohort_ids': [c.id for c in changed_cohorts],
            'last_check': {kind: time.strftime("%Y-%m-%d %H:%M:%S")
                           for kind, time in aggregator.last_check.items()},
        }

        logging.info(profiler)
        logging.info(output)

        return output

    def index(self):
        """Index entities for text search.
        Must be called with internal_api for full permissions.
        See core@Index for full description.
        """

        indexer = Indexer.get_or_insert('the indexer')
        index = indexer.get_index()
        # Now and the max modified time of indexed entites
        # will be used to update last_check.  Basically the
        # last check should either be now time if no items
        # were found to update or the age of the last item
        # that was updated.
        #
        # The reason that we cannot always use now time is
        # because we may not index all of the enties between
        # the last check and now if there are many of them.
        now = indexer.datetime()
        max_modified_time_of_indexed_entity = None

        # get changes
        changed_entities = indexer.get_changed_entities()

        # post changes
        for entity in changed_entities:
            try:
                indexer_entity = indexer.entity_to_document(entity)
                index.put(indexer_entity)
            except:
                time.sleep(2)
                indexer_entity = indexer.entity_to_document(entity)
                index.put(indexer_entity)

            # Update the most recent modification time for an
            # indexed entity
            if max_modified_time_of_indexed_entity is None:
                max_modified_time_of_indexed_entity = entity.modified
            else:
                max_modified_time_of_indexed_entity = max(
                    max_modified_time_of_indexed_entity,
                    entity.modified
                )

        # Update last_check so that future calls to index no longer
        # try to index these same items.  The logic of what to set
        # last_check to is articulated above.
        any_updates = max_modified_time_of_indexed_entity is not None
        indexer.last_check = (
            now if not
            any_updates
            else max_modified_time_of_indexed_entity
        )
        indexer.put()

        return {'success': True}

    def check_for_errors(self):
        """Check for new errors - email on error.
        Must be called with internal_api for full permissions.
        See core@Index for full description.
        """

        checker = ErrorChecker.get_or_insert('the error checker')
        result = checker.check()
        checker.put()
        return result

    def send_pending_email(self):
        """Send any email in the queue.
        Must be called with internal_api for full permissions.
        See core@Email for full description.
        """
        result = Email.send_pending_email()
        return {'message': result}

    def send_reminders(self):
        """Check for teachers that need reminders and add them to the email
        queue.
        See core@Reminder for details.
        """

        # already sent?
        # check if today's reminders have already been sent
        # if so, return.
        today = Reminder.get_pst_date()
        already_queued = self.api.get('Reminder', {'pst_date': today.isoformat()})
        if already_queued:
            return {'message': 'Reminders already queued to email'}

        # get reminders
        reminders = self.get_reminders_by_date(today.isoformat())

        # send a summary to perts admins
        self._send_reminder_summary(reminders)

        # queue emails
        for r in reminders:

            to = r['to_address'] or config.to_dev_team_email_address

            email = Email.create(
                to_address=to,
                reply_to=r['reply_to'],
                from_address=r['from_address'],
                subject=r['subject'],
                body=r['body']
            )

            email.put()

        # save as already sent
        todays_reminder = Reminder.create(
            pst_date=today.isoformat()
        )
        todays_reminder.put()

        return {
            'message': 'Reminders sent',
            'reminders': reminders,
            'date': today.isoformat()
        }

    def get_reminders_by_date(self, date_string=None):
        emails_by_user = collections.defaultdict(list)

        # render each unsent reminder
        for program in Program.list_all():
            for user_type in ['student', 'teacher']:
                for reminder in program.get_reminders(user_type):
                    new_emails = self._get_emails_from_reminder(
                        date_string, program, user_type, reminder)
                    for user_id, emails in new_emails.items():
                        emails_by_user[user_id] += emails

        # consolidate
        # If a user has more than one message then they should be merged into a
        # single message.
        merged = {}
        for user_id, emails in emails_by_user.items():
            merged[user_id] = Reminder.merge_multiple_emails(emails)

        return merged.values()

    def _get_emails_from_reminder(self, date_string, program, user_type, reminder):
        # date that activity must be scheduled for to recieve this
        # reminder; this will be used to filter the activities
        date = Reminder.get_pst_date(
            date_string=date_string,
            offset=-reminder['relative_date_to_send']
        )

        # activities
        # find activities for this program and user_type scheduled
        # on a date that requires sending a reminder.
        activities = self.api.get('activity', {
            'scheduled_date': date,
            'assc_program_list': program.id,
            'user_type': user_type,
            'activity_ordinal': reminder['activity_ordinal'],
            'status': reminder['send_if_activity']
        })

        if len(activities) is 0:
            return {}

        # classrooms
        # we'll need these to render classroom names in emails
        classroom_ids = [a.assc_classroom_list[0] for a in activities]
        classroom_dict = {c.id: c for c in Classroom.get_by_id(classroom_ids)}

        # cohorts (school_admins)
        # Organize the relevant activities by what cohort they're in, so we
        # can send summary emails to the school_admins of those cohorts.
        activities_by_cohort = collections.defaultdict(list)
        for a in activities:
            activities_by_cohort[a.assc_cohort_list[0]].append(a)
        cohort_ids = activities_by_cohort.keys()

        # There could be a lot of cohorts here, which may exceed the limit
        # of 30 subqueries. Api.get() can handle it, but it does so by post-
        # processing a larger (simpler) query. To prevent that larger query
        # from including ALL users (expensive, memory-intensive), include the
        # user type parameter, which otherwise probably isn't necessary.
        admins = self.api.get('user', {
            'owned_cohort_list': cohort_ids,
            'user_type': 'school_admin',
        })

        admins_by_cohort = collections.defaultdict(list)
        for admin in admins:
            for cohort_id in admin.owned_cohort_list:
                admins_by_cohort[cohort_id].append(admin)

        # email
        # Render the email for each relevant reminder.
        # Organize by user to make it easy to consolidate.
        # Deep copy the reminder to prevent it from getting
        # modified by subsequent calls.
        emails = collections.defaultdict(list)
        for activity in activities:
            classroom = classroom_dict[activity.assc_classroom_list[0]]
            cohort_id = activity.assc_cohort_list[0]
            for admin in admins_by_cohort[cohort_id]:
                email = Reminder.render_reminder(
                    copy.deepcopy(reminder), admin, activity, classroom)
                emails[admin.id].append(email)

        return emails

    def _send_reminder_summary(self, emails):
        # send summary to ICF
        body = config.admin_reminder_summary_body
        if len(emails) > 0:
            for e in emails:
                body += "\n----\n\nTo: {}  \nSubject: {}\n\n{}".format(
                    e['to_address'], e['subject'], e['body'])
        else:
            body += "\n----\n\nNo reminders today."

        to_list = [config.to_dev_team_email_address,
                   '']
        summary = Email.create(
            to_address=", ".join(to_list),
            from_address=config.from_yosemite_email_address,
            subject=config.admin_reminder_summary_subject,
            body=body,
            template_data={'emails': emails}
        )
        summary.put()

    def clean_gcs_bucket(self, bucket):
        """Deletes all files in a given GCS bucket. Used for emptying out
        cluttered buckets, like our backup buckets."""

        bucket_files = CsvFile.list_bucket_files(bucket)
        messages = {}

        for filename in bucket_files:
            msg = CsvFile.delete(filename)
            messages[filename] = msg

        return messages
