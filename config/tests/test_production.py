import os
import subprocess
import sys
from django.test import SimpleTestCase


class ProductionTests(SimpleTestCase):
    def test_low_entropy_secret_and_partial_wildcard_rejected(self):
        url = 'postgresql://user:pass@localhost/db?sslmode=verify-full&sslrootcert=system'
        for overrides in ({'SECRET_KEY': 'a' * 64}, {'ALLOWED_HOSTS': '*.example.com'}, {'ALLOWED_HOSTS': ''}):
            self.assertNotEqual(self.check_config(DATABASE_URL=url, **overrides).returncode, 0)

    def test_tls_modes_and_missing_ca_rejected(self):
        for query in ('sslmode=require', 'sslmode=disable', 'sslmode=verify-ca&sslrootcert=system', 'sslmode=verify-full'):
            self.assertNotEqual(self.check_config(DATABASE_URL='postgresql://user:pass@localhost/db?' + query).returncode, 0)

    def test_unbounded_connection_timeout_rejected(self):
        for timeout in ('0', '-1', '31', 'invalid'):
            url = 'postgresql://user:pass@localhost/db?sslmode=verify-full&sslrootcert=system&connect_timeout=' + timeout
            self.assertNotEqual(self.check_config(DATABASE_URL=url).returncode, 0)
    def check_config(self, code='import django; django.setup()', **overrides):
        env = dict(os.environ, DJANGO_SETTINGS_MODULE='config.production', DEBUG='False',
            SECRET_KEY='unit-test-only-' + 'x' * 60, DATABASE_URL='', DB_HOST='', ALLOWED_HOSTS='example.com',
            CSRF_TRUSTED_ORIGINS='', CORS_ALLOWED_ORIGINS='')
        env.update(overrides)
        return subprocess.run([sys.executable, '-B', '-c', code],
            env=env, capture_output=True, text=True, timeout=20)

    def test_cloudfront_proxy_header_and_mandatory_https_protections(self):
        for trusted in ('True', 'False'):
            with self.subTest(TRUST_PROXY_HEADERS=trusted):
                code = '''
import django
django.setup()
from django.conf import settings
from django.test import RequestFactory
from django.middleware.security import SecurityMiddleware
from django.http import HttpResponse
import os
trusted = os.environ['TRUST_PROXY_HEADERS'] == 'True'
expected = ('HTTP_CLOUDFRONT_FORWARDED_PROTO', 'https') if trusted else None
assert settings.SECURE_PROXY_SSL_HEADER == expected
assert settings.SECURE_SSL_REDIRECT is True
assert settings.SESSION_COOKIE_SECURE is True
assert settings.CSRF_COOKIE_SECURE is True
assert settings.SECURE_REDIRECT_EXEMPT == [r'^health/$']
middleware = SecurityMiddleware(lambda request: HttpResponse())
request = RequestFactory().get('/', HTTP_HOST='example.com', HTTP_CLOUDFRONT_FORWARDED_PROTO='https', HTTP_X_FORWARDED_PROTO='http')
assert request.is_secure() is trusted
assert middleware(request).status_code == (200 if trusted else 301)
request = RequestFactory().get('/', HTTP_HOST='example.com', HTTP_CLOUDFRONT_FORWARDED_PROTO='http', HTTP_X_FORWARDED_PROTO='https')
assert request.is_secure() is False
assert middleware(request).status_code == 301
'''
                result = self.check_config(code=code, TRUST_PROXY_HEADERS=trusted,
                    SECURE_SSL_REDIRECT='False',
                    DATABASE_URL='postgresql://user:pass@localhost/db?sslmode=verify-full&sslrootcert=system')
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_production_rejects_sqlite(self):
        result = self.check_config(DATABASE_URL='sqlite:///:memory:')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('PostgreSQL', result.stderr)

    def test_production_rejects_debug_and_unverified_tls(self):
        self.assertNotEqual(self.check_config(DEBUG='True', DATABASE_URL='postgresql://user:pass@localhost/db?sslmode=verify-full&sslrootcert=system').returncode, 0)
        self.assertNotEqual(self.check_config(DATABASE_URL='postgresql://user:pass@localhost/db').returncode, 0)

    def test_postgres_ssl_configuration_loads_without_connecting(self):
        result = self.check_config(DATABASE_URL='postgresql://user:pass@localhost/db?sslmode=verify-full&sslrootcert=system')
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_unsafe_hosts_origins_and_short_secret_rejected(self):
        url = 'postgresql://user:pass@localhost/db?sslmode=verify-full&sslrootcert=system'
        for overrides in ({'ALLOWED_HOSTS': '*'}, {'ALLOWED_HOSTS': '.example.com'},
                          {'CSRF_TRUSTED_ORIGINS': 'http://example.com'}, {'SECRET_KEY': 'short'}):
            with self.subTest(overrides=tuple(overrides)):
                self.assertNotEqual(self.check_config(DATABASE_URL=url, **overrides).returncode, 0)

    def test_missing_database_environment_not_loaded_from_dotenv(self):
        self.assertNotEqual(self.check_config(DATABASE_URL='').returncode, 0)
