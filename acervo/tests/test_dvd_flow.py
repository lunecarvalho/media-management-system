from unittest.mock import Mock, patch
from urllib.parse import urlsplit, parse_qs

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from acervo.models import Categoria, Produto, Exemplar
from integracoes.models import FilmeReferencia
from integracoes.dvd_dataset import SOURCE
from usuarios.models import Perfil


class DVDFlowTests(TestCase):
    code = '7892110019392'

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user('dvd-flow')
        Perfil.objects.create(usuario=self.user)
        self.client.force_login(self.user)
        self.category = Categoria.objects.create(nome='Filmes')
        self.url = reverse('api:exemplar-por-codigo', args=[self.code])

    def dvd(self):
        return FilmeReferencia.objects.create(ean=self.code, titulo='MATRIX', titulo_original='MATRIX',
            diretor='Lana Wachowski, Lilly Wachowski', ano=1999)

    def post_data(self, row):
        data = {f'produto-{key}': row[key] for key in ('tipo', 'titulo', 'artista_diretor', 'ean', 'ano')}
        data.update({'produto-categoria': self.category.pk, 'codigo_interno': 'EX-DVD',
                     'estado_conservacao': 'bom', 'status': 'disponivel'})
        return data

    @patch('integracoes.musicbrainz.requests.get')
    def test_dvd_priority_and_confirmed_registration_preserve_source(self, get):
        self.dvd()
        for query in ({}, {'metadados': '1'}):
            response = self.client.get(self.url, query)
            self.assertEqual(response.status_code, 200)
            data = response.json()
            row = data['results'][0]
            self.assertEqual(data['fonte'], SOURCE)
            self.assertEqual((row['tipo'], row['titulo'], row['artista_diretor'], row['ano']),
                ('DVD', 'MATRIX', 'Lana Wachowski, Lilly Wachowski', 1999))
        get.assert_not_called()
        self.assertFalse(Produto.objects.exists())
        target = row['cadastro_url']
        # Apagar o cache local não perde o pré-preenchimento persistido na sessão.
        cache.clear()
        page = self.client.get(target)
        self.assertEqual(page.context['form'].product_form['tipo'].value(), 'DVD')
        response = self.client.post(target, self.post_data(row))
        self.assertEqual(response.status_code, 302)
        product = Produto.objects.get()
        self.assertEqual(product.origem, SOURCE)
        self.assertEqual(product.identificadores, {'dvd_ean': self.code})
        self.assertEqual(Exemplar.objects.count(), 1)

    @patch('integracoes.musicbrainz.requests.get')
    def test_existing_catalog_precedes_reference_and_provider(self, get):
        self.dvd()
        product = Produto.objects.create(tipo='CD', titulo='Já cadastrado', artista_diretor='Autor',
            ean=self.code, categoria=self.category)
        data = self.client.get(self.url, {'metadados': '1'}).json()
        self.assertEqual(data['produto']['id'], product.pk)
        self.assertEqual(data['produto']['tipo'], 'CD')
        item = Exemplar.objects.create(produto=product, codigo_interno=self.code, usuario_responsavel=self.user)
        self.assertEqual(self.client.get(self.url, {'metadados': '1'}).json()['id'], item.pk)
        get.assert_not_called()

    @patch('integracoes.musicbrainz.requests.get')
    def test_cd_fallback_uses_real_mapper_and_preserves_provenance(self, get):
        get.return_value = Mock(status_code=200)
        mbid = '12345678-1234-1234-1234-123456789abc'
        get.return_value.json.return_value = {'releases': [{'id': mbid, 'title': 'Album',
            'barcode': self.code, 'date': '2001', 'artist-credit': [{'name': 'Artista'}],
            'media': [{'format': 'CD'}], 'country': 'BR'}]}
        response = self.client.get(self.url, {'metadados': '1'})
        self.assertEqual(response.status_code, 200)
        row = response.json()['results'][0]
        self.assertEqual(row['tipo'], 'CD')
        self.assertIn('barcode:', get.call_args.kwargs['params']['query'])
        self.assertEqual(self.client.post(row['cadastro_url'], self.post_data(row)).status_code, 302)
        product = Produto.objects.get()
        self.assertEqual(product.origem, 'MusicBrainz')
        self.assertEqual(product.identificadores['musicbrainz_release_id'], mbid)
        self.assertEqual(product.metadados['formatos'], ['CD'])

    @patch('integracoes.musicbrainz.requests.get')
    def test_unknown_and_unavailable_allow_manual_without_fabricated_metadata(self, get):
        get.return_value = Mock(status_code=200)
        get.return_value.json.return_value = {'releases': []}
        response = self.client.get(self.url, {'metadados': '1'})
        self.assertEqual(response.status_code, 404)
        form = self.client.get(response.json()['cadastro_url']).context['form'].product_form
        self.assertEqual(form['ean'].value(), self.code)
        for field in ('tipo', 'titulo', 'artista_diretor', 'ano'):
            self.assertIn(form[field].value(), (None, ''))
        from integracoes.models import LimiteAPI
        cache.clear()
        LimiteAPI.objects.all().delete()
        import requests
        get.side_effect = requests.Timeout('simulated')
        response = self.client.get(self.url, {'metadados': '1'})
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()['erro']['codigo'], 'fonte_indisponivel')
        self.assertEqual(self.client.get(response.json()['cadastro_url']).context['form'].product_form['ean'].value(), self.code)
        self.assertFalse(Produto.objects.exists())

    @patch('integracoes.musicbrainz.requests.get')
    def test_html_without_javascript_and_metadata_search_use_local_dvd(self, get):
        self.dvd()
        response = self.client.get('/codigo-barras/', {'codigo': self.code})
        self.assertContains(response, 'MATRIX')
        self.assertContains(response, 'Conferir e cadastrar')
        self.assertContains(response, 'Lana Wachowski, Lilly Wachowski')
        response = self.client.get('/acervo/metadados/', {'ean': self.code, 'fonte': 'movies'})
        self.assertContains(response, 'MATRIX')
        key = next(iter(self.client.session['metadados_escolhas']))
        response = self.client.post('/acervo/metadados/', {'escolha': key})
        self.assertEqual(response.context['product_form']['ean'].value(), self.code)
        response = self.client.get('/acervo/metadados/', {'ean': self.code, 'fonte': 'musicbrainz'})
        self.assertContains(response, 'MATRIX')
        get.assert_not_called()

    def test_modified_type_or_ean_cannot_reuse_source_metadata(self):
        self.dvd()
        row = self.client.get(self.url).json()['results'][0]
        for field, value in [('tipo', 'CD'), ('ean', '0012345678905')]:
            data = self.post_data(row)
            data[f'produto-{field}'] = value
            response = self.client.post(row['cadastro_url'], data)
            self.assertEqual(response.status_code, 200)
            self.assertIn(field, response.context['form'].product_form.errors)
        self.assertFalse(Produto.objects.exists())

    def test_expired_session_entry_keeps_ean_for_manual_registration(self):
        self.dvd()
        row = self.client.get(self.url).json()['results'][0]
        token = parse_qs(urlsplit(row['cadastro_url']).query)['leitura'][0]
        session = self.client.session
        session['barcode_prefill'][token]['expira'] = 0
        session.save()
        response = self.client.get(row['cadastro_url'])
        self.assertContains(response, 'expiraram')
        form = response.context['form'].product_form
        self.assertEqual(form['ean'].value(), self.code)
        self.assertIn(form['titulo'].value(), (None, ''))

    @patch('acervo.barcode_flow.pesquisar')
    def test_html_provider_failure_is_distinct_from_missing(self, search):
        from integracoes.musicbrainz import FonteIndisponivel
        search.side_effect = FonteIndisponivel('MusicBrainz indisponível')
        response = self.client.get('/codigo-barras/', {'codigo': self.code})
        self.assertContains(response, 'Consulta de metadados indisponível')
        self.assertContains(response, 'data-state="error"')
        self.assertContains(response, f'codigo={self.code}')
        self.assertNotContains(response, 'Código não encontrado no sistema')
