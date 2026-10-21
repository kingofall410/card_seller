from .settings import *
DATABASES['default'] = {
    'ENGINE': 'django.db.backends.postgresql',
    'NAME': 'cardishthings',
    'USER': 'dcrown',
    'PASSWORD': 'nirvana1',
    #'HOST': 'localhost',
    'HOST': '192.168.132.111',
    'PORT': '5432',
}
