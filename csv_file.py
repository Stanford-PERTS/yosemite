"""DEPRECATED 2014-03-01 by cam.

This csv stuff is now all done through compute engine. I'll leave this file
around in case we want to know how to interact with cloud storage from app
engine in the future.

Note 2013-04-11 by ajb:

Adding a delete file classmethod. This will be used to clean out our backup
buckets with a cron job, to keep them from getting too gross.
TODO: If we want to do more stuff with GCS, we should clean up this class
because it's getting a little smelly. Currently it's geared around one specific
bucket--perts_prod/--but we should generalize it to make it more useful.
(also it like doesn't really make sense that the file's called csv_file)
"""
import cloudstorage as gcs
import json

import util

# The demo code in this library download is very useful. This particular
# download is for SDK version 1.8.8
# https://code.google.com/p/appengine-gcs-client/downloads/detail?name=appengine-gcs-client-python-r127.zip&can=2&q=

# Some documentation for the GCS client library:
# https://developers.google.com/appengine/docs/python/googlecloudstorageclient/
# https://developers.google.com/appengine/docs/python/googlecloudstorageclient/functions


class CsvFile:
    """Uses Google Cloud Storage to manage csv files with certain presets."""

    mime_type = 'text/plain'

    if util.is_development():
        bucket = 'perts_dev'
    else:
        bucket = 'perts_prod'
    # You can specific some parameters here, see commented example.
    retry_params = gcs.RetryParams()
    # retry_params = gcs.RetryParams(initial_delay=0.2,
    #                                max_delay=5.0,
    #                                backoff_factor=2,
    #                                max_retry_period=15)

    # Only used during writes. Controls permissions. For types of permission,
    # see https://developers.google.com/storage/docs/accesscontrol#extension
    write_options = {
        'x-goog-acl': 'project-private',  # default permission
        # 'x-goog-meta-foo': 'foo',  # arbitrary meta data
        # 'x-goog-meta-bar': 'bar',
    }

    @classmethod
    def list_bucket_files(klass, bucket_name):
        iterable = gcs.listbucket('/' + bucket_name + '/')
        return [f.filename for f in iterable]

    def __init__(self, filename):
        self.relative_path = filename
        self.absolute_path = '/{}/{}'.format(self.bucket, self.relative_path)
        # create the file, if it doesn't exist already
        # This doesn't work.

        try:
            gcs_file = gcs.open(self.absolute_path, mode='r',
                                retry_params=self.retry_params)
            gcs_file.close()
        except:
            self.write(json.dumps([]))

    def read(self):
        gcs_file = gcs.open(self.absolute_path, mode='r',
                            retry_params=self.retry_params)
        string = gcs_file.read()
        gcs_file.close()
        return string

    def write(self, string):
        gcs_file = gcs.open(self.absolute_path, mode='w',
                            content_type=self.mime_type,
                            retry_params=self.retry_params,
                            options=self.write_options)
        # unicode not allowed here
        gcs_file.write(str(string))
        gcs_file.close()

    @classmethod
    def delete(self, filename):
        """Delete method will remove a file from GCS, provided an absolute
        file path."""
        try:
            gcs.delete(filename)
            return "{} deleted.".format(filename)
        except gcs.NotFoundError:
            return 'GCS File Not Found'


