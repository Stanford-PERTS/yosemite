"""Contains specialized classes which don't interact directly with users, don't
have many instances, and use human-readable key names."""

import calendar                                     # converts datetime to utc
import collections
import datetime
from google.appengine.ext import db
from google.appengine.ext.db.metadata import Kind   # Indexer
from google.appengine.api import search             # Indexer
from google.appengine.api import logservice         # ErrorChecker
from google.appengine.api import mail               # ErrorChecker
import itertools                                    # slicing streams
import json                                         # For CsvCache
import logging                                      # error logging
import re

import config
from core import *
from csv_file import CsvFile                        # For CsvCache
import util


class NamedModel(Model):
    """Ancestor for specialized entities that can be retrieved directly by
    knowing their key name. They do not have ids like core entities do.

    Example query:
    CsvCache.get_by_key_name('pd_all')
    """

    @classmethod
    def create(klass, **kwargs):
        if 'key_name' not in kwargs:
            raise Exception("NamedModel entities must have a key name.")
        return klass(**kwargs)

    def __str__(self):
        """A string represenation of the entity. Goal is to be readable.

        Returns, e.g. <core.Pd Pd_oha4tp8a4tph1>.
        Native implementation does nothing useful.
        """
        return '<named.{} "{}">'.format(
            self.__class__.__name__, self.key().name())

    def __repr__(self):
        """A unique representation of the entity. Goal is to be unambiguous.

        But our ids are unambiguous, so we can just forward to __str__.
        Native implemention returns a useless memory address.
        """
        return self.__str__()

    # special methods to allow comparing entities, even if they're different
    # instances according to python
    # https://groups.google.com/forum/?fromgroups=#!topic/google-appengine-python/uYneYzhIEzY
    def __eq__(self, value):
        """Allows entity == entity to be True if keys match.

        Is NOT called by `foo is bar`."""
        if self.__class__ == value.__class__:
            return str(self.key()) == str(value.key())
        else:
            return False

    # Because we defined the 'equals' method, eq, we must also be sure to
    # define the 'not equals' method, ne, otherwise you might get A == B is
    # True, and A != B is also True!
    def __ne__(self, value):
        """Allows entity != entity to be False if keys match."""
        if self.__class__ == value.__class__:
            # if they're the same class, compare their keys
            return str(self.key()) != str(value.key())
        else:
            # if they're not the same class, then it's definitely True that
            # they're not equal.
            return True

    def __hash__(self):
        """Allows entity in entity_list to be True."""
        return hash(str(self.key()))


