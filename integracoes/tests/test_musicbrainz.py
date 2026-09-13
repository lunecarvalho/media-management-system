from unittest.mock import patch, Mock
from django.core.cache import cache
from django.test import TestCase
from integracoes.musicbrainz import pesquisar, FonteIndisponivel

class MusicBrainzTests(TestCase):
    def setUp(self): cache.clear()

    @patch('integracoes.musicbrainz.requests.get')
    def test_search_mapping_cache_and_headers(self, get):
        get.return_value = Mock(status_code=200)
        get.return_value.json.return_value = {'releases': [{'id': '12345678-1234-1234-1234-123456789abc', 'title': 'Album', 'date': '2001-01-01', 'artist-credit': [{'name': 'Band'}]}]}
        results = pesquisar('Album')
        self.assertEqual(results[0]['ano'], 2001)
        self.assertEqual(results[0]['artista_diretor'], 'Band')
        self.assertEqual(pesquisar('Album'), results)
        self.assertEqual(get.call_count, 1)
        self.assertIn('User-Agent', get.call_args.kwargs['headers'])
        self.assertEqual(get.call_args.kwargs['timeout'], (3.05, 10))

    @patch('integracoes.musicbrainz.requests.get')
    def test_rate_limit_shared_in_database(self, get):
        get.return_value = Mock(status_code=200)
        get.return_value.json.return_value = {'releases': []}
        pesquisar('first')
        with self.assertRaises(FonteIndisponivel): pesquisar('second')
        self.assertEqual(get.call_count, 1)

    @patch('integracoes.musicbrainz.requests.get')
    def test_unavailable(self, get):
        get.return_value = Mock(status_code=503)
        with self.assertRaises(FonteIndisponivel): pesquisar('Album')
