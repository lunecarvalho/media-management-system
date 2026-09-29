from unittest.mock import Mock, patch
import requests
from django.test import TestCase
from django.contrib.auth.models import User
from django.core.cache import cache
from acervo.models import Produto
from integracoes.models import FilmeReferencia, LimiteAPI
from usuarios.models import Perfil


class CDTextFlowTests(TestCase):
    code = '7891430074425'
    mbid = '12345678-1234-1234-1234-123456789abc'

    def setUp(self):
        cache.clear()
        user = User.objects.create_user('cd-text')
        Perfil.objects.create(usuario=user)
        self.client.force_login(user)

    def release(self, **kwargs):
        return dict({'id': self.mbid, 'title': 'Perfil 2', 'media': [{'format': 'CD'}],
            'artist-credit': [{'name': 'Chico Buarque'}], 'date': '2001', 'country': 'BR',
            'label-info': [{'label': {'name': 'Gravadora'}, 'catalog-number': 'ABC-12'}]}, **kwargs)

    def search(self, **kwargs):
        return self.client.get('/acervo/buscar-cd/', {'codigo': self.code, **kwargs})

    @patch('integracoes.musicbrainz.requests.get')
    def test_opening_form_does_not_search_and_short_query_is_rejected(self, get):
        self.assertContains(self.search(), 'Buscar no MusicBrainz')
        self.assertContains(self.search(titulo='!'), 'dois caracteres')
        get.assert_not_called()

    @patch('integracoes.musicbrainz.requests.get')
    def test_title_artist_and_both_queries(self, get):
        get.return_value = Mock(status_code=200)
        get.return_value.json.return_value = {'releases': [self.release()]}
        for params in ({'titulo': 'Vida'}, {'artista': 'Chico Buarque'}, {'titulo': 'Perfil 2', 'artista': 'Chico Buarque'}):
            cache.clear()
            LimiteAPI.objects.all().delete()
            response = self.search(**params)
            self.assertContains(response, 'Selecionar esta edição')
            query = get.call_args.kwargs['params']['query']
            self.assertNotIn('barcode:', query)
            self.assertIn('format:CD', query)
            if params.get('titulo'): self.assertIn('release:', query)
            if params.get('artista'): self.assertIn('artist:', query)
        self.assertFalse(Produto.objects.exists())

    @patch('integracoes.musicbrainz.requests.get')
    def test_barcode_missing_then_explicit_selection_preserves_physical_ean(self, get):
        get.return_value = Mock(status_code=200)
        get.return_value.json.return_value = {'releases': []}
        # Use named route to avoid coupling to the API URL spelling.
        from django.urls import reverse
        missing = self.client.get(reverse('api:exemplar-por-codigo', args=[self.code]), {'metadados': '1'})
        self.assertEqual(missing.status_code, 404)
        self.assertIn('busca_cd_url', missing.json())
        for barcode in ('', '0012345678905'):
            cache.clear()
            LimiteAPI.objects.all().delete()
            get.return_value.json.return_value = {'releases': [self.release(title='Outra edição'), self.release(barcode=barcode)]}
            response = self.search(titulo='Perfil 2', artista='Chico Buarque')
            rows = response.context['results']
            self.assertEqual(len(rows), 2)
            self.assertFalse(Produto.objects.exists())
            cache.clear()
            form = self.client.get(rows[1]['cadastro_url']).context['form'].product_form
            self.assertEqual(form['ean'].value(), self.code)
            self.assertEqual(form['titulo'].value(), 'Perfil 2')
            from urllib.parse import parse_qs, urlsplit
            token = parse_qs(urlsplit(rows[1]['cadastro_url']).query)['leitura'][0]
            saved = self.client.session['barcode_prefill'][token]['dados']
            self.assertEqual(saved['origem'], 'MusicBrainz')
            self.assertEqual(saved['identificadores']['musicbrainz_release_id'], self.mbid)
            self.assertEqual(saved['metadados']['barcode_musicbrainz'], barcode)
            self.assertEqual(saved['metadados']['catalogos'], ['ABC-12'])

    @patch('integracoes.musicbrainz.requests.get')
    def test_empty_and_errors_keep_manual_ean(self, get):
        get.return_value = Mock(status_code=200)
        get.return_value.json.return_value = {'releases': []}
        response = self.search(titulo='Vida')
        self.assertContains(response, 'Nenhum CD correspondente')
        for error, message in [(requests.Timeout(), 'demorou'), (requests.ConnectionError(), 'Não foi possível')]:
            cache.clear()
            LimiteAPI.objects.all().delete()
            get.side_effect = error
            response = self.search(titulo='Vida')
            self.assertContains(response, message)
            self.assertNotContains(response, 'Nenhum CD correspondente')
            form = self.client.get(response.context['manual_url']).context['form'].product_form
            self.assertEqual(form['ean'].value(), self.code)

    @patch('integracoes.musicbrainz.requests.get')
    def test_dvd_cannot_enter_text_search(self, get):
        FilmeReferencia.objects.create(ean=self.code, titulo='DVD', diretor='Diretor', ano=2000)
        response = self.search(titulo='Vida')
        self.assertEqual(response.status_code, 302)
        response = self.client.get(response.url)
        self.assertNotContains(response, 'Buscar CD por título/artista')
        get.assert_not_called()
