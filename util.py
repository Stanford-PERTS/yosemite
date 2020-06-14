"""Collection of utility functions."""

from google.appengine.api import taskqueue
from google.appengine.api import users as app_engine_users  # is_god()
from google.appengine.ext import db  # DictionaryProperty
from google.appengine.ext.db import metadata  # delete_everything()
import collections
import copy
import datetime  # parse_date()
import google.appengine.api.app_identity as app_identity  # is_development()
import json  # get_request_dictionary() and hash_dict()
import logging
import os  # is_development()
import pickle  # DictionaryProperty
import re  # get_request_dictionary() and hash_dict()
import time  # delete_everything()
import unicodedata  # clean_string()
import urllib
import urlparse

import config
from dateutil import parser as dateutil_parser  # parse_datetime()
from simple_profiler import Profiler

# A 'global' profiler object that's used in BaseHandler.get. So, to profile
# any request handler, add events like this:
# util.profiler.add_event("did the thing")
# and when you're ready, print the results, perhaps like this:
# logging.info(util.profiler)
profiler = Profiler()


def allow_all_logging():
    """Don't ignore any log events."""
    logging.getLogger().setLevel(logging.DEBUG)


def clean_string(s):
    """Returns lowercase-ified string, without special chars. See
    var f for only allowable chars to return."""

    # *Replace* unicode special chars with closest related char, decode to
    # string from unicode.
    if isinstance(s, unicode):
        s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore')
    s = s.lower()
    f = 'abcdefghijklmnopqrstuvwxyz0123456789'
    return filter(lambda x: x in f, s)


def hash_dict(d):
    """Generate a unique, identifying json string from a flat dictionary.
    Use json.loads() to convert back to a dictionary."""
    ordered_d = collections.OrderedDict(sorted(d.items(), key=lambda t: t[0]))
    return json.dumps(ordered_d)


def parse_datetime(s, return_type='datetime'):
    """Takes just about any date/time string and returns a python object.
    Datetime objects are the default, but setting type to 'date' or 'time'
    returns the appropriate object.

    See http://labix.org/python-dateutil
    """

    if return_type not in ['datetime', 'date', 'time']:
        raise Exception("Invalid type: {}.".format(return_type))

    dt = dateutil_parser.parse(s)

    if return_type in ['date', 'time']:
        method = getattr(dt, return_type)
        return method()
    else:
        return dt


def ordinal_suffix(i):
    """Get 'st', 'nd', 'rd' or 'th' as appropriate for an integer."""
    if i < 0:
        raise Exception("Can't handle negative numbers.")

    if i % 100 in [11, 12, 13]:
        return 'th'
    elif i % 10 is 1:
        return 'st'
    elif i % 10 is 2:
        return 'nd'
    elif i % 10 is 3:
        return 'rd'
    else:
        return 'th'


def get_request_dictionary(request):
    params = {}
    relevant = lambda x: x not in config.ignored_url_arguments
    for k in filter(relevant, request.arguments()):
        v = request.get(k)

        # Convert some special tokens into values that otherwise can't be
        # easily sent in a request string, e.g. None
        if isinstance(v, collections.Hashable) and v in config.url_values:
            v = config.url_values[v]

        if k[-5:] == '_json':
            # this value should be interpreted as json AND renamed w/o suffix
            params[k[:-5]] = json.loads(v)
        elif k in config.boolean_url_arguments:
            # Sending a javascript boolean via POST results in v being a
            # python native bool here. If via GET, it comes as str 'true'.
            if isinstance(v, bool):
                params[k] = v
            else:
                params[k] = str(v) in config.true_strings
        elif k in config.integer_url_arguments:
            params[k] = None if v == '' else int(v)
        elif k in config.date_url_arguments:
            params[k] = None if v is None else parse_datetime(v, 'date')
        elif k in config.time_url_arguments:
            params[k] = None if v is None else parse_datetime(v, 'time')
        elif k in config.datetime_url_arguments:
            params[k] = None if v is None else parse_datetime(v, 'datetime')
        elif k in config.json_url_arugments:
            params[k] = json.loads(v)
        else:
            params[k] = v
    return params


