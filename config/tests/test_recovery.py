import json
import os
from pathlib import Path
import tempfile
from unittest.mock import patch
from django.test import SimpleTestCase
from scripts import recover_eb as recovery


class RecoveryTests(SimpleTestCase):
    def setUp(self):
        self.calls = []
        self.env = dict(ApplicationName=recovery.APPLICATION, EnvironmentName=recovery.ENVIRONMENT,
                        EnvironmentId=recovery.ENVIRONMENT_ID, Status='Ready', Health='Green', VersionLabel=None)
        values = dict(DJANGO_SETTINGS_MODULE='config.production', DEBUG='False',
                      ALLOWED_HOSTS='app.example.com', CSRF_TRUSTED_ORIGINS='https://app.example.com',
                      SECRET_KEY='test-only', DATABASE_URL='test-only')
        self.config = {'ConfigurationSettings': [{'OptionSettings': [
            {'Namespace': 'aws:elasticbeanstalk:application:environment', 'OptionName': k, 'Value': v}
            for k, v in values.items()]}]}
        self.updated = False

    def call(self, service, operation, *args):
        self.calls.append((service, operation, args))
        if operation == 'get-caller-identity':
            return dict(Account=recovery.ACCOUNT, Arn=f'arn:aws:sts::{recovery.ACCOUNT}:assumed-role/MediaTrackGitHubDeployRole/test')
        if operation == 'describe-environments':
            return {'Environments': [dict(self.env, VersionLabel=recovery.VERSION) if self.updated else self.env]}
        if operation == 'describe-application-versions':
            return {'ApplicationVersions': [dict(VersionLabel=recovery.VERSION, Status='UNPROCESSED',
                    SourceBundle=dict(S3Bucket=recovery.BUCKET, S3Key=recovery.KEY))]}
        if operation == 'head-object':
            return dict(ContentLength=98945, ETag=recovery.ETAG)
        if operation == 'describe-configuration-settings':
            return self.config
        if operation == 'update-environment':
            self.updated = True
        if operation == 'describe-events':
            return {'Events': []}
        return {}

    def test_preflight_never_mutates(self):
        self.assertEqual(recovery.recover(self.call)['preflight'], 'passed')
        self.assertFalse(self.updated)
        self.assertNotIn('update-environment', [c[1] for c in self.calls])

    def test_wrong_destination_or_busy_environment_blocks_update(self):
        for change in ({'EnvironmentId': 'other'}, {'Status': 'Updating'},
                       {'ApplicationName': 'other'}, {'AbortableOperationInProgress': True}):
            original = self.env
            self.env = dict(original, **change)
            with self.assertRaises(ValueError):
                recovery.recover(self.call, execute=True)
            self.env = original
        self.assertFalse(self.updated)

    def test_missing_configuration_blocks_update(self):
        self.config['ConfigurationSettings'][0]['OptionSettings'] = []
        with self.assertRaises(ValueError):
            recovery.recover(self.call, execute=True)
        self.assertFalse(self.updated)

    def test_changed_package_blocks_update(self):
        def call(*args):
            return {'ContentLength': 98945, 'ETag': 'changed'} if args[1] == 'head-object' else self.call(*args)
        with self.assertRaises(ValueError):
            recovery.recover(call, execute=True)
        self.assertFalse(self.updated)

    def test_wrong_account_role_or_version_blocks_update(self):
        replacements = {
            'get-caller-identity': {'Account': 'other', 'Arn': 'other'},
            'describe-application-versions': {'ApplicationVersions': []},
        }
        for operation, response in replacements.items():
            def call(*args):
                return response if args[1] == operation else self.call(*args)
            with self.assertRaises(ValueError):
                recovery.recover(call, execute=True)
        with self.assertRaises(ValueError):
            recovery.recover(lambda *args: {'Account': recovery.ACCOUNT, 'Arn': 'wrong'}, execute=True)
        self.assertFalse(self.updated)

    def test_success_requires_five_http_and_version_checks_and_one_update(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, RUNNER_TEMP=directory):
            probes = []
            result = recovery.recover(self.call, execute=True, sleep=lambda _: None,
                                      check_http=lambda origin: probes.append(origin) or True)
            self.assertEqual(result['consecutive_checks'], 5)
            self.assertEqual(len(probes), 5)
            self.assertEqual([c[1] for c in self.calls].count('update-environment'), 1)
            self.assertIsNone(json.loads((Path(directory) / 'eb-before.json').read_text())['Environments'][0]['VersionLabel'])

    def test_error_event_stops_without_retry(self):
        def call(*args):
            return {'Events': [{'Severity': 'ERROR'}]} if args[1] == 'describe-events' else self.call(*args)
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, RUNNER_TEMP=directory):
            with self.assertRaises(ValueError):
                recovery.recover(call, execute=True, sleep=lambda _: None)
        self.assertEqual([c[1] for c in self.calls].count('update-environment'), 1)

    def test_timeout_is_not_success(self):
        ticks = iter([0, 1801])
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, RUNNER_TEMP=directory):
            with self.assertRaises(ValueError):
                recovery.recover(self.call, execute=True, clock=lambda: next(ticks), sleep=lambda _: None)
        self.assertEqual([c[1] for c in self.calls].count('update-environment'), 1)
