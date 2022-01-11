#
# Django Development
# ..........................

import sys
import os
if 'makemessages' in sys.argv:
    LOCALE_PATHS = (os.path.join('geotrek', 'locale'),)

DEBUG = True

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

#
# Developper additions
# ..........................

INSTALLED_APPS = (
    'django_extensions',
    'debug_toolbar',
    'drf_yasg',
) + INSTALLED_APPS

INTERNAL_IPS = type(str('c'), (), {'__contains__': lambda *a: True})()

ALLOWED_HOSTS = ['*']

MIDDLEWARE += (
    'debug_toolbar.middleware.DebugToolbarMiddleware',
)
#
# Use some default tiles
# ..........................

LOGGING['loggers']['geotrek']['level'] = 'DEBUG'
LOGGING['loggers']['']['level'] = 'DEBUG'