class CsvCache(NamedModel):
    """Stubs for managing data caches that can be turned into csvs."""

    files = db.StringListProperty()
    last_checked = db.DateTimeProperty()

    # Temporary, in-memory storage of GCS data.
    _cache = []

    def name(self):
        return self.key().name()

    def to_list(self):
        """Turns csv_dict into a list that can easily become a csv.

        MEMORY INTENSIVE, should only be run on a cloud compute instance.
        """

        # This is the dangerous line; moving from a large string to an even
        # larger list takes a lot of RAM.
        json_entries = self._cache.split("\n")

        out = []
        if len(json_entries) > 0:
            # headers only included in the first bucket
            first = json.loads(json_entries.pop())
            headers = first.keys()
            first_row = first.values()
            out.append(headers)
            out.append(first_row)
            # table
            for pd_json in json_entries:
                out.append(json.loads(pd_json))
        return out

    def load(self, filename):
        """Retrieves serialized pd data from Google Cloud Storage."""
        global profiler
        file_path = self.name() + '/' + filename
        profiler.add_event("  Loading file...")
        gcs_file = CsvFile(file_path)
        profiler.add_event("  Loaded. Reading...")
        self._cache = gcs_file.read()
        profiler.add_event("  load() done")

    def append(self, entries, columns):
        """Adds data to cache.

        Data is not indexed and we don't worry about duplicate rows because
        they can be removed with R during analysis. Each pd is JSONed and
        written to a new line, so the file can be appended to without ever
        unserializing pre-existing data.
        """
        json_entries = []
        for pd_entity in entries:
            pd_dict = {k: unicode(v)
                       for k, v in pd_entity.to_dict().items()
                       if k in columns}
            pd_json = json.dumps(pd_dict)
            json_entries.append(pd_json)
        new_lines = "\n".join(json_entries)
        self._cache += "\n" + new_lines

    def save(self, filename):
        """Writes in-memory dictionary to GCS a JSON string."""
        global profiler
        file_path = self.name() + '/' + filename
        profiler.add_event("  Loading file...")
        gcs_file = CsvFile(file_path)
        profiler.add_event("  Loaded. Writing...")
        gcs_file.write(self._cache)
        self._cache = []
        gcs_file = None
        profiler.add_event("  save() done.")

    def update(self):
        """Figures out what new data exists, based on configuration settings
        for this cache, and updates the cache accordingly. Does not save."""

        global profiler
        profiler.clear()
        profiler.add_event("Starting fetch.")

        conf = config.csv_cache_settings[self.name()]

        # What entities are new and should be added to the csv?
        if not self.last_checked:
            self.last_checked = datetime.datetime(1970, 1, 1, 0, 0)
        klass = kind_to_class(conf['kind'])
        q = klass.all().filter('deleted =', False).filter('is_test =', False)
        q.filter(conf['newness_property'] + ' >', self.last_checked)
        q.order(conf['newness_property'])
        new_entities = q.fetch(conf['fetch_size'])

        profiler.add_event("Fetch complete, {} new entities.".format(len(new_entities)))

        updates_made = len(new_entities)

        if updates_made:
            if self.name() == 'pd_all':
                profiler.add_event("Beginning to index by cohort.")
                # index all the pd entities according to their cohort
                indexed_pds = {}
                for pd in new_entities:
                    if pd.cohort not in indexed_pds:
                        indexed_pds[pd.cohort] = []
                    indexed_pds[pd.cohort].append(pd)

                profiler.add_event("Pds indexed into {} cohorts.".format(
                    len(indexed_pds)))

                # write each cohort's pds to a different gcs file
                for cohort_id, pd_list in indexed_pds.items():
                    cohort_abbr = cohort_id[-3:]
                    profiler.add_event("Loading {}".format(cohort_abbr))
                    self.load(cohort_id)
                    profiler.add_event("Loading done. Appending {}.".format(cohort_abbr))
                    self.append(pd_list, conf['columns'])
                    profiler.add_event("Appending done. Saving {}.".format(cohort_abbr))
                    self.save(cohort_id)
                    profiler.add_event("Saving done.".format(cohort_abbr))

            elif self.name() == 'user_all':
                self.load('user_all')
                profiler.add_event("{} loaded.".format('user_all'))
                self.append(new_entities, conf['columns'])
                profiler.add_event("{} loaded.".format('user_all'))
                self.save('user_all')
                profiler.add_event("{} loaded.".format('user_all'))

            else:
                pass

            last = new_entities[-1]
            self.last_checked = getattr(last, conf['newness_property'])

        else:
            self.last_checked = datetime.datetime.now()

        self.put()
        profiler.add_event("CsvCache saved, script complete.")

        logging.info(profiler)

        return updates_made


class Timestamp(NamedModel):
    """Ultra-simple timestamp storage. Give it any name you like.

    Originally created to keep track of gradual processing of entities, like
    collecting and aggregating pds, or systematically updating user objects.
    """
    timestamp = db.DateTimeProperty()


