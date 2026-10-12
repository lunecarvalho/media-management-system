import os
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command, CommandError
from django.test import TestCase


class BootstrapAdminTests(TestCase):
    credentials = {
        'DJANGO_SUPERUSER_USERNAME': 'first-admin',
        'DJANGO_SUPERUSER_EMAIL': 'admin@example.invalid',
        'DJANGO_SUPERUSER_PASSWORD': 'Unique-bootstrap!49-xZr8',
    }

    def run_bootstrap(self, overrides=None):
        output, errors = StringIO(), StringIO()
        with patch.dict(os.environ, self.credentials | (overrides or {})):
            call_command('bootstrap_render_admin', stdout=output, stderr=errors)
        self.assertNotIn(self.credentials['DJANGO_SUPERUSER_PASSWORD'], output.getvalue() + errors.getvalue())
        return output.getvalue()

    def test_native_command_creates_active_admin_with_hashed_password_and_admin_access(self):
        self.run_bootstrap()
        user = get_user_model().objects.get(username='first-admin')
        self.assertTrue(user.is_superuser and user.is_staff and user.is_active)
        self.assertEqual(user.email, self.credentials['DJANGO_SUPERUSER_EMAIL'])
        self.assertTrue(user.check_password(self.credentials['DJANGO_SUPERUSER_PASSWORD']))
        self.assertNotEqual(user.password, self.credentials['DJANGO_SUPERUSER_PASSWORD'])
        self.client.force_login(user)
        self.assertEqual(self.client.get('/admin/').status_code, 200)

    def test_restart_does_not_duplicate_or_change_password_or_email(self):
        self.run_bootstrap()
        original = get_user_model().objects.get().password
        self.run_bootstrap({'DJANGO_SUPERUSER_PASSWORD': 'Different-secret!94',
                            'DJANGO_SUPERUSER_EMAIL': 'changed@example.invalid'})
        user = get_user_model().objects.get()
        self.assertEqual(user.password, original)
        self.assertEqual(user.email, self.credentials['DJANGO_SUPERUSER_EMAIL'])

    def test_any_existing_superuser_prevents_creation_even_without_credentials(self):
        get_user_model().objects.create_superuser('existing', password='Existing-secret!94')
        self.run_bootstrap({key: '' for key in self.credentials})
        self.assertEqual(get_user_model().objects.count(), 1)

    def test_existing_regular_account_is_not_promoted(self):
        user = get_user_model().objects.create_user('first-admin', password='Original-secret!94')
        original = user.password
        with self.assertRaises(CommandError):
            self.run_bootstrap()
        user.refresh_from_db()
        self.assertFalse(user.is_staff or user.is_superuser)
        self.assertEqual(user.password, original)

    def test_missing_credentials_and_weak_password_create_nothing(self):
        for overrides in ({key: ''} for key in self.credentials):
            with self.subTest(overrides=overrides), self.assertRaises(CommandError):
                self.run_bootstrap(overrides)
        with self.assertRaises(CommandError):
            self.run_bootstrap({'DJANGO_SUPERUSER_PASSWORD': '123'})
        self.assertFalse(get_user_model().objects.exists())

    def test_native_error_is_sanitized_and_creation_is_rolled_back(self):
        secret = self.credentials['DJANGO_SUPERUSER_PASSWORD']

        def failing_command(*args, **kwargs):
            self.assertEqual(args, ('createsuperuser',))
            self.assertFalse(kwargs['interactive'])
            get_user_model().objects.create_superuser('partial', password='Temporary-secret!94')
            kwargs['stderr'].write(secret)
            raise CommandError(secret)

        output, errors = StringIO(), StringIO()
        with patch.dict(os.environ, self.credentials), patch(
            'usuarios.management.commands.bootstrap_render_admin.call_command',
            side_effect=failing_command,
        ), self.assertRaises(CommandError) as raised:
            call_command('bootstrap_render_admin', stdout=output, stderr=errors)
        self.assertNotIn(secret, str(raised.exception) + output.getvalue() + errors.getvalue())
        self.assertFalse(get_user_model().objects.exists())
