from django.test import SimpleTestCase
from scripts.validate_eb_environment import validate
from scripts.collect_eb_diagnostics import environment_summary, event_summary, query
from unittest.mock import patch
import subprocess


class DeploymentTests(SimpleTestCase):
    def payload(self, **overrides):
        environment = {'ApplicationName': 'test-app', 'EnvironmentName': 'test-env',
                       'Status': 'Ready', 'Health': 'Green', 'VersionLabel': 'test-version',
                       'AbortableOperationInProgress': False}
        environment.update(overrides)
        return {'Environments': [environment]}

    def test_existing_destination_records_previous_version(self):
        self.assertEqual(validate(self.payload(), 'test-app', 'test-env'), 'test-version')

    def test_missing_or_ambiguous_destination_rejected(self):
        for items in ([], self.payload()['Environments'] * 2):
            with self.assertRaises(ValueError):
                validate({'Environments': items}, 'test-app', 'test-env')

    def test_wrong_destination_rejected(self):
        for change in ({'ApplicationName': 'other'}, {'EnvironmentName': 'other'}):
            with self.assertRaises(ValueError):
                validate(self.payload(**change), 'test-app', 'test-env')

    def test_concurrent_update_rejected(self):
        for change in ({'Status': 'Updating'}, {'AbortableOperationInProgress': True}):
            with self.assertRaises(ValueError):
                validate(self.payload(**change), 'test-app', 'test-env')

    def test_success_requires_expected_version_and_health(self):
        for change in ({'VersionLabel': 'old'}, {'VersionLabel': None},
                       {'Health': 'Red'}, {'Health': 'Yellow'}):
            with self.assertRaises(ValueError):
                validate(self.payload(**change), 'test-app', 'test-env', 'test-version')
        self.assertEqual(validate(self.payload(), 'test-app', 'test-env', 'test-version'), 'test-version')

    def test_diagnostics_exclude_messages_urls_and_unknown_fields(self):
        payload = self.payload(EnvironmentVariables={'SECRET_KEY': 'private'},
                               EndpointURL='https://example.invalid/?signature=private')
        summary = environment_summary(payload)
        self.assertNotIn('EnvironmentVariables', summary[0])
        self.assertNotIn('EndpointURL', summary[0])
        event = {'Severity': 'ERROR', 'RequestId': 'correlation',
                 'Message': 'https://example.invalid/?signature=private',
                 'UnknownSecret': 'private'}
        self.assertEqual(event_summary({'Events': [event]}),
                         [{'Severity': 'ERROR', 'RequestId': 'correlation'}])

    @patch('scripts.collect_eb_diagnostics.subprocess.run')
    def test_diagnostics_do_not_expose_cli_error_output(self, run):
        run.return_value = subprocess.CompletedProcess([], 1, 'private', 'private')
        self.assertEqual(query(['describe-events'], 'sa-east-1', 'mediatrack-production'),
                         ({}, 'aws_query_failed'))
        self.assertIn('--profile', run.call_args.args[0])
        run.side_effect = subprocess.TimeoutExpired('aws', 45, output='private')
        self.assertEqual(query(['describe-events'], 'sa-east-1'),
                         ({}, 'aws_query_unavailable'))
