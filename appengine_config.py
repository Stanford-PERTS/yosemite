import gae_mini_profiler.profiler


def webapp_add_wsgi_middleware(app):
    # We never use appstats; disabling.
    # from google.appengine.ext.appstats import recording
    # app = recording.appstats_wsgi_middleware(app)

    # app = gae_mini_profiler.profiler.ProfilerWSGIMiddleware(app)

    return app


# def gae_mini_profiler_should_profile_production():
#     from google.appengine.api import users
#     return users.is_current_user_admin()