class Aggregator(NamedModel):
    """Update aggregated statistics on student progress.

    ## Purpose

    "Complex writes for easy reads." We want summaries of complex tracking
    information available on the dashboard so researchers and school admins
    can review the progress of their respective participants.

    ## Design

    The Yosemite aggregation spider stores a timestamp will continually check
    for changes more recent than that timestamp. After completing a check, it
    sets the timestamp either to the current time (if no changes were found) or
    to the most recent change it found.

    The Aggregator is interested in two kinds of changes:

    1. New progress pds where the variable is of the form 'sX__progress', where
       X is the session number.
    2. Modified student entities. This is relevent if a student's certification
       status or participation code have changed.

    If it finds any changes like this, then the aggregator will start a three-
    tiered set up updates. Data from progress pds is summarized and stored with
    user entities. Those summaries are themselves summarized and stored with
    the related activities. This is done once again for cohorts.

    ## Known Inefficiency

    If a cohort has had multiple activity updates at different times, it will
    be re-summarized every time. Functionally, this should not be too big a
    problem since cohorts are small.
    """

    # Aggregator properties
    last_check = util.DictionaryProperty()

    def get_changed(self, kind):
        """Get all entities of a kind which have been modified recently."""
        # Fetch in smaller chunks to prevent the process from being too slow.
        fetch_size = 50
        if kind not in self.last_check or not self.last_check[kind]:
            self.last_check[kind] = datetime.datetime(1970, 1, 1, 0, 0)

        # Check for updated entities of specified kind.
        klass = kind_to_class(kind)

        query = klass.all().filter('is_test =', False)
        # Do NOT filter by deleted, b/c we want recently-deleted entities
        # to come up in this query as "changed", forcing their parent to
        # update their totals downward.
        if kind == 'pd':
            # The exception for this is pd, which uses deletion differently.
            # We never have a reason to pay attention to deleted pd (except
            # for manual debugging and data analysis). And, in fact, we never
            # want pd progress values to decrease.
            query.filter('deleted =', False)

        # This only applies to pds for now, which need public = True.
        if kind in config.kinds_with_get_filters:
            for filter_tuple in klass.get_filters():
                query.filter(*filter_tuple)

        query.filter('modified >', self.last_check[kind])
        query.order('modified')

        result = query.fetch(fetch_size)

        # Set last_check for where most recent update left off.
        if len(result) > 0:
            self.last_check[kind] = result[-1].modified
        else:
            self.last_check[kind] = datetime.datetime.now()

        return result

    def save(self, kind, changed_entities):
        """Save entities with their new aggregation data, but don't update
        their modified time.

        Otherwise, the aggregator would constantly be going over entities it
        had modified, rather than the ones we're really interested in.
        """

        for e in changed_entities:
            # Copy the aggregated_data property to a JSON-serialized one, which
            # we can analyze through BigQuery.
            e.aggregation_json = e.aggregation_data

            # Record that the aggregator touched this entity.
            e.aggregated = self.datetime()

        # Save w/o changing modified time and without caching rosters or
        # schedules. Memcache management will be done explicitly only on the
        # unique list of classrooms and cohorts modified, NOT on every User
        # and Activity.
        db.put(changed_entities, set_modified_time=False,
               memcache_management=False)

    def summarize_students(self, students, activity_ordinal):
        """Given all the students of an activity, sums up their data."""

        summary = {
            'n': 0,
            'completed': 0,
            'makeup_eligible': 0,
            'makeup_ineligible': 0,
            'uncoded': 0
        }

        for student in students:
            status_code1 = student.get_status_code(1)
            status_code2 = student.get_status_code(2)
            st1 = config.status_codes[status_code1] if status_code1 else {}
            st2 = config.status_codes[status_code2] if status_code2 else {}
            if (st1.get('exclude_from_counts', False) or
                st2.get('exclude_from_counts', False)):
                continue

            agg_data = student.aggregation_data[activity_ordinal]
            status_code = student.get_status_code(activity_ordinal)
            status = config.status_codes[status_code] if status_code else {}

            if status_code:
                if not status['study_eligible']:
                    # Don't count this student at all. Skip to next one.
                    continue

                if status['counts_as_completed']:
                    summary['completed'] += 1
                elif status['makeup_eligible']:
                    summary['makeup_eligible'] += 1
                else:
                    summary['makeup_ineligible'] += 1
            elif agg_data['progress'] >= 100:
                summary['completed'] += 1
            else:
                summary['uncoded'] += 1

            # Study ineligible students and exclude_from_count students are
            # not counted in this total b/c they exit the for loop higher up.
            summary['n'] += 1

        return summary

    def aggregate_to_users(self):
        """Calculate session progress and accounted_for status for users.

        'progress' is just a redundant storage of a student's progress pd
        value. This makes it easier to display the progress of many students at
        once without having to pull pd.

        'accounted_for' is true if a student's progress is 100 or if they have
        a participation status code that excuses them.

        TODO(chris): get these definitions into the Yosemite doc:
        https://docs.google.com/document/d/1tmZhuWMDX29zte6f0A8yXlSUvqluyMNEnFq8qyJq1pA).
        """
        # Some terminology:
        # changed_X: these things are around because the aggregator detected
        #     they have recent modifications; they come from
        #     aggregator.get_changed(kind).
        # referenced_X: these things are referenced by things that have
        #     changed. Often, they're around because we need to "back-query"
        #     stuff to get complete totals. They're not necessarily changed,
        #     but we have to roll them into our statistics because they're
        #     siblings of things that have changed, and we're summarizing all
        #     the children into the parent.

        # Trigger 1 of 2: modified pds which need to aggregate to their users.
        # E.g. a student's progress pd has increased.
        profiler.add_event('...get changed pd')
        changed_pds = self.get_changed('pd')

        # We only want user-related progress pds which have an activity ordinal
        # (some testing pds don't have an ordinal). Do some filtering.
        profiler.add_event('...process')
        referenced_user_ids = []
        changed_progress_pds = []
        for pd in changed_pds:
            is_user_pd = get_kind(pd.scope) == 'user'
            has_ordinal = isinstance(pd.activity_ordinal, (int, long))
            if pd.is_progress() and is_user_pd and has_ordinal:
                if pd.scope not in referenced_user_ids:
                    referenced_user_ids.append(pd.scope)
                changed_progress_pds.append(pd)

        if len(referenced_user_ids) > 0:
            referenced_users = User.get_by_id(referenced_user_ids)
        else:
            referenced_users = []

        # Trigger 2 of 2: modified users whose status codes may have changed.
        # E.g. a student is marked absent, "accounting for" their lack of
        # participation.
        profiler.add_event('...get changed users')
        changed_users = self.get_changed('user')

        # Unique list of users from both triggers.
        changed_users = list(set(changed_users + referenced_users))

        # Most aggregation runs will have nothing new to aggregate. Exit
        # quickly to save cpu load.
        if len(changed_users) is 0:
            return []

        # Now with all the data in hand, start summarizing it and storing it
        # in user entities.
        profiler.add_event('...process')
        pds_by_user = util.list_by(changed_progress_pds, 'scope')
        for user in changed_users:
            if user.id in pds_by_user:
                # Under normal operation, there should only be one active pd
                # per user per activity ordinal. But we've found evidence that
                # there may be several, due to inconsistent querying in
                # self.get_changed(). If there are multiple that might cause
                # incorrect aggregation, log an error, and
                # make sure to choose the highest progress value available.
                pds = pds_by_user[user.id]
                pds_by_ordinal = util.list_by(pds, 'activity_ordinal')
                if any([len(v) > 1 for v in pds_by_ordinal.values()]):
                    logging.warning(
                        "Multiple pds found in aggregation: {}"
                        .format(json.dumps([pd.to_dict() for pd in pds])))

                agg_data = {}
                for pd in pds:
                    # Record progress values by activity ordinal
                    o = pd.activity_ordinal
                    new_v = int(pd.value)

                    # Keep track of which ordinals we've seen before
                    if o in agg_data and new_v < agg_data[o]['progress']:
                        # See pull #306
                        logging.error(
                            "Out-of-order hypothesis confirmed! {}"
                            .format(pds_by_user[user.id]))
                    elif o not in agg_data:
                        agg_data[o] = {'progress': None}

                    # Only save the value if it's larger than the previous
                    # (only relevant when there are more than one).
                    current_v = agg_data[o]['progress']
                    if current_v is None or new_v > current_v:
                        agg_data[o]['progress'] = new_v

                    if new_v is 100 and user.get_status_code(o) is None:
                        # Also assign the status code "Completed" to this
                        # student. This is technically redundant, but makes
                        # the data clearer.
                        user.set_status_code(o, 'COM')

                # Copy compiled results into the user.
                for k, v in agg_data.items():
                    user.aggregation_data[k] = agg_data[k]

        # Save changes to users and the aggregator timestamp.
        profiler.add_event('...save users')
        self.save('user', changed_users)

        return changed_users

    def aggregate_to_activities(self, changed_users):
        """Calculate basic stats of users in an activity for reporting.

        For instance, a count of all users with progress 100 will be saved
        with the activity as aggregation_data['all']['completed']."""

        # Firm assumptions: these are enforced.
        # 1. We only want to aggregate student-users to student-type activities
        # Soft assumptions: violating these assumptions will log errors but
        # will not break the aggregator.
        # 1. All students have one associated classroom.
        changed_students = []
        students_breaking_assumptions = []
        for user in changed_users:
            if user.user_type == 'student':
                if len(user.assc_classroom_list) is 1:
                    changed_students.append(user)
                else:
                    students_breaking_assumptions.append(user)
        if len(students_breaking_assumptions) > 0:
            logging.error("Students with bad classroom associations: {}"
                          .format(students_breaking_assumptions))

        # Set up an index of users and activities by classroom (we'll need this
        # later).
        index = {}
        cohort_ids = []  # Get list of unique cohorts.
        for s in changed_students:
            cl_id = s.assc_classroom_list[0]
            if cl_id not in index:
                index[cl_id] = {'students': [], 'activities': []}
            co_id = s.assc_cohort_list[0]
            if co_id not in cohort_ids:
                cohort_ids.append(co_id)
        classroom_ids = index.keys()

        if len(classroom_ids) is 0:
            return []

        # Activities don't store relationships with users directly. To find
        # them, query via classroom ids.
        profiler.add_event('...get related activities')
        query = Activity.all().filter('deleted =', False)
        query.filter('is_test =', False)
        query.filter('user_type =', 'student')

        if len(classroom_ids) < 30:
            # Don't filter by classroom id directly, because there may be more
            # than 30. Filter the query by cohort, then further filter by
            # classroom in-memory.
            logging.info(
                "Using normal classroom query for classroom activities")
            query.filter('assc_classroom_list IN', classroom_ids)
            fetched_activities = query.run()
        else:
            logging.info(
                "> 30 classrooms: Using cohort query for classroom activities")
            query.filter('assc_cohort_list IN', cohort_ids)
            fetched_activities = [a for a in query.run()
                                  if a.assc_classroom_list[0] in classroom_ids]

        # Soft assumptions: violating these assumptions will log errors but
        # will not break the aggregator.
        # 1. All student activities have one associated classroom.
        profiler.add_event('...process')
        referenced_activities = []
        activities_breaking_assumptions = []
        for a in fetched_activities:
            if len(a.assc_classroom_list) is 1:
                referenced_activities.append(a)
            else:
                activities_breaking_assumptions.append(a)
        if len(activities_breaking_assumptions) > 0:
            logging.error("Activities with bad classroom associations: {}"
                          .format(activities_breaking_assumptions))

        # Add the activities to the index.
        for a in referenced_activities:
            cl_id = a.assc_classroom_list[0]
            index[cl_id]['activities'].append(a)

        # Re-query users for these classrooms so we can calculate the total
        # number of students per classroom not just the change in number of
        # students per classroom.
        profiler.add_event('...get related users')
        query = User.all().filter('deleted =', False)
        query.filter('is_test =', False)
        query.filter('user_type =', 'student')

        if len(classroom_ids) < 30:
            # Don't filter by classroom id directly, because there may be more
            # than 30. Filter the query by cohort, then further filter by
            # classroom in-memory.
            logging.info("Using normal classroom query for activity users")
            query.filter('assc_classroom_list IN', classroom_ids)
            referenced_students = query.run()
        else:
            logging.info(
                "> 30 classrooms: using cohort query for activity users")
            query.filter('assc_cohort_list IN', cohort_ids)
            referenced_students = [
                u for u in query.run()
                if u.assc_classroom_list[0] in classroom_ids]

        # Add the students to the index.
        profiler.add_event('...process')
        changed_student_index = {s.id: s for s in changed_students}
        for s in referenced_students:
            # Important: some of these users *just changed*, i.e. just had
            # their aggregation modified and have been passed in to this
            # function as changed_students. They may be more up to date than
            # the version of the same entity returned by they query.
            if s.id in changed_student_index:
                # So, when possible, prefer the already-in-memory version.
                s = changed_student_index[s.id]

            status_code1 = s.get_status_code(1)
            st1 = config.status_codes[status_code1] if status_code1 else {}
            status_code2 = s.get_status_code(2)
            st2 = config.status_codes[status_code2] if status_code2 else {}
            if (st1.get('exclude_from_counts', False) or
                st2.get('exclude_from_counts', False)):
                # Don't count this student at all, even in gross totals.
                continue
            cl_id = s.assc_classroom_list[0]
            index[cl_id]['students'].append(s)

        # Iterate over activities, calculating stats based on the related set
        # of users.
        # See the summarize_students() method and/or the docs:
        # https://docs.google.com/document/d/1tmZhuWMDX29zte6f0A8yXlSUvqluyMNEnFq8qyJq1pA
        for classroom_id, d in index.items():
            for a in d['activities']:
                a.aggregation_data['total_students'] = len(d['students'])

                cert_students = [s for s in d['students'] if s.certified]
                a.aggregation_data['certified_students'] = len(cert_students)

                s = self.summarize_students(cert_students, a.activity_ordinal)
                a.aggregation_data['certified_study_eligible_dict'] = s

        profiler.add_event('...save activities')
        self.save('activity', referenced_activities)

        # Cache new classroom rosters for all modified classrooms.
        for cl_id in classroom_ids:
            logging.info("Aggregator queueing roster tasks for "
                         "classroom {}.".format(cl_id))
            memcache.delete(cl_id + '_roster')
            util.add_eventually_consistent_task('/task/cache_roster/' + cl_id)

        return referenced_activities

    def aggregate_to_cohorts(self, changed_activities):
        """Summarize activity-stats at the cohort level."""
        # Query for activities whose scheduled_date may have changed.
        # Combine it with the changed activities that were passed in,
        # preferring in-memory versions where there are overlaps.
        changed_activity_index = {a.id: a for a in changed_activities}
        for a in self.get_changed('activity'):
            if a.id not in changed_activity_index:
                changed_activity_index[a.id] = a

        # What cohorts need to be updated based on the changed activities?
        cohort_ids = list(set([a.assc_cohort_list[0]
                               for a in changed_activity_index.values()]))
        if len(cohort_ids) is 0:
            return []
        profiler.add_event('...get related cohorts')
        referenced_cohorts = Cohort.get_by_id(cohort_ids)  # speedy key fetch

        # Index cohorts by id for easy reference. Also reset their aggregation
        # data so it has the proper structure but is full of zeroes.
        profiler.add_event('...process')
        cohort_index = {}
        for c in referenced_cohorts:
            cohort_index[c.id] = c
            c.aggregation_data = copy.deepcopy(
                Cohort.aggregation_data.default)

        # Re-query for all activities in these cohorts so we can calculate true
        # totals, not just incremental changes.
        profiler.add_event('...get related activities')
        query = Activity.all().filter('deleted =', False)
        query.filter('is_test =', False)
        query.filter('user_type =', 'student')
        query.filter('assc_cohort_list IN', cohort_ids)
        referenced_activities = query.run()

        # Iterate over activities, incrementing cohort values.
        profiler.add_event('...process')
        for a in referenced_activities:
            # Prefer recently-changed, in-memory entities
            if a.id in changed_activity_index:
                a = changed_activity_index[a.id]

            a_agg = a.aggregation_data
            cohort = cohort_index[a.assc_cohort_list[0]]
            c_agg = cohort.aggregation_data[a.activity_ordinal]

            # Count incomplete rosters.
            if not a.roster_complete:
                c_agg['incomplete_rosters'] += 1

            # Store activity status.
            c_agg[a.interpreted_status()] += 1

            # Store student counts.
            c_agg['total_students'] += a_agg['total_students']
            c_agg['certified_students'] += a_agg['certified_students']

            # Count all the certified study eligible stats.
            for variable, value in a_agg['certified_study_eligible_dict'].items():
                c_agg['certified_study_eligible_dict'][variable] += value

        profiler.add_event('...save cohorts')
        self.save('cohort', referenced_cohorts)

        # Cache new cohort rosters and schedules for all modified cohorts.
        for c_id in cohort_ids:
            logging.info("Aggregator queueing roster and schedule tasks for "
                         "cohort {}.".format(c_id))
            memcache.delete(c_id + '_roster')
            util.add_eventually_consistent_task('/task/cache_roster/' + c_id)
            memcache.delete(c_id + '_schedule')
            util.add_eventually_consistent_task('/task/cache_schedule/' + c_id)

        return referenced_cohorts


