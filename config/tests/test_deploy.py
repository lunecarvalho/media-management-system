from django.test import SimpleTestCase
from scripts.validate_eb_environment import validate


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
        for change in ({'VersionLabel': 'old'}, {'Health': 'Red'}, {'Health': 'Yellow'}):
            with self.assertRaises(ValueError):
                validate(self.payload(**change), 'test-app', 'test-env', 'test-version')
        self.assertEqual(validate(self.payload(), 'test-app', 'test-env', 'test-version'), 'test-version')
