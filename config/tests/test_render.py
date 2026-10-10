import os
import subprocess
import sys
from django.test import SimpleTestCase


class RenderTests(SimpleTestCase):
    def check_config(self, code='import django; django.setup()', **overrides):
        env = dict(os.environ, DJANGO_SETTINGS_MODULE='config.render', DEBUG='False',
                   SECRET_KEY='test-only-key-0123456789012345678901234567890123456789',
                   DATABASE_URL='postgresql://test:test@db.internal/test', DB_HOST='',
                   ALLOWED_HOSTS='mediatrack.example.com',
                   CSRF_TRUSTED_ORIGINS='https://mediatrack.example.com', CORS_ALLOWED_ORIGINS='')
        env.update(overrides)
        return subprocess.run([sys.executable, '-B', '-c', code], env=env,
                              capture_output=True, text=True, timeout=20)

    def test_postgres_defaults_to_required_tls_without_connection(self):
        result = self.check_config(code='''
import django
django.setup()
from django.conf import settings
assert settings.DATABASES['default']['OPTIONS']['sslmode'] == 'require'
assert settings.DATABASES['default']['OPTIONS']['connect_timeout'] == 5
assert settings.STORAGES['staticfiles']['BACKEND'] == 'whitenoise.storage.CompressedManifestStaticFilesStorage'
''')
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_unsafe_configuration_rejected(self):
        for overrides in ({'DEBUG': 'True'}, {'SECRET_KEY': 'short'}, {'SECRET_KEY': 'x' * 60},
                          {'DATABASE_URL': ''}, {'DATABASE_URL': 'sqlite:///:memory:'},
                          {'ALLOWED_HOSTS': '*'}, {'ALLOWED_HOSTS': '.example.com'},
                          {'ALLOWED_HOSTS': 'https://example.com'},
                          {'CSRF_TRUSTED_ORIGINS': ''},
                          {'CSRF_TRUSTED_ORIGINS': ' , '},
                          {'CSRF_TRUSTED_ORIGINS': 'https://mediatrack.example.com/'},
                          {'CSRF_TRUSTED_ORIGINS': 'https://mediatrack.example.com:bad'},
                          {'CSRF_TRUSTED_ORIGINS': 'https://mediatrack.example.com:65536'},
                          {'CORS_ALLOWED_ORIGINS': 'https://frontend.example.com/'},
                          {'CSRF_TRUSTED_ORIGINS': 'http://mediatrack.example.com'},
                          {'CSRF_TRUSTED_ORIGINS': 'https://other.example.com'}):
            with self.subTest(fields=list(overrides)):
                self.assertNotEqual(self.check_config(**overrides).returncode, 0)

    def test_tls_downgrade_and_unbounded_timeouts_rejected(self):
        for query in ('sslmode=disable', 'sslmode=prefer', 'sslmode=allow',
                      'sslmode=verify-full', 'connect_timeout=0', 'connect_timeout=31',
                      'connect_timeout=bad'):
            with self.subTest(query=query):
                self.assertNotEqual(self.check_config(
                    DATABASE_URL='postgresql://test:test@db.internal/test?' + query).returncode, 0)

    def test_https_proxy_cookies_csrf_and_probes(self):
        result = self.check_config(code='''
import django
django.setup()
from django.conf import settings
from django.test import RequestFactory, Client
from django.middleware.security import SecurityMiddleware
from django.http import HttpResponse
from unittest.mock import patch
from django.db import DatabaseError
assert settings.SECURE_PROXY_SSL_HEADER == ('HTTP_X_FORWARDED_PROTO', 'https')
assert settings.SECURE_SSL_REDIRECT and settings.SESSION_COOKIE_SECURE and settings.CSRF_COOKIE_SECURE
factory = RequestFactory()
request = factory.get('/', HTTP_HOST='mediatrack.example.com', HTTP_X_FORWARDED_PROTO='https')
assert request.is_secure()
assert SecurityMiddleware(lambda req: HttpResponse())(request).status_code == 200
client = Client(enforce_csrf_checks=True, HTTP_HOST='mediatrack.example.com')
with patch('config.views.connection.cursor', side_effect=DatabaseError('private')) as cursor:
    assert client.get('/health/').status_code == 200
    cursor.assert_not_called()
    assert client.get('/readiness/').status_code == 301
    response = client.get('/readiness/', HTTP_X_FORWARDED_PROTO='https')
    assert response.status_code == 503 and response.json() == {'status': 'unavailable'}
    assert client.post('/usuarios/login/', HTTP_X_FORWARDED_PROTO='https').status_code == 403
''')
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_development_still_uses_sqlite(self):
        result = self.check_config(
            DJANGO_SETTINGS_MODULE='config.settings', DEBUG='True', DATABASE_URL='',
            code="from django.conf import settings; assert settings.DATABASES['default']['ENGINE'] == 'django.db.backends.sqlite3'")
        self.assertEqual(result.returncode, 0, result.stderr)
