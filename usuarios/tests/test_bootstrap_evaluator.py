import os
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django.test import TestCase

from usuarios.models import Perfil


class BootstrapEvaluatorTests(TestCase):
    credentials = {
        'DJANGO_EVALUATOR_USERNAME': 'academic-evaluator',
        'DJANGO_EVALUATOR_EMAIL': 'evaluator@example.invalid',
        'DJANGO_EVALUATOR_PASSWORD': 'Unique-evaluator!49-xZr8',
    }

    def run_bootstrap(self, overrides=None):
        output, errors = StringIO(), StringIO()
        with patch.dict(os.environ, self.credentials | (overrides or {})):
            call_command('bootstrap_render_evaluator', stdout=output, stderr=errors)
        self.assertNotIn(self.credentials['DJANGO_EVALUATOR_PASSWORD'], output.getvalue() + errors.getvalue())
        return output.getvalue()

    def test_command_creates_safe_evaluator_profile(self):
        self.run_bootstrap()
        user = get_user_model().objects.get(username='academic-evaluator')

        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertEqual(user.perfil.tipo, 'avaliador')
        self.assertTrue(user.perfil.ativo)
        self.assertTrue(user.check_password(self.credentials['DJANGO_EVALUATOR_PASSWORD']))

    def test_repeated_command_does_not_change_existing_evaluator(self):
        self.run_bootstrap()
        user = get_user_model().objects.get(username='academic-evaluator')
        original_password = user.password

        self.run_bootstrap({
            'DJANGO_EVALUATOR_EMAIL': 'changed@example.invalid',
            'DJANGO_EVALUATOR_PASSWORD': 'Different-evaluator!94',
        })

        user.refresh_from_db()
        self.assertEqual(user.password, original_password)
        self.assertEqual(user.email, self.credentials['DJANGO_EVALUATOR_EMAIL'])
        self.assertEqual(Perfil.objects.count(), 1)

    def test_existing_account_is_not_promoted(self):
        user = get_user_model().objects.create_user(
            'academic-evaluator', password='Original-secret!94',
        )
        original_password = user.password

        with self.assertRaises(CommandError):
            self.run_bootstrap()

        user.refresh_from_db()
        self.assertFalse(user.is_staff or user.is_superuser)
        self.assertEqual(user.password, original_password)
        self.assertFalse(Perfil.objects.exists())

    def test_missing_or_weak_credentials_create_nothing(self):
        for key in self.credentials:
            with self.subTest(key=key), self.assertRaises(CommandError):
                self.run_bootstrap({key: ''})
        with self.assertRaises(CommandError):
            self.run_bootstrap({'DJANGO_EVALUATOR_PASSWORD': '123'})
        self.assertFalse(get_user_model().objects.exists())
