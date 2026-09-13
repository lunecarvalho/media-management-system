"""Testes isolados do banco e dos segredos locais."""
import os
os.environ['DEBUG'] = 'False'
os.environ['SECRET_KEY'] = 'test-only-key-not-for-production-012345678901234567890123456789'
os.environ['DATABASE_URL'] = os.environ.get('TEST_DATABASE_URL', '')
os.environ['DB_HOST'] = ''
from .settings import *  # noqa: F403,E402
if not os.environ.get('TEST_DATABASE_URL'):
    DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}}
SECURE_SSL_REDIRECT = False
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
ALLOWED_HOSTS = ['testserver', 'localhost']
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
}
