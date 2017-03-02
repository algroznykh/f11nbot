WSGI_APPLICATION = 'test_projecrt.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'stvalbot',
        'USER': 'postgres',
        'PASSWORD': '',
        'HOST': '127.0.0.1',
        'PORT': '5432',
    }
}

INSTALLED_APPS = ['data']

SECRET_KEY = 'SECRET_1'

try:
    from local_settings import *

except ImportError:
    pass