class Indexer(NamedModel):
    """
    Update entity search data store

    Design
    The indexer will find entities which have changed and add them
    to the entity index.

    orginal author
    bmh September 2013
    """

    # Data
    last_check = db.DateTimeProperty()
    # Do not search
    blacklist = [
        'Aggregator',         # boring
        'Pd',                 # personal
        'Indexer',            # boring
        'QualtricsLink',      # boring
        # 'ErrorChecker',       # boring
        'Stratifier',         # boring
        'StratifierHistory',  # boring
    ]
    # Limit the number of items we are willing to index
    max_entities_to_index = 10

    doc_id_leading_char = re.compile(r'[A-Za-z]')
    doc_id_valid_char = re.compile(r'[A-Za-z0-9_]')

    def get_index(self):
        return search.Index(name='index')

    def get_changed_entities(self):

        # get classes
        # not blacklisted
        klass_names = [
            k.kind_name
            for k in Kind.all()
            if k.kind_name not in self.blacklist
        ]

        # check for cases where the Klass cannot be converted (KeyError)
        # this happens in production for reasons I don't understand
        # bmh 2013
        Klasses = []
        for k in klass_names:
            try:
                Klass = kind_to_class(k)
            except AttributeError:
                pass
            else:
                Klasses.append(Klass)

        # get entites
        if not self.last_check:
            self.last_check = 0

        entities = [
            e
            for Klass in Klasses
            for e in Klass.all().filter(
                "modified > ", self.last_check
                ).order("modified").fetch(self.max_entities_to_index)
        ]

        return entities

    def entity_to_document(self, entity):
        doc = search.Document(
            doc_id=self.clean_doc_id(entity.key().name()),
            fields=[
                search.TextField(name=self.clean_doc_id(key),
                                 value=unicode(value))
                for key, value
                in entity.to_dict().items()
            ]
        )
        return doc

    def clean_doc_id(self, string):
        """Make sure any strings going into the indexer are properly formed."""
        doc_id_leading_char = r'^[^A-Za-z]*'
        doc_id_valid_char = r'[^A-Za-z0-9_]'
        # Get rid of any unicode
        ascii_string = string.encode('ascii', 'ignore')
        # Get rid of chars that are gobally wrong.
        partially_clean = re.sub(doc_id_valid_char, '', ascii_string)
        # Get rid of all chars from the beginning up to the first valid lead
        # char.
        clean_string = re.sub(doc_id_leading_char, '', partially_clean)
        return clean_string


