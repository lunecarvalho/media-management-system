import dj_database_url
from django.test import SimpleTestCase


class EnvironmentTests(SimpleTestCase):
    def test_database_url_decodes_credentials_and_ssl(self):
        db = dj_database_url.parse('postgresql://user:p%40ss@localhost/database?sslmode=verify-full')
        self.assertEqual(db['PASSWORD'], 'p@ss')
        self.assertEqual(db['OPTIONS']['sslmode'], 'verify-full')

    def test_logout_requires_post(self):
        self.assertEqual(self.client.get('/usuarios/logout/').status_code, 405)
