"""API Layer

All code considered outside the core platform (like URLs, program apps, etc.)
must interact with the platform via these function calls. All interaction with
the Datastore also happens through these functions. This is where permissions
are enforced. Expect calls to raise exceptions if things go wrong.
"""

from google.appengine.api import memcache
import cloudstorage as gcs
import csv
import datetime  # for checking reset password tokens
import logging
import markdown
import pickle
import random
import sys

from core import *
from cron import *
from named import *
import config
import sharding
import util


class Api:
    """The set of functions through which the outside world interacts with
    pegasus.

    Designed to be instantiated in the context of a user. Who the user is
    and what relationships they have determine how permissions are enforced.
    """

    def __init__(self, user):
        """Create an interface to pegasus.

        Args:
            user: core.User, who is making the api request
        """
        self.user = user

    @classmethod
    def post_process(klass, results, unsafe_filters):
        """Assumes IN filters with list values, e.g. ('id IN', ['X', 'Y'])."""
        logging.info('Api.post_process() handled unsafe filters:')
        logging.info('{}'.format(unsafe_filters))
        all_matching_sets = []
        for filter_tuple in unsafe_filters:
            p = filter_tuple[0].split(' ')[0]
            values = filter_tuple[1]
            matches = set([e for e in results if getattr(e, p) in values])
            all_matching_sets.append(matches)
        return set.intersection(*all_matching_sets)

    @classmethod
    def limit_subqueries(klass, filters):
        # GAE limits us to 30 subqueries! This is a BIG problem, because
        # stacking 'property IN list' filters MULTIPLIES the number of
        # subqueries (since IN is shorthand for a bunch of = comparisions). My
        # temporary solution is to detect unwieldy queries and do some post-
        # processing in python.
        # https://groups.google.com/forum/#!topic/google-appengine-python/ZlqZHwfznbQ
        subqueries = 1
        safe_filters = []
        unsafe_filters = []
        in_filters = []
        for filter_tuple in filters:
            if filter_tuple[0][-2:] == 'IN':
                subqueries *= len(filter_tuple[1])
                in_filters.append(filter_tuple)
            else:
                safe_filters.append(filter_tuple)
        if subqueries > 30:
            # mark in_filters as unsafe one by one, starting with the largest,
            # until subqueries is small enough
            s = subqueries
            for f in sorted(in_filters, key=lambda f: len(f[1]), reverse=True):
                if s < 30:
                    safe_filters.append(f)
                else:
                    unsafe_filters.append(f)
                s /= len(f[1])
        else:
            safe_filters += in_filters
        if len(unsafe_filters) > 0:
            logging.info('Api.limit_subqueries() marked filters as unsafe '
                         'because they would generate too many subqueries:')
            logging.info('{}'.format(unsafe_filters))
        return (safe_filters, unsafe_filters)

    def see(self, kind, kwargs):
        if 'n' in kwargs:
            n = kwargs['n']
            del(kwargs['n'])
        else:
            n = 1000

        # Although we almost always want to 'see' the entity's name, sometimes
        # want to specify a different property, like email. Allow this via the
        # 'see' key word.
        if 'see' in kwargs:
            projection = kwargs['see']
            del(kwargs['see'])
        else:
            projection = 'name'

        permissions_filters = self.user.get_permission_filters(kind, 'see')
        # request_filters = [(k + ' =', v) for k, v in kwargs.items()]
        request_filters = []
        for k, v in kwargs.items():
            operator = ' IN' if type(v) is list else ' ='
            request_filters.append((k + operator, v))

        logging.info('Api.see(kind={}, kwargs={})'.format(kind, kwargs))
        logging.info('permission filters: {}'.format(permissions_filters))
        logging.info('request filters: {}'.format(request_filters))

        filters = permissions_filters + request_filters
        klass = kind_to_class(kind)
        safe_filters, unsafe_filters = Api.limit_subqueries(filters)

        # Projection queries are nice and efficient for 'see' b/c they only
        # return what you're looking for (name and id), but they won't work if
        # you are filtering on the same thing you're projecting (see
        # https://developers.google.com/appengine/docs/python/datastore/projectionqueries#Python_Limitations_on_projections)
        # so fork into one of two modes: projection when not filtering by name,
        # and regular otherwise.
        # Also, post processing on projection results doesn't work because
        # python can't introspect the entity's properties.
        if 'name' in kwargs or len(unsafe_filters) > 0:
            # regular-type query
            query = klass.all().filter('deleted =', False)
        else:
            # projection query
            query = db.Query(klass, projection=[projection])
            query.filter('deleted =', False)
        for filter_tuple in safe_filters:
            query.filter(*filter_tuple)
        results = query.fetch(n)

        if len(unsafe_filters) > 0:
            results = Api.post_process(results, unsafe_filters)
        return [{'id': e.key().name(), projection: getattr(e, projection)}
                for e in results]

    def get(self, kind, kwargs, ancestor=None):
        """Query entities in the datastore.

        Specify an ancestor to make an "ancestor query": a query limited to
        one entity group which is strongly consistent.

        * Applies query filters based on what permissions the user has.
        * Works around App Engine limitations for complex queries.
        * Calls class startup methods, allowing on-instantiation code execution
        """
        if 'n' in kwargs:
            n = int(kwargs['n'])
            del(kwargs['n'])
        else:
            n = 1000

        if 'order' in kwargs:
            order = kwargs['order']
            del(kwargs['order'])
        else:
            order = None

        permissions_filters = self.user.get_permission_filters(kind, 'get')
        # request_filters = [(k + ' =', v) for k, v in kwargs.items()]
        request_filters = []
        for k, v in kwargs.items():
            operator = ' IN' if type(v) is list else ' ='
            request_filters.append((k + operator, v))

        logging.info('Api.get(kind={}, kwargs={}, ancestor={})'
                     .format(kind, kwargs, ancestor))
        logging.info('permission filters: {}'.format(permissions_filters))
        logging.info('request filters: {}'.format(request_filters))

        filters = permissions_filters + request_filters
        klass = kind_to_class(kind)
        query = klass.all().filter('deleted =', False)

        if order:
            query.order(order)

        if isinstance(ancestor, Model):
            query.ancestor(ancestor)

        if kind in config.kinds_with_get_filters:
            filters = filters + klass.get_filters()

        safe_filters, unsafe_filters = Api.limit_subqueries(filters)

        # build the query
        for filter_tuple in safe_filters:
            query.filter(*filter_tuple)
        # get full, in-memory entities
        results = query.fetch(n)
        # post-processing, if necessary
        if len(unsafe_filters) > 0:
            results = Api.post_process(results, unsafe_filters)

        # run custom startup code, if such behavior is defined
        for e in results:
            if hasattr(e, 'startup'):
                e.startup()

        return results

    def get_from_path(self, kind, id):
        results = self.get(kind, {'id': id})
        if len(results) is not 1:
            raise IdError()
        return results[0]

    def see_by_ids(self, ids):
        grouped_ids = {}
        for id in ids:
            kind = get_kind(id)
            if kind not in grouped_ids:
                grouped_ids[kind] = []
            grouped_ids[kind].append(id)
        results = []
        for kind, ids in grouped_ids.items():
            results += self.see(kind, {'id': ids})
        return results

    def get_by_ids(self, ids):
        grouped_ids = {}
        for id in ids:
            kind = get_kind(id)
            if kind not in grouped_ids:
                grouped_ids[kind] = []
            grouped_ids[kind].append(id)
        results = []
        for kind, ids in grouped_ids.items():
            results += self.get(kind, {'id': ids})
        return results

    def get_roster(self, entity_id, allow_memcache_retrieval=True):
        """Get user information for the school and classroom roster UI.

        Uses memcache if an appropriate key is found. These keys are populated
        from this function any time a trip to the datastore is required. A
        cronjob calls this function every few minutes to maximize the chances
        that the memcache keys are availble. Keys are erased any time a user
        within the respective cohort or classroom is written to or created to
        ensure that memcache data is never out of date.

        Args:
            entity_id: str, the id of the Cohort or Classroom for which we're
                looking up students.
            allow_memcache_retrieval: bool, default True, whether we allow
                ourselves to return results from memcache. Setting to False
                forces the function to visit the datastore and refresh memcache
                with the results. Used in re-caching task workers. See
                task_handlers.py

        Returns:
            Tuple of:
                results: list of dictionaries, each an abbreviated set of info
                    on a user (only the stuff req'd for the roster view)
                from_memcache: bool, whether the results were pulled from
                    memcache (True) or the datastore (False).
        """
        # Wrangle some search parameters.
        classroom_params = {'is_test': False, 'is_archived': False}
        user_params = {'is_test': False, 'is_archived': False,
                      'user_type': 'student', 'order': 'last_name'}
        kind = get_kind(entity_id)
        roster_key = entity_id + '_roster'
        if kind == 'cohort':
            classroom_params['assc_cohort_list'] = entity_id
            user_params['assc_cohort_list'] = entity_id
        elif kind == 'classroom':
            classroom_params['id'] = entity_id
            user_params['assc_classroom_list'] = entity_id

        # Check if the query results are in memcache. Note that we should be
        # able to trust that any data in memcache is fresh as other code is
        # responsible for clearing the cache if state changes.
        result_dicts = memcache.get(roster_key)

        if result_dicts and allow_memcache_retrieval:
            logging.info("Got results from memcache.")
            return (result_dicts, True)  # True means results are from memcache
        elif not allow_memcache_retrieval:
            logging.info("Memcache results disallowed. Forced to use "
                         "datastore and refresh memcache.")
        else:
            logging.info("Nothing found in memcache: {}".format(roster_key))

        # If the results weren't found in memcache, we need to run the query
        # against the datastore.
        results = self.get('user', user_params)

        def s(e):
            n = getattr(e, 'last_name', None)
            return n.lower() if n else None

        sorted_results = sorted(results, key=s)
        result_dicts = [e.to_roster_dict() for e in sorted_results]

        # We'll want the classroom names as well. Useful in both the roster UIs
        # and in partial matching.
        classroom_results = self.see('classroom', classroom_params)
        classroom_index = {c['id']: c for c in classroom_results}
        for d in result_dicts:
            c_id = d['assc_classroom_list'][0]
            d['classroom_name'] = classroom_index[c_id]['name']

        # Cache the results for next time, as long as the result set is small
        # enough. App Engine limits us to 1 MB per cached value.
        if sys.getsizeof(pickle.dumps(result_dicts)) > 1000000:
            logging.error("Roster too large, cannot cache: {}."
                          .format(entity_id))
        else:
            memcache.set(roster_key, result_dicts)

        # Return a simplified dictionary.
        return (result_dicts, False)  # False means results are from datastore

    def get_schedule(self, cohort_id, allow_memcache_retrieval=True):
        """Get activity information for the school UI.

        Uses memcache if an appropriate key is found. These keys are populated
        from this function any time a trip to the datastore is required. A
        cronjob calls this function every few minutes to maximize the chances
        that the memcache keys are availble. Keys are erased any time an
        activity within the respective cohort is written to or created to
        ensure that memcache data is never out of date.

        Args:
            entity_id: str, the id of the Cohort for which we're looking up
                students.
            allow_memcache_retrieval: bool, default True, whether we allow
                ourselves to return results from memcache. Setting to False
                forces the function to visit the datastore and refresh memcache
                with the results. Used in re-caching task workers. See
                task_handlers.py

        Returns:
            Tuple of:
                results: list of dictionaries, each an abbreviated set of info
                    on an activity (only the stuff req'd for the schedule view)
                from_memcache: bool, whether the results were pulled from
                    memcache (True) or the datastore (False).
        """
        # Wrangle some search parameters.
        classroom_params = {'is_test': False, 'is_archived': False,
                            'assc_cohort_list': cohort_id}
        activity_params = dict(classroom_params, user_type='student')
        schedule_key = cohort_id + '_schedule'

        # Check if the query results are in memcache. Note that we should be
        # able to trust that any data in memcache is fresh as other code is
        # responsible for clearing the cache if state changes.
        result_dicts = memcache.get(schedule_key)

        if result_dicts and allow_memcache_retrieval:
            logging.info("Got results from memcache.")
            return (result_dicts, True)  # True means results are from memcache
        elif not allow_memcache_retrieval:
            logging.info("Memcache results disallowed. Forced to use "
                         "datastore and refresh memcache.")
        else:
            logging.info("Nothing found in memcache: {}".format(schedule_key))

        # If the results weren't found in memcache, we need to run the query
        # against the datastore.
        activities = self.get('activity', activity_params)

        # We'll want the classroom names as well.
        classroom_results = self.see('classroom', classroom_params)
        classroom_index = {c['id']: c for c in classroom_results}
        result_dicts = []
        for a in activities:
            d = a.to_schedule_dict()
            c_id = a.assc_classroom_list[0]
            d['parent_name'] = classroom_index[c_id]['name']
            result_dicts.append(d)

        # Sort by classroom name, then activity ordinal.
        def s(d):
            return (d.get('activity_ordinal', None),
                    d.get('parent_name', '').lower())

        sorted_results = sorted(result_dicts, key=s)

        # Cache the results for next time, as long as the result set is small
        # enough. App Engine limits us to 1 MB per cached value.
        if sys.getsizeof(pickle.dumps(result_dicts)) > 1000000:
            logging.error("Schedule too large, cannot cache: {}."
                          .format(cohort_id))
        else:
            memcache.set(schedule_key, result_dicts)

        # Return a simplified dictionary.
        return (result_dicts, False)  # False means results are from datastore

    def create(self, kind, kwargs):
        logging.info('Api.create(kind={}, kwargs={})'.format(kind, kwargs))
        logging.info("Api.create is in transction: {}"
                     .format(db.is_in_transaction()))

        # check permissions

        # can this user create this type of object?
        if not self.user.can_create(kind):
            raise PermissionDenied("User type {} cannot create {}".format(
                self.user.user_type, kind))
        # if creating a user, can this user create this TYPE of user
        if kind == 'user':
            if not self.user.can_put_user_type(kwargs['user_type']):
                raise PermissionDenied(
                    "{} cannot create users of type {}."
                    .format(self.user.user_type, kwargs['user_type']))

        # create the object

        klass = kind_to_class(kind)
        # some updates require additional validity checks
        if kind in config.custom_create:
            # These put and associate themselves; the user is sent in so custom
            # code can check permissions.
            entity = klass.create(self.user, **kwargs)
            return entity
        else:
            # non-custom creates require more work
            entity = klass.create(**kwargs)

        if kind in config.kinds_requiring_put_validation:
            entity.validate_put(kwargs)

        # create initial relationships with the creating user

        action = config.creator_relationships[kind]
        if action is not None:
            if self.user.user_type == 'public':
                raise Exception(
                    "We should never be associating with the public user.")
            # associate, but don't put the created entity yet, there's more
            # work to do
            self.user = self.associate(action, self.user, entity, put=False)
            self.user.put()  # do put the changes to the creator

        # create required relationships between the created entity and existing
        # non-user entities

        # different types of users have different required relationships
        k = kind if kind != 'user' else entity.user_type
        for kind_to_associate in config.required_associations[k]:
            target_klass = kind_to_class(kind_to_associate)
            # the id of the entity to associate must have been passed in
            target = target_klass.get_by_id(kwargs[kind_to_associate])
            entity = self.associate('associate', entity, target, put=False)
        if k in config.optional_associations:
            for kind_to_associate in config.optional_associations[k]:
                # they're optional, so check if the id has been passed in
                if kind_to_associate in kwargs:
                    # if it was, do the association
                    target_klass = kind_to_class(kind_to_associate)
                    target = target_klass.get_by_id(kwargs[kind_to_associate])
                    entity = self.associate('associate', entity, target,
                                            put=False)

        # At one point we created qualtrics link pds for students here. Now
        # that happens in the program app via the getQualtricsLinks functional
        # node.

        # now we're done, so we can put all the changes to the new entity
        entity.put()

        return entity

    @db.transactional
    def batch_put_pd(self, params):
        """Put many pds to a single entity group within a transaction.

        See api_handlers.BatchPutPdHandler for structure of params.
        """
        pds = []
        # Go through the pd_batch to create a pd entity for each one
        for pd_info in params['pd_batch']:
            # Copy the other properties, which all apply to each pd
            pd_params = params.copy()
            del pd_params['pd_batch']
            # Mix the variable and value properties of this pd into the params
            pd_params.update(pd_info)
            pds.append(self.create('pd', pd_params))
        return pds

    def batch_put_user(self, params):
        """Put many users.

        See api_handlers.BatchPutUserHandler for structure of params.
        """
        users = []

        # If you look at api_handlers.BatchPutUserHandler you can see the
        # structure of the params dictionary. It's got all the normal
        # parameters to create a user, but instead of the user's first name
        # and last name, it has a list of such names, representing many users
        # to create.
        # Remove the list to convert the batch parameters to creation
        # parameters for a single user (which are now missing name arguments,
        # obviously). We'll fill in names one by one as we create users.
        user_names = params['user_names']  # dicts w/ 'first_name', 'last_name'
        del params['user_names']

        def empty_string_to_none(d):
            """CSV files can't express None; assume blank cells mean None."""
            for k, v in d.items():
                d[k] = None if v == '' else v

        empty_string_to_none(params)
        for d in user_names:
            empty_string_to_none(d)

        # Make one user through the normal api as a template, which will raise
        # any relevant configuration or permissions exceptions. After this
        # single create() call, we'll skip all that fancy logic in favor of
        # speed.
        template_user_params = params.copy()
        template_user_params.update(user_names.pop())
        template_user = self.create('user', template_user_params)
        template_user.consent = template_user_params['consent']

        # Make all the other users in memory, copying relationships from the
        # template. First we'll need to determine which are the relationship-
        # containing properties.
        relationship_property_names = [p for p in dir(User)
                                       if p.split('_')[0] in ['assc', 'owned']]
        for user_info in user_names:
            loop_params = params.copy()
            loop_params.update(user_info)
            loop_user = User.create(**loop_params)  # doesn't put()
            loop_user.consent = loop_params['consent']
            for prop in dir(loop_user):
                if prop in relationship_property_names:
                    template_value = getattr(template_user, prop)
                    setattr(loop_user, prop, template_value)
            users.append(loop_user)

        # Save all the users in a single db operation, but don't try to
        # deal with memcache and rosters for each individual user.
        db.put(users, memcache_management=False)

        # The roster of the classroom and cohort for this batch need to be
        # re-cached manually, so that it's done just once for the whole batch.
        template_user.recache_rosters()

        # Put the template user in the list so they're all there.
        users.append(template_user)

        consent_pds = self.update_user_consent(users)
        logging.info("Created consent pd:")
        logging.info(consent_pds)

        return users

    def update_user_consent(self, users_with_consent):
        """Allow setting of consent pd with batch user upload.

        Required for PATHS+ which operates in multiple "runs" where the
        database is reset but we want to re-upload some history of participants
        afterward.
        """

        # Ignore users with no consent attribute or one with an empty value.
        users = [u for u in users_with_consent if getattr(u, 'consent', None)]
        if len(users) == 0:
            return
        pds = []
        for u in users:
            params = {
                'variable': 'consent',
                'value': u.consent,  # 'true' or 'false'
                'program': u.assc_program_list[0],
                'scope': u.id,
            }
            pds.append(self.create('pd', params))
        return pds

    def update(self, kind, id, kwargs):
        entity = Model.get_from_path(kind, id)
        if not self.user.has_permission('put', entity):
            raise PermissionDenied()
        # if creating a user, can this user create this TYPE of user
        # this is necessary to check if user can promote target user
        # to the proposed level; that does not get checked in user.can_put()
        if kind == 'user' and 'user_type' in kwargs:
            if not self.user.can_put_user_type(kwargs['user_type']):
                raise PermissionDenied(
                    "{} cannot create users of type {}.".format(
                        self.user.user_type, kwargs['user_type']))
        # check put permissions for specific entity
        # can_put_non_relational only checks if user has permissions on entity
        # itself it does not check if they have permissions on entities being
        # associated that needs to be checked as well. Perhaps update should
        # explicitly disallow updates to relationships and force api.associate
        # to handle them?
        self.user.can_put_non_relational(kind, id)

        # some updates require additional validity checks
        if kind in config.kinds_requiring_put_validation:
            kwargs = entity.validate_put(kwargs)

        # run the actual update
        for k, v in kwargs.items():
            setattr(entity, k, v)
        entity.put()
        return entity

    def recursive_update(self, kind, id, params, preview=False):
        """Brute-force changes to an entity and all its children.

        Intentionally EXCLUDES pd entities in this recursion, because there
        could be thousands of entities to move and this could not be done
        without a timeout.

        Creates logs of its activity in case anything needs to be undone. Logs
        are JSON serialization of the set of all entities before changes and
        the set of entities after changes. This way, if some data is erased by
        this function, it can be found again.

        Returns a list of changed entities.

        Lana. Lana. LAAANAAAA. Danger zone.
        """
        if self.user.user_type != 'god':
            raise PermissionDenied()

        # Get the requested entity's children, limiting ourselves to
        # non-deleted ones. Keeping deleted entities around is really only for
        # emergency data recovery.
        entities = self._get_children(id, [('deleted =', False)],
                                      exclude_kinds=['pd'])

        # keep a record of these entities before they were changed
        before_snapshot = [e.to_dict() for e in entities]

        #   Make all the requested property changes to all the retrieved
        # entities, if those properties exist. It's important to have this
        # flexibility because a single conceptual change (e.g. changing cohort
        # associations of all children) requires various kinds of property
        # updates (e.g. to assc_cohort_list of Activity and cohort of Pd).
        #   Also build a unique set of only the changed entities to make the
        # db.put() as efficient as possible.
        to_put = set()
        for e in entities:
            for k, v in params.items():
                if hasattr(e, k) and getattr(e, k) != v:
                    to_put.add(e)
                    setattr(e, k, v)
        to_put = list(to_put)

        after_snapshot = [e.to_dict() for e in to_put]

        if not preview:
            db.put(list(to_put))

            # save the log
            body = json.dumps({
                'entities before recursive update': before_snapshot,
                'entities after recursive update': after_snapshot,
            })
            log_entry = LogEntry.create(log_name='recursive_udpate', body=body)
            log_entry.put()

        return to_put

    def unassociate(self, action, from_entity, to_entity, put=True):
        logging.info(
            'Api.unassociate(action={}, from_entity={}, to_entity={}, put={})'
            .format(action, from_entity.id, to_entity.id, put))

        # If unassociating from a classroom or cohort, we need to clear the
        # corresponding cached roster so it correctly updates. This extra step
        # is needed because normally this procedure is done when an entity is
        # put(), and at that time we only know what the user's NEW associations
        # are, we don't know what they WERE.
        # Note: deleting nonexistent keys is not an error, so no checks are
        # necessary that this is the right type of entity, etc.
        memcache.delete(to_entity.id + '_roster')

        # create the requested association
        from_kind = get_kind(from_entity)
        to_kind = get_kind(to_entity)
        if not self.user.can_associate(action, from_entity, to_entity):
            raise PermissionDenied()
        logging.info("action {}".format(action))
        if action == 'disown':
            property_name = 'owned_' + to_kind + '_list'
        elif action == 'unassociate':
            property_name = 'assc_' + to_kind + '_list'
        relationship_list = getattr(from_entity, property_name)
        if to_entity.id in relationship_list:
            relationship_list.remove(to_entity.id)
        setattr(from_entity, property_name, relationship_list)

        # recurse through cascading relationships
        start_cascade = (action == 'unassociate' and from_kind == 'user' and
                         to_kind in config.user_disassociation_cascade)
        if start_cascade:
            for k in config.user_disassociation_cascade[to_kind]:
                # figure out the target entity
                attr = 'assc_{}_list'.format(k)
                target_id = getattr(to_entity, attr)[0]
                target_entity = Model.get_from_path(k, target_id)
                # make sure the user is ALREADY associated with the target
                if target_id in getattr(from_entity, attr):
                    # then actually unassociate
                    from_entity = self.unassociate(
                        'unassociate', from_entity, target_entity, put=False)

        if not put:
            # avoid multiple db.puts when creating entities
            return from_entity
        else:
            from_entity.put()

        return from_entity

    def associate(self, action, from_entity, to_entity, put=True):
        logging.info('Api.associate(action={}, from_entity={}, to_entity={}, put={})'.format(action, from_entity.id, to_entity.id, put) )

        # create the requested association
        from_kind = get_kind(from_entity)
        to_kind = get_kind(to_entity)
        if not self.user.can_associate(action, from_entity, to_entity):
            raise PermissionDenied("association failure!")
        if action == 'set_owner':
            property_name = 'owned_' + to_kind + '_list'
        elif action == 'associate':
            property_name = 'assc_' + to_kind + '_list'
        relationship_list = getattr(from_entity, property_name)
        if to_entity.id not in relationship_list:
            relationship_list.append(to_entity.id)
        setattr(from_entity, property_name, relationship_list)

        # recurse through cascading relationships

        start_cascade = (action in ['associate', 'set_owner']
                         and from_kind == 'user'
                         and to_kind in config.user_association_cascade)
        if start_cascade:
            for k in config.user_association_cascade[to_kind]:
                # figure out the target entity
                attr = 'assc_{}_list'.format(k)
                # target_id = getattr(to_entity, attr)[0]
                target_list = getattr(to_entity, attr)
                if len(target_list) > 0:
                    target_id = target_list[0]
                    target_entity = Model.get_from_path(k, target_id)
                    # only associate if the user isn't ALREADY associated
                    if target_id not in getattr(from_entity, attr):
                        from_entity = self.associate(
                            'associate', from_entity, target_entity, put=False)
                # else: we can't cascade because this entity's associations
                # aren't complete. This happens when they are first created,
                # and we don't have to worry about it.

        if not put:
            # avoid multiple db.puts when creating entities
            return from_entity
        else:
            from_entity.put()

        return from_entity

    def update_csv_cache(self, cache_name):
        """Looks for changes and updates csv caches."""
        # Find the related CsvCache entity.
        # cache = CsvCache.get_by_key_name(cache_name)
        # if not cache:
        #     # This csv cache doesn't exist yet, so make it.
        #     cache = CsvCache.create(key_name=cache_name)
        cache = CsvCache.get_or_insert(cache_name)

        # update() also saves cache info to the datastore and GCS
        updates_made = cache.update()

        return {'last_checked': str(cache.last_checked),
                'updates_made': updates_made}

    def get_cached_proto_csv(self, cache_name):
        """Get a cache of data as a list designed for csv conversion."""
        if self.user.user_type != 'god':
            raise PermissionDenied("Only gods can download CSVs")

        cache = CsvCache.get_by_key_name(cache_name)

        if not cache:
            # This csv cache doesn't exist yet, so make it.
            cache = CsvCache.create(key_name=cache_name)
            cache.put()

        cache.load()
        return cache.to_list()

    def get_entity_csv(self, entity):
        """Get a list of existing entities designed for csv conversion."""
        from google.appengine.ext.db import GqlQuery

        # permissions
        if self.user.user_type != 'god':
            raise PermissionDenied("Only gods can download CSVs")

        allowed_entities = ['program', 'cohort', 'classroom', 'school']
        if entity not in allowed_entities:
            raise PermissionDenied(
                "Requested entity is not allowed for live CSV")
        entity = entity.title()  # capitalize first letter so GQL query works
        # retrieve requested entity type
        q = GqlQuery("SELECT * FROM {} WHERE is_test=False AND deleted=False"
                     .format(entity))

        # make a list of lists with headers, see CsvHandler
        out = []
        headers = None
        for r in q:
            entry_dicts = r.to_dict()
            if not headers:
                headers = entry_dicts.keys()
                out.append(headers)
            out.append(entry_dicts.values())
        return out

    def import_links(self, filename, session_ordinal):

        # Set GCS path dependent on session number.
        if session_ordinal is 1:
            path = '/yosemite-qualtrics-1/' + filename
        elif session_ordinal is 2:
            path = '/yosemite-qualtrics-2/' + filename

        retry_params = gcs.RetryParams()
        links = []

        # Try the whole gcs transaction
        try:
            f = gcs.open(path, mode='r', retry_params=retry_params)
            # Try just the csv read
            try:
                reader = csv.reader(f)
                for row in reader:
                    if row[7] == 'Link':
                        continue
                    link = row[7]
                    l = QualtricsLink.create(key_name=link,
                                             link=link,
                                             session_ordinal=session_ordinal)
                    links.append(l)
            except:
                logging.error('Something went wrong with the CSV import!')
                logging.error('CSV has been deleted, try uploading again.')
                # Throwing out links
                links = []

            finally:
                f.close()

            gcs.delete(path)

        except gcs.NotFoundError:
            return 'GCS File not found. Did you upload a new file to the bucket?'

        db.put(links)
        return len(links)

    def delete_everything(self):
        if self.user.user_type == 'god' and util.is_development():
            util.delete_everything()
        else:
            raise PermissionDenied("Only gods working on a development server "
                                   "can delete everything.")
        return True

    def delete(self, id):
        logging.info('Api.delete(id={})'.format(id))

        entity = Model.get_from_path(get_kind(id), id)
        if not self.user.has_permission('delete', entity):
            raise PermissionDenied()
        deleted_list = self._get_children(id, [('deleted =', False)])
        cache = {}
        for e in deleted_list:
            cache = self._disassociate(e.id, cache=cache)
            e.deleted = True
        # save changes to deleted entities
        db.put(deleted_list)
        # save changes to users which were disassociated from deleted entities
        db.put([e for id, e in cache.items()])
        return True

    def _disassociate(self, id, cache={}):
        """Find all users associated with this entity and remove the
        relationship. Does not touch the datastore."""
        logging.info('Api._disassociate(id={})'.format(id))

        kind = get_kind(id)
        for relation in ['assc', 'owned']:
            prop = '{}_{}_list'.format(relation, kind)
            query = User.all().filter('deleted =', False)
            query.filter(prop + ' =', id)
            for entity in query.run():
                if entity.id in cache:
                    # prefer the cached entity over the queried one b/c the
                    # datastore is eventually consistent and repeatedly getting
                    # the same entity is not guaranteed to reflect changes.
                    entity = cache[entity.id]
                else:  # cache the entity so it can be used again
                    cache[entity.id] = entity
                relationship_list = getattr(entity, prop)
                relationship_list.remove(id)
        return cache

    def archive(self, id, undo=False):
        entity = Model.get_from_path(get_kind(id), id)
        if not self.user.has_permission('archive', entity):
            raise PermissionDenied()
        entity_list = self._get_children(id, [('is_archived =', undo)])
        for e in entity_list:
            e.is_archived = not undo
        db.put(entity_list)
        return True

    def check_reset_password_token(self, token_string):
        """Validate a token supplied by a user.

        Returns the matching user entity if the token is valid.
        Return None if the token doesn't exist or has expired.

        """
        token_entity = ResetPasswordToken.get_by_id(token_string)

        if token_entity is None:
            # This token doesn't exist. The provided token string is invalid.
            return None

        # Check that it hasn't expired and isn't deleted
        one_hour = datetime.timedelta(hours=1)
        expired = datetime.datetime.now() - token_entity.created > one_hour
        if expired or token_entity.deleted:
            # Token is invalid.
            return None

        return User.get_by_id(token_entity.user)

    def clear_reset_password_tokens(self, user_id):
        """Delete all tokens for a given user."""
        q = ResetPasswordToken.all()
        q.filter('deleted =', False)
        q.filter('user =', user_id)
        tokens = q.fetch(100)
        for t in tokens:
            t.deleted = True
        db.put(tokens)

    def get_all_pd_data(self):
        if not self.user.has_permission('get_all_pd_data'):
            raise PermissionDenied("Only gods can download pd data.")
        else:
            out = []
            query = Pd.all().filter("deleted =", False)

            # headers
            first = query.get().to_dict()
            headers = first.keys()
            first_row = first.values()
            out.append(headers)
            out.append(first_row)

            # table
            for result in query:
                result = result.to_dict()
                out.append(result.values())

            return out

    def _get_children(self, id, filters=[], exclude_kinds=[]):
        """Returns a list of the requested entity and all its children. What
        'children' means is defined by config.children_cascade."""
        # Confusingly enough, a pegasus kind is not the same as an app engine
        # kind. Example: class StraitifierHistory:
        # pegasus kind (used in api urls): 'stratifier_history'
        # app engine kind (used in keys): 'StratifierHistory'
        kind = get_kind(id)
        klass = kind_to_class(kind)
        entity = klass.get_by_id(id)
        results = [entity]

        # children-fetching differs based on user type
        if kind == 'user':
            if entity.user_type in ['god']:
                raise Exception()
            kind = entity.user_type

        # Depending on the current kind, we need to get children of other
        # kinds. Exactly which kinds and filters apply is defined in
        # config.children_cascade. For instance, activities with user type
        # 'teacher' are children of a user with user type 'teacher', but
        # activities with user type 'student' are not (those are children of a
        # classroom). Since this structure doesn't map perfectly onto pure
        # kinds, we need a little fanciness to achieve the needed flexibility.
        if kind in config.children_cascade:
            for info in config.children_cascade[kind]:
                loop_filters = filters[:]
                # activities need some extra filtering
                if info.kind == 'teacher_activity':
                    loop_filters.append(('user_type =', 'teacher'))
                    child_kind = 'activity'
                elif info.kind == 'student_activity':
                    loop_filters.append(('user_type =', 'student'))
                    child_kind = 'activity'
                else:
                    child_kind = info.kind

                if child_kind not in exclude_kinds:
                    child_klass = kind_to_class(child_kind)
                    q = child_klass.all().filter(info.property + ' =', id)
                    for filter_tuple in loop_filters:
                        q.filter(*filter_tuple)
                    for child in q.run():
                        results += self._get_children(child.id, filters,
                                                      exclude_kinds)

        return results

    def init_activities(self, user_type, teacher_id, program_id,
                        cohort_id=None, classroom_id=None, is_test=False):
        logging.info(
            'Api.init_activities(program={}, cohort={}, classroom={})'.format(
                program_id, cohort_id, classroom_id))

        program = self.get_from_path('program', program_id)

        # Get and check templates.
        templates = program.activity_templates(user_type)
        if len(templates) is 0:
            raise Exception("Program {} has no templates; cannot "
                            "initialize activities.".format(program.name))

        # Check that these activities don't already exist.
        params = {
            'user_type': user_type,
            'teacher': teacher_id,
            'assc_program_list': program.id,
            'is_test': is_test,
        }
        if cohort_id:
            params['assc_cohort_list'] = cohort_id
        if classroom_id:
            params['assc_classroom_list'] = classroom_id
        existing_activities = self.get('activity', params)

        if len(existing_activities) is not 0:
            # Some previous process created these activities, so do nothing.
            # Return an empty list b/c no activites were created.
            return []

        # Now we should be ready to create activities.
        created_activities = []
        for index, template in enumerate(templates):
            params = {
                # 'name': template['name'],
                'activity_ordinal': index + 1,
                'user_type': user_type,
                'teacher': teacher_id,
                'status': 'incomplete',
                'program_abbreviation': program.abbreviation,
                'program': program.id,
                'is_test': is_test,
            }
            if cohort_id:
                cohort = Cohort.get_by_id(cohort_id)
                params['cohort'] = cohort.id
            if classroom_id:
                classroom = Classroom.get_by_id(classroom_id)
                params['classroom'] = classroom.id
            created_activities.append(self.create('activity', params))
        return created_activities

    def stratify(self, program_id, name, proportions, attributes):
        """Perform stratified randomization and issue a condition."""
        # Each total of users that have been assigned to a specific condition
        # within a certain set of parameters is distributed over a set of
        # counter shards. Each set of counter shards is summed or incremented
        # via a key. We need to construct the key corresponding to each
        # condition in this stratifier to look up and reconstruct the history
        # of how conditions have been assigned. Then we can issue a condition
        # to this new user and increment the corresponding set of counter
        # shards.

        # The keys are a comma-separated list of all the pieces of data that
        # identify them. Based on the implementation of sharded
        # counters which we borrow from Google's example:
        # https://cloud.google.com/appengine/articles/sharding_counters

        # Used as a prefix for the condition keys.
        # e.g. 'student_stratifier,Program_XYZ,{"control": 1, "treatment": 1}'
        # Hashing a dictionary results in a predictably-ordered JSON string
        # suitable for key generation.
        proportions_str = util.hash_dict(proportions)
        attributes_str = util.hash_dict(attributes)
        prefix = ','.join([program_id, name, proportions_str])

        # Use the prefix and hash algorithm to make each key.
        conditions = proportions.keys()
        # e.g. 'student_stratifier,Program_XYZ,{"control": 1, "treatment": 1},{"classroom": "Classroom_QWE", "gender": "male"},control'
        keys = {c: ','.join([prefix, attributes_str, c]) for c in conditions}

        # @todo: use?
        # prefix_keys = {c: ','.join([prefix, c]) for c in conditions}

        # Sum the shards to get a history
        history = {c: sharding.get_count(k) for c, k in keys.items()}

        # @todo: use?
        # prefix_history = {c: sharding.get_count(k)
        #                   for c, k in prefix_keys.items()}

        # Use the history to figure out which condition(s) are currently
        # underrepresented, which considers balance across both individual
        # buckets, and the whole prefix.
        candidates = self.get_candidate_conditions(proportions, history)

        # @todo: use?
        # prefix_candidates = self.get_candidate_conditions(proportions,
        #                                                   prefix_history)
        # @todo: Not sure how to use prefix_candidates!!

        assigned_condition = random.choice(candidates)

        # Then increment the counter for that condition and return it.
        sharding.increment(keys[assigned_condition])

        # @todo: use?
        # sharding.increment(prefix_keys[assigned_condition])

        return assigned_condition

    def get_candidate_conditions(self, proportions, history, margin=None):
        """Returns conditions valid for assignment based on a history."""
        if margin is None:
            margin = config.stratification_balance_margin
        ideal_total = sum(proportions.values())
        conditions = proportions.keys()
        total_assigned = sum(history.values())

        # Return all conditions if nothing has been assigned
        if total_assigned is 0:
            return conditions

        # Find proportion assigned to each condition
        current_ratios = {c: n / float(total_assigned)
                          for c, n in history.items()}
        ideal_ratios = {c: p / float(ideal_total)
                        for c, p in proportions.items()}
        # Any conditions that are more prevalent than ideal by a fixed margin
        # are NOT returned as candidate conditions. This makes sure that
        # randomization remains balanced.
        candidates = []
        for condition, ideal_ratio in ideal_ratios.items():
            ratio_difference = current_ratios[condition] - ideal_ratio
            if ratio_difference < margin:
                candidates.append(condition)

        return candidates

    def preview_reminders(self, program, user_type):
        """Show what reminder emails will look like.

        Permissions are open, because this is read only and only uses data from
        the current user.
        See core@Reminder for details.
        """
        activities = self.get_by_ids(self.user.owned_activity_list)
        reminders = Reminder.preview_reminders(
            program, user_type, self.user, activities)
        return {'message': reminders}

    def show_reminders(self, date_string=None):
        god_api = Api(User(user_type='god'))
        cron = Cron(god_api)
        reminders = cron.get_reminders_by_date(date_string)

        # Add a preview of how the text will be converted to html when sent.
        # See core.Email.send()
        for r in reminders:
            r['html'] = markdown.markdown(r['body'])
        return reminders

    def search(self, query, start=0, end=1):
        """Search the full text index. Return results from start to end.
        Ignore results that the user does not have permission to see.
        """

        indexer = Indexer.get_or_insert('the indexer')
        index = indexer.get_index()
        results = []

        matches = index.search(query)

        for match in matches:
            entity_id = match.doc_id

            try:
                entity = self.get_by_ids([entity_id])[0].to_dict()
                if not entity['is_test'] and not entity['deleted']:
                    results.append(entity)
            except PermissionDenied:
                pass
            except IndexError:
                logging.warning("Could not get entity: " + entity_id)

            if len(results) == end - start:
                break

        logging.info("""Search()
            query: {},
            n_results: {}
            result: {}
            """.format(query, len(results[start:]), results[start:]))

        return results[start:]

    def program_outline(self, program_id):
        program = self.get('program', {'id': program_id})[0]
        teacher_config = Program.get_app_configuration(program.abbreviation,
                                                       'teacher')
        student_config = Program.get_app_configuration(program.abbreviation,
                                                       'student')
        return {'teacher': teacher_config['outline'],
                'student': student_config['outline']}

    def sync_subprogram_activities(self, program_id, user_type, outline):
        if self.user.user_type != 'god':
            raise PermissionDenied()

        def base_query():
            q = Activity.all().filter('deleted =', False)
            q.filter('assc_program_list =', program_id)
            q.filter('user_type =', user_type)
            return q

        # How many activities do we expect based on the outline?
        is_activity = lambda m: 'type' in m and m['type'] == 'activity'
        num_activities = len(filter(is_activity, outline))

        # How many activities do users actually have?
        # Check the boundary of ordinals. If the outline specifies 4
        # activities, check for ordinals 4 and 5. If neither exist, there
        # are too few. If only 4 exists, we're done. If 4 and 5 exist,
        # there are too many. If 5 exists but not 4, well, that's FUBAR.
        normal_query = base_query()
        normal_query.filter('activity_ordinal =', num_activities)

        extra_query = base_query()
        extra_query.filter('activity_ordinal =', num_activities + 1)

        normal_exist = normal_query.count() > 0
        extra_exist = extra_query.count() > 0

        # Compare expectation and reality and deal with it.
        if normal_exist and not extra_exist:
            # This is exactly what we expect if activities and the outline
            # are in sync.
            message = 'Activity entities already synched.'
        elif not normal_exist:
            # There aren't as many activity entities as there are specified
            # in the outline. We need to create more.
            message = 'Extra activities created to match modified outline.'
            # What's the largest ordinal that exists?
            count_query = base_query()
            a = count_query.order('-activity_ordinal').fetch(1)[0]
            largest_ordinal = a.activity_ordinal
            # Every activity 1 marks a set that must be extended.
            copy_query = base_query()
            copy_query.filter('activity_ordinal =', 1)
            # Index association changes by teacher and then do them all at
            # once later b/c multiple writes to the same entity in quick
            # succession will fail.
            teacher_updates = {}
            for a in copy_query.run():
                # Add as many activities as required by the outline
                added_ids = []
                for o in range(largest_ordinal + 1, num_activities + 1):
                    kwargs = {
                        'activity_ordinal': o,
                        'user_type': a.user_type,
                        'teacher': a.teacher,
                        'status': 'incomplete',
                        'program_abbreviation': a.program_abbreviation,
                        'assc_program_list': a.assc_program_list,
                        'assc_cohort_list': a.assc_cohort_list,
                        'assc_classroom_list': a.assc_classroom_list,
                    }
                    new_activity = Activity.create(**kwargs)
                    new_activity.put()
                    added_ids.append(new_activity.id)
                # Record this association for later.
                if a.teacher not in teacher_updates:
                    teacher_updates[a.teacher] = []
                teacher_updates[a.teacher] += added_ids
            # Associate these activities with their owners (teachers). This way
            # we have only one put() per teacher.
            for teacher_id, new_ids in teacher_updates.items():
                teacher = User.get_by_id(teacher_id)
                teacher.owned_activity_list += new_ids
                teacher.put()
        elif normal_exist and extra_exist:
            # There are more activity entities than there are specified in
            # the outline. We need to delete the extras.
            message = 'Deleted extra activity entities.'
            del_query = base_query()
            del_query.filter('activity_ordinal >', num_activities)
            for a in del_query.run():
                self.delete(a.id)

        return message

    def sync_program_activities(self, program_id):
        if self.user.user_type != 'god':
            raise PermissionDenied()

        abbr = Program.get_by_id(program_id).abbreviation
        s_config = Program.get_app_configuration(abbr, 'student')
        t_config = Program.get_app_configuration(abbr, 'teacher')
        s_message = t_message = 'Subprogram not present.'
        # Don't assume every program will always have both types of subprograms
        if s_config:
            s_message = self.sync_subprogram_activities(
                program_id, 'student', s_config['outline'])
        if t_config:
            t_message = self.sync_subprogram_activities(
                program_id, 'teacher', t_config['outline'])

        return {'student': s_message, 'teacher': t_message}