def is_localhost():
    """Is running on the development SDK, i.e. NOT deployed to app engine."""
    return os.environ['SERVER_SOFTWARE'].startswith('Development')


def is_development():
    """Localhost OR the pegasus-dev app are development.

    Pegasus and Yosemite are not, i.e. are production.
    """
    # see http://stackoverflow.com/questions/5523281/how-do-i-get-the-application-id-at-runtime
    return is_localhost() or app_identity.get_application_id() == 'yosemite-dev'


def delete_everything():
    #   get all of our classes
    for kind in metadata.get_kinds():
        entities_remain = True
        while entities_remain:
            q = db.GqlQuery("SELECT __key__ FROM " + kind)
            if q.count():
                db.delete(q.fetch(200))
                time.sleep(0.5)
            else:
                entities_remain = False


def zero_float(string):
    """ Try to make a string into a floating point number
    and make it zero if it cannot be cast.  This function
    is useful because python will throw an error if you
    try to cast a string to a float and it cannot be."""
    try:
        return float(string)
    except:
        return 0


def list_by(l, p):
    """Turn a list of objects into a dictionary of lists, keyed by p.

    Example: Given list of pd entities and 'user', returns
    {
        'User_ABC': [pd1, pd2],
        'User_DEF': [pd3, pd4],
    }
    Objects lacking property p will be indexed under None.
    """
    d = {}
    for x in l:
        key = getattr(x, p) if hasattr(x, p) else None
        if key not in d:
            d[key] = []
        d[key].append(x)
    return d


def is_function(x):
    """Actually tests if x is callable, which applies both to user-defined and
    built in (native) python functions.
    See http://stackoverflow.com/questions/624926/how-to-detect-whether-a-python-variable-is-a-function
    """
    return hasattr(x, '__call__')


class DictionaryProperty(db.Property):
    """Abstracts the serialized storage of python dictionaries as properties
    of google datastore entities.

    See: http://forums.udacity.com/questions/6021587/how-tostore-dictionary-and-other-python-objects-in-google-datastore"""
    data_type = dict

    def get_value_for_datastore(self, model_instance):
        value = super(DictionaryProperty, self).get_value_for_datastore(
            model_instance)
        return db.Blob(pickle.dumps(value))

    def make_value_from_datastore(self, value):
        if value is None:
            return dict()
        return pickle.loads(value)

    def default_value(self):
        if self.default is None:
            return dict()
        else:
            return super(DictionaryProperty, self).default_value().copy()

    def validate(self, value):
        if not isinstance(value, dict):
            msg = "{} needs to be convertible to a dict. Value: {}.".format(
                self.name, value)
            raise db.BadValueError(msg)
        return super(DictionaryProperty, self).validate(value)

    def empty(self, value):
        return value is None


class ComplexListProperty(db.Property):
    """Abstracts the serialized storage of python lists as properties of google
    datastore entities.

    See: http://forums.udacity.com/questions/6021587/how-tostore-dictionary-and-other-python-objects-in-google-datastore"""
    data_type = list

    def get_value_for_datastore(self, model_instance):
        value = super(ComplexListProperty, self).get_value_for_datastore(
            model_instance)
        return db.Blob(pickle.dumps(value))

    def make_value_from_datastore(self, value):
        if value is None:
            return list()
        return pickle.loads(value)

    def default_value(self):
        if self.default is None:
            return list()
        else:
            return super(ComplexListProperty, self).default_value().copy()

    def validate(self, value):
        if not isinstance(value, list):
            msg = "{} needs to be convertible to a list. Value: {}, {}.".format(
                self.name, value, type(value))
            raise db.BadValueError(msg)
        return super(ComplexListProperty, self).validate(value)

    def empty(self, value):
        return value is None


