from unittest.mock import patch, Mock
from django.core.cache import cache
from django.test import TestCase
from integracoes.musicbrainz import pesquisar, FonteIndisponivel

class MusicBrainzTests(TestCase):
    def setUp(self): cache.clear()

    @patch('integracoes.musicbrainz.requests.get')
    def test_search_mapping_cache_and_headers(self, get):
        get.return_value = Mock(status_code=200)
        get.return_value.json.return_value = {'releases': [{'id': '12345678-1234-1234-1234-123456789abc', 'title': 'Album', 'media': [{'format': 'CD'}], 'date': '2001-01-01', 'artist-credit': [{'name': 'Band'}]}]}
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

    @patch('integracoes.musicbrainz.requests.get')
    def test_barcode_flow_reuses_provider_with_cd_format_filter(self, get):
        get.return_value = Mock(status_code=200)
        get.return_value.json.return_value = {'releases': []}
        pesquisar(ean='7891234567895', somente_cd=True)
        self.assertEqual(get.call_args.kwargs['params']['query'], 'barcode:"7891234567895" AND format:CD')
        self.assertIn('User-Agent', get.call_args.kwargs['headers'])

    @patch('integracoes.musicbrainz.requests.get')
    def test_invalid_json_shape_is_reported_as_provider_failure(self, get):
        get.return_value = Mock(status_code=200)
        get.return_value.json.return_value = []
        with self.assertRaises(FonteIndisponivel):
            pesquisar(ean='7891234567895', somente_cd=True)

    @patch('integracoes.musicbrainz.requests.get')
    def test_only_explicit_cd_media_are_accepted_in_all_searches(self, get):
        base = {'id': '12345678-1234-1234-1234-123456789abc', 'title': 'Album', 'barcode': '0012345678905'}
        cases = [None, [], [{'format': 'Cassette'}], [{'format': 'Vinyl'}], [{'format': 'Digital Media'}], [{'format': 'DVD'}],
                 [{}], [{'format': 'CD'}, {'format': 'DVD'}], [None]]
        get.return_value = Mock(status_code=200)
        get.return_value.json.return_value = {'releases': [dict(base, media=media) for media in cases] +
            [dict(base, media=[{'format': 'CD'}, {'format': 'CD'}]) , base]}
        rows = pesquisar('Album', somente_cd=False)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['tipo'], 'CD')
        self.assertEqual(rows[0]['origem'], 'MusicBrainz')
        self.assertEqual(rows[0]['metadados']['formatos'], ['CD', 'CD'])
        self.assertIn('format:CD', get.call_args.kwargs['params']['query'])
        self.assertEqual(rows[0]['identificadores']['musicbrainz_release_id'], base['id'])

    @patch('integracoes.musicbrainz.requests.get')
    def test_barcode_match_must_be_exact(self, get):
        get.return_value = Mock(status_code=200)
        get.return_value.json.return_value = {'releases': [
            {'id': '12345678-1234-1234-1234-123456789abc', 'title': 'Album', 'media': [{'format': 'CD'}],
             'barcode': code} for code in ('0012345678905', '1234567890123', '')]}
        rows = pesquisar(ean='0012345678905')
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['ean'], '0012345678905')

    @patch('integracoes.musicbrainz.requests.get')
    def test_timeout_is_handled(self, get):
        import requests
        get.side_effect = requests.Timeout('test timeout')
        with self.assertRaises(FonteIndisponivel):
            pesquisar(ean='0012345678905')
