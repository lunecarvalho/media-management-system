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
    def check_config(self, **overrides):
        env = dict(os.environ, DJANGO_SETTINGS_MODULE='config.production', DEBUG='False',
            SECRET_KEY='unit-test-only-' + 'x' * 60, DATABASE_URL='', DB_HOST='', ALLOWED_HOSTS='example.com',
            CSRF_TRUSTED_ORIGINS='', CORS_ALLOWED_ORIGINS='')
        env.update(overrides)
        return subprocess.run([sys.executable, '-B', '-c', 'import django; django.setup()'],
            env=env, capture_output=True, text=True, timeout=20)

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