class ErrorChecker(NamedModel):
    """
    Check for recent errors using log api

    Design
    The error checker will keep track of how long it has been since a check
    occured and how long since an email alert was sent.

    It will also facilite searching the error log.

    orginal author
    bmh October 2013
    """

    # constants
    # How long will we wait between emails?
    minimum_seconds_between_emails = 60 * 60  # 1 hour
    maximum_requests_to_email = 100     # how long can the log be
    maximum_entries_per_request = 100   # how long can the log be

    # error levels
    level_map = collections.defaultdict(lambda x: 'UNKNOWN')
    level_map[logservice.LOG_LEVEL_DEBUG] = 'DEBUG'
    level_map[logservice.LOG_LEVEL_INFO] = 'INFO'
    level_map[logservice.LOG_LEVEL_WARNING] = 'WARNING'
    level_map[logservice.LOG_LEVEL_ERROR] = 'ERROR'
    level_map[logservice.LOG_LEVEL_CRITICAL] = 'CRITICAL'

    # email stuff
    to_address = config.to_dev_team_email_address
    from_address = config.from_yosemite_email_address
    subject = "Error(s) during calls to: "
    body = """
Cptn. Kirk,

Get Spock, his rocket boots are needed.

More information is available on the dashboard

    https://appengine.google.com/logs?app_id=s~pegasusplatform&severity_level_override=0&severity_level=3

your humble national park,

Yosemite

"""

    # Data
    last_check = db.DateTimeProperty()
    last_email = db.DateTimeProperty()

    def to_unix_time(self, dt):
        return calendar.timegm( dt.timetuple() )

    def to_utc_time(self, unix_time):
        return datetime.datetime.utcfromtimestamp(unix_time)

    def any_new_errors(self):
        since = self.last_check if self.last_check else self.datetime()
        log_stream = logservice.fetch(
            start_time = self.to_unix_time( since ),
            minimum_log_level = logservice.LOG_LEVEL_ERROR
        )

        return next(iter(log_stream), None) is not None

    def get_recent_log(self):
        """ see api
        https://developers.google.com/appengine/docs/python/logs/functions
        """
        out = ""
        since = self.last_check if self.last_check else self.datetime()
        log_stream = logservice.fetch(
            start_time = self.to_unix_time( since ),
            minimum_log_level = logservice.LOG_LEVEL_ERROR,
            include_app_logs = True
        )
        requests = itertools.islice(log_stream, 0, self.maximum_requests_to_email)

        for r in requests:
            log = itertools.islice(r.app_logs, 0, self.maximum_entries_per_request)
            log = [
                self.level_map[l.level] + '\t' +
                str(self.to_utc_time(l.time)) + '\t' +
                l.message + '\n'
                for l in log
            ]
            out = out + r.combined + '\n' + ''.join(log) + '\n\n'

        return out

    def get_error_summary(self):
        """ A short high level overview of the error.

        This was designed to serve as the email subject line so that
        developers could quickly see if an error was a new type of error.

        It returns the resources that were requested as a comma
        seperated string:
        e.g.

            /api/put/pd, /api/...

        see google api
        https://developers.google.com/appengine/docs/python/logs/functions
        """
        # Get a record of all the requests which generated an error
        # since the last check was performed, typically this will be
        # at most one error, but we don't want to ignore other errors if
        # they occurred.
        since = self.last_check if self.last_check else self.datetime()
        log_stream = logservice.fetch(
            start_time=self.to_unix_time(since),
            minimum_log_level=logservice.LOG_LEVEL_ERROR,
            include_app_logs=True
        )
        # Limit the maximum number of errors that will be processed
        # to avoid insane behavior that should never happen, like
        # emailing a report with a googleplex error messages.
        requests = itertools.islice(
            log_stream, 0, self.maximum_requests_to_email
        )

        # This should return a list of any requested resources
        # that led to an error.  Usually there will only be one.
        # for example:
        #   /api/put/pd
        # or
        #   /api/put/pd, /api/another_call
        out = ', '.join(set([r.resource for r in requests]))

        return out

    def should_email(self):
        since_last = ( self.datetime() - self.last_email ).seconds if self.last_email else 10000000
        return since_last > self.minimum_seconds_between_emails

    def mail_log(self):
        body = self.body + self.get_recent_log()
        subject = self.subject + self.get_error_summary()

        if util.is_development():
            logging.warning("This is a development environment."
                            "Mail NOT really sent.")
        else:
            mail.send_mail(self.from_address, self.to_address, subject, body)

        self.last_email = self.now
        return (subject, body)

    def check(self):
        self.now = self.datetime()
        should_email = self.should_email()
        new_errors = self.any_new_errors()

        # check for errors
        if new_errors and should_email:
            message = self.mail_log()
        else:
            message = None

        logging.info("any_new_errors: {}, should_email: {}, message: {}"
                     .format(new_errors, should_email, 'None' if message is None else message[0]))

        self.last_check = self.now

        # TODO(benjaminhaley) this should return simpler output, ala
        #                     chris's complaint https://github.com/daveponet/pegasus/pull/197/files#diff-281842ae8036e3fcb830df255cd15610R663
        return {
            'email content': message,
            'checked for new errors': should_email
        }


