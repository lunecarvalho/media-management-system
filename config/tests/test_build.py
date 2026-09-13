import tempfile
from pathlib import Path
from zipfile import ZipFile
from unittest.mock import patch
from django.test import TestCase
from django.db import DatabaseError
from scripts.build_bundle import bundle
import hashlib
import certifi
from django.core.management import call_command
from django.test import Client, override_settings
from django.contrib.staticfiles.storage import staticfiles_storage


class BuildTests(TestCase):
    def test_collected_static_is_served_without_runserver(self):
        with tempfile.TemporaryDirectory() as directory:
            with override_settings(STATIC_ROOT=directory, DEBUG=False, STORAGES={
                'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
                'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'},
            }):
                call_command('collectstatic', interactive=False, verbosity=0)
                url = staticfiles_storage.url('css/dashboard-fixed.css')
                response = Client().get(url)
                self.assertEqual(response.status_code, 200)
                self.assertIn('text/css', response['Content-Type'])
                self.assertIn('immutable', response['Cache-Control'])
                response.close()

    def test_bundle_excludes_secrets_and_development_compose(self):
        with tempfile.TemporaryDirectory() as directory:
            target = bundle(Path(directory) / 'test.zip')
            with ZipFile(target) as archive:
                names = archive.namelist()
            self.assertIn('Dockerfile', names)
            self.assertIn('config/production.py', names)
            self.assertNotIn('docker-compose.yml', names)
            self.assertFalse(any(n.endswith('.sqlite3') or '/.env' in n or n == '.env' for n in names))

    def test_health_does_not_require_authentication(self):
        self.assertEqual(self.client.get('/health/').json(), {'status': 'ok'})

    @patch('config.views.connection.cursor', side_effect=DatabaseError('sensitive'))
    def test_health_does_not_expose_database_errors(self, cursor):
        response = self.client.get('/health/')
        self.assertEqual(response.status_code, 503)
        self.assertNotContains(response, 'sensitive', status_code=503)

    def test_bundle_is_reproducible(self):
        with tempfile.TemporaryDirectory() as directory:
            first = bundle(Path(directory) / 'first.zip')
            second = bundle(Path(directory) / 'second.zip')
            self.assertEqual(hashlib.sha256(first.read_bytes()).digest(), hashlib.sha256(second.read_bytes()).digest())

    def test_bundle_excludes_nested_credentials(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ('Dockerfile', 'requirements.txt', '.python-version', 'manage.py', '.dockerignore'):
                (root / name).write_text('test')
            (root / 'config').mkdir()
            for name in ('.env', 'secret.pem', 'private.key', 'db.sqlite3', 'settings.py'):
                (root / 'config' / name).write_text('test')
            with patch('scripts.build_bundle.ROOT', root):
                target = bundle(root / 'output.zip')
            with ZipFile(target) as archive:
                self.assertIn('config/settings.py', archive.namelist())
                self.assertNotIn('config/.env', archive.namelist())
                self.assertNotIn('config/secret.pem', archive.namelist())
                self.assertNotIn('config/private.key', archive.namelist())

    def test_public_ca_can_be_added_but_private_key_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            target = bundle(Path(directory) / 'cert.zip', certifi.where())
            with ZipFile(target) as archive:
                self.assertIn('certs/rds-ca.pem', archive.namelist())
            private = Path(directory) / 'private.pem'
            private.write_text('-----BEGIN PRIVATE KEY-----')
            with self.assertRaises(ValueError):
                bundle(Path(directory) / 'rejected.zip', private)
