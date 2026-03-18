import django
from django.conf import settings

settings.configure(
    DATABASES={
        'default': {
            'ENGINE': 'django.db.backends.postgresql',   # or mysql
            'NAME': 'cardishthings',
            'USER': 'dcrown',
            'PASSWORD': 'nirvana1',
            'HOST': 'localhost',
            'PORT': '5432',  # or 3306 for MySQL
        }
    }
)

django.setup()

from django.db import connections

try:
    connections['default'].cursor()
    print("SUCCESS: Django can connect to the new database.")
except Exception as e:
    print("ERROR:", e)