class JsonProperty(db.Property):
    """Abstracts the serialized storage of python dictionaries and lists as
    JSON strings.

    This is useful because BigQuery has tools to handle JSON built in. It does
    not have tools to handle python's native serialized data

    See:
    * http://forums.udacity.com/questions/6021587/how-tostore-dictionary-and-other-python-objects-in-google-datastore
    * https://cloud.google.com/appengine/docs/python/datastore/propertyclass#Property_validate
    """
    data_type = dict

    def get_value_for_datastore(self, model_instance):
        value = super(JsonProperty, self).get_value_for_datastore(
            model_instance)
        # Important to use db.Text and not just native str b/c the datastore
        # limits strings to 500 characters.
        # https://cloud.google.com/appengine/docs/python/datastore/typesandpropertyclasses#TextProperty
        return db.Text(json.dumps(value))

    def make_value_from_datastore(self, value):
        if value is None:
            return None
        return json.loads(value)

    def default_value(self):
        if self.default is None:
            return None
        else:
            return copy.deepcopy(super(JsonProperty, self).default_value())

    def validate(self, value):
        try:
            json.dumps(value)
        except:
            msg = "{} needs to be convertible as JSON. Value: {}.".format(
                self.name, value)
            raise db.BadValueError(msg)
        return super(JsonProperty, self).validate(value)

    def empty(self, value):
        return value is None


def text_to_html(string):
    """Take text as input and return html that renders nicely.
    For example replace newlines with '<br/>'

    This was built for use in reminder emails, please check for
    effects there if you are updating it."""
    string = "<html><body>" + string + "</body></html>"
    string = string.replace("\n", "<br/>")

    return string


def levenshtein_distance(s, t):
    """Returns the Levenshtein edit distance between two strings.

    https://code.google.com/p/googleappengine/source/browse/trunk/python/lib/whoosh/whoosh/support/levenshtein.py?r=193
    """

    m, n = len(s), len(t)
    d = [range(n + 1)]
    d += [[i] for i in range(1, m + 1)]
    for i in range(0, m):
        for j in range(0, n):
            cost = 1
            if s[i] == t[j]:
                cost = 0
            d[i + 1].append(min(d[i][j + 1] + 1,    # deletion
                                d[i + 1][j] + 1,    # insertion
                                d[i][j] + cost))    # substitution
    return d[m][n]


# Quick way of detecting if a kwarg was specified or not.
sentinel = object()


def set_query_parameters(url, new_fragment=sentinel, **new_params):
    """Given a URL, set a query parameter or fragment and return the URL.

    Setting to '' or None removes the parameter or hash/fragment.

    > set_query_parameter('http://me.com?foo=bar&biz=baz', foo='stuff', biz='')
    'http://me.com?foo=stuff'

    http://stackoverflow.com/questions/4293460/how-to-add-custom-parameters-to-an-url-query-string-with-python
    """
    scheme, netloc, path, query_string, fragment = urlparse.urlsplit(url)
    query_params = urlparse.parse_qs(query_string)

    query_params.update(new_params)
    query_params = {k: v for k, v in query_params.items()
                    if v not in ['', None]}
    new_query_string = urllib.urlencode(query_params, doseq=True)

    if new_fragment is not sentinel:
        fragment = new_fragment

    return urlparse.urlunsplit(
        (scheme, netloc, path, new_query_string, fragment))


def add_eventually_consistent_task(url, queue_name='default', countdown=10,
                                   **kwargs):
    # When testing, CAM found that tasks that ran immediately after a write
    # sometimes pulled stale results from the datastore: the write that
    # triggered them wasn't reflected in the query made in the task and
    # thus a bad roster was cached. This created an unacceptable situation:
    # the UI would not to reflect the change the user just made, and it
    # would never correct itself until another write was made.

    # The solution here is just to wait 10 seconds to allow writes to
    # propagate.
    # print 'util.add_eventually_consistent_task() ' + url  # for debugging
    taskqueue.add(url=url, queue_name=queue_name, countdown=countdown,
                  **kwargs)
