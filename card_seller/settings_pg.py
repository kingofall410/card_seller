from .settings import *
DATABASES['default'] = {
    'ENGINE': 'django.db.backends.postgresql',
    'NAME': 'cardishthings',
    'USER': 'dcrown',
    'PASSWORD': 'nirvana1',
    'HOST': 'localhost',
    'PORT': '5432',
}