class QualtricsLink(NamedModel):
    """Unique Links class for Qualtrics Survey.
       Contains information to match to the survey,
       and the link itself. The key_name is part of
       the link that is unique, namely the final 15
       chars of the link. The full
    """
    # Links correspond to a specific session, specified here by ordinal.
    session_ordinal = db.IntegerProperty()
    # The body of the link:
    link = db.StringProperty()

    @classmethod
    def get_link(klass, session_ordinal):

        @db.transactional
        def _get_link_transactional(key):

            link = db.get(key)
            if link is None:
                raise db.TransactionFailedError()
            rawlink = link.link
            db.delete(link)
            return rawlink

        # Fetch
        query = QualtricsLink.all().order('link')
        query.filter('session_ordinal =', session_ordinal)

        # Notify devs if running low on Qualtrics Links
        if query.count() < 1000:
            logging.error('Running low on Qualtrics Links! Import more soon!')

        link_keys = query.fetch(50, keys_only=True)

        # TODO: change these dummy links at 739, 753 to real link values
        if not link_keys:
            logging.error('Out of links! Returning default survey link!')
            return config.default_qualtrics_links[session_ordinal]

        # Verify link's existence
        raw_link = None
        for key in link_keys:
            try:
                raw_link = _get_link_transactional(key)
                break
            except db.TransactionFailedError:
                continue

        # Catch if raw_link is empty
        if not raw_link:
            logging.error('Something went wrong with Qualtrics association!')
            logging.error('Assigning user default link!')
            raw_link = config.default_qualtrics_links[session_ordinal]

        return raw_link
