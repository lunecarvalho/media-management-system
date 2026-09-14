from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User

from acervo.models import Produto, Exemplar, Categoria
from integracoes.musicbrainz import FonteIndisponivel
from usuarios.models import Perfil


class BarcodeFlowTests(TestCase):
    code = '7891234567895'

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user('barcode-flow')
        Perfil.objects.create(usuario=self.user)
        self.client.force_login(self.user)
        self.category = Categoria.objects.create(nome='Geral')
        self.url = reverse('api:exemplar-por-codigo', args=[self.code])
        self.row = {'tipo': 'CD', 'titulo': 'Edição de teste', 'artista_diretor': 'Artista',
                    'ean': self.code, 'ano': 2001, 'gravadora_distribuidora': 'Editora',
                    'descricao': 'Descrição da edição', 'metadados': {'generos': ['Não criar']}}

    def assert_no_registration(self):
        self.assertEqual(Produto.objects.count(), 0)
        self.assertEqual(Exemplar.objects.count(), 0)
        self.assertEqual(Categoria.objects.count(), 1)

    @patch('acervo.barcode_flow.pesquisar')
    def test_local_missing_never_requests_external_automatically(self, search):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 404)
        self.assertTrue(response.json()['metadados_disponiveis'])
        self.assertIn('cadastro_url', response.json())
        search.assert_not_called()
        self.assert_no_registration()

    @patch('acervo.barcode_flow.pesquisar')
    def test_local_product_and_copy_take_priority_even_with_external_option(self, search):
        product = Produto.objects.create(tipo='DVD', titulo='Local', artista_diretor='Diretor',
                                         ean=self.code, categoria=self.category)
        data = self.client.get(self.url, {'metadados': '1'}).json()
        self.assertEqual(data['tipo_codigo'], 'ean')
        self.assertEqual(data['produto']['categoria_nome'], 'Geral')
        copy = Exemplar.objects.create(produto=product, codigo_interno=self.code, usuario_responsavel=self.user)
        data = self.client.get(self.url, {'metadados': '1'}).json()
        self.assertEqual(data['id'], copy.pk)
        self.assertEqual(self.client.get(self.url, {'modo': 'ean', 'metadados': '1'}).json()['tipo_codigo'], 'ean')
        search.assert_not_called()
        self.assertEqual(Produto.objects.count(), 1)
        self.assertEqual(Exemplar.objects.count(), 1)

    @patch('acervo.barcode_flow.pesquisar')
    def test_explicit_search_prefills_real_form_without_saving(self, search):
        search.return_value = [self.row]
        response = self.client.get(self.url, {'metadados': '1'})
        self.assertEqual(response.status_code, 200)
        search.assert_called_once_with(ean=self.code, somente_cd=True)
        data = response.json()
        self.assertEqual(data['tipo_codigo'], 'externo')
        target = data['results'][0]['cadastro_url']
        self.assertNotIn('titulo=', target)
        form_response = self.client.get(target)
        form = form_response.context['form']
        for field in ('tipo', 'titulo', 'artista_diretor', 'ean', 'ano', 'gravadora_distribuidora', 'descricao'):
            self.assertEqual(form.product_form[field].value(), self.row[field])
        self.assertIsNone(form.product_form['categoria'].value())
        self.assertIsNone(form['codigo_interno'].value())
        self.assertIsNone(form['preco'].value())
        self.assertEqual(form['status'].value(), 'disponivel')
        self.assertContains(form_response, 'Nada foi salvo ainda')
        self.assert_no_registration()

    @patch('acervo.barcode_flow.pesquisar')
    def test_missing_fields_and_ambiguous_editions_remain_separate(self, search):
        search.return_value = [{'tipo': 'CD', 'titulo': 'Primeira'}, {'tipo': 'CD', 'titulo': 'Segunda'}]
        data = self.client.get(self.url, {'metadados': '1'}).json()
        self.assertEqual(len(data['results']), 2)
        targets = [row['cadastro_url'] for row in data['results']]
        self.assertNotEqual(*targets)
        form = self.client.get(targets[1]).context['form'].product_form
        self.assertEqual(form['titulo'].value(), 'Segunda')
        for field in ('artista_diretor', 'ano', 'gravadora_distribuidora', 'descricao', 'categoria'):
            self.assertIn(form[field].value(), (None, ''))
        self.assert_no_registration()

    @patch('acervo.barcode_flow.pesquisar')
    def test_provider_failure_empty_and_wrong_barcode_do_not_save(self, search):
        search.side_effect = FonteIndisponivel('Fonte indisponível')
        response = self.client.get(self.url, {'metadados': '1'})
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()['erro']['codigo'], 'fonte_indisponivel')
        search.side_effect = None
        for rows in ([], [{**self.row, 'ean': '0000000000000'}], [{**self.row, 'tipo': 'DVD'}]):
            search.return_value = rows
            self.assertEqual(self.client.get(self.url, {'metadados': '1'}).status_code, 404)
        self.assert_no_registration()

    @patch('acervo.barcode_flow.pesquisar')
    def test_internal_mode_and_invalid_codes_do_not_query_musicbrainz(self, search):
        self.assertFalse(self.client.get(self.url, {'modo': 'interno'}).json()['metadados_disponiveis'])
        self.assertEqual(self.client.get(self.url, {'modo': 'interno', 'metadados': '1'}).status_code, 404)
        for code in ('MT-20', '123'):
            url = reverse('api:exemplar-por-codigo', args=[code])
            self.assertEqual(self.client.get(url, {'metadados': '1'}).status_code, 404)
        for code in ('has space', 'x' * 41):
            url = reverse('api:exemplar-por-codigo', args=[code])
            self.assertEqual(self.client.get(url).status_code, 400)
        search.assert_not_called()

    def test_manual_registration_preserves_code_without_guessing_type(self):
        for mode, code, field in [('auto', self.code, 'ean'), ('ean', '789123', 'ean'), ('interno', self.code, 'codigo_interno'), ('auto', 'MT.1/2', 'codigo_interno')]:
            response = self.client.get(reverse('acervo:cadastrar'), {'codigo': code, 'modo': mode})
            form = response.context['form']
            self.assertEqual((form.product_form if field == 'ean' else form)[field].value(), code)
            self.assertIn(form.product_form['tipo'].value(), (None, ''))
            self.assertIsNone(form.product_form['categoria'].value())
        self.assert_no_registration()

    @patch('acervo.barcode_flow.pesquisar')
    def test_prefill_is_scoped_to_user_and_expiration_is_recoverable(self, search):
        search.return_value = [self.row]
        target = self.client.get(self.url, {'metadados': '1'}).json()['results'][0]['cadastro_url']
        other = User.objects.create_user('other-flow')
        Perfil.objects.create(usuario=other)
        self.client.force_login(other)
        response = self.client.get(target)
        self.assertContains(response, 'expiraram')
        self.assertIsNone(response.context['form'].product_form['titulo'].value())
        self.client.force_login(self.user)
        cache.clear()
        response = self.client.get(target)
        self.assertContains(response, 'expiraram')
        self.assertEqual(response.context['form'].product_form['ean'].value(), self.code)
        self.assert_no_registration()

    @patch('acervo.barcode_flow.pesquisar')
    def test_product_added_after_lookup_is_reused_at_registration(self, search):
        search.return_value = [self.row]
        target = self.client.get(self.url, {'metadados': '1'}).json()['results'][0]['cadastro_url']
        product = Produto.objects.create(tipo='CD', titulo='Agora local', artista_diretor='A', ean=self.code, categoria=self.category)
        self.assertEqual(self.client.get(target).context['form']['produto'].value(), product.pk)
        self.assertEqual(Produto.objects.count(), 1)
        self.assertEqual(Exemplar.objects.count(), 0)

    @patch('acervo.barcode_flow.pesquisar')
    def test_permissions_and_fallback_remain_enforced(self, search):
        response = self.client.get(reverse('codigo_barras'), {'codigo': self.code})
        self.assertContains(response, 'modo=auto')
        self.assertContains(response, 'Consultar em página completa')
        self.assert_no_registration()
        for user in (None, User.objects.create_user('no-profile')):
            self.client.logout()
            if user:
                self.client.force_login(user)
            self.assertEqual(self.client.get(self.url, {'metadados': '1'}).status_code, 403)
            self.assertIn(self.client.get(reverse('acervo:cadastrar')).status_code, (302, 403))
        search.assert_not_called()

    @patch('acervo.barcode_flow.pesquisar')
    def test_prefilled_form_only_saves_on_valid_post(self, search):
        search.return_value = [self.row]
        target = self.client.get(self.url, {'metadados': '1'}).json()['results'][0]['cadastro_url']
        self.client.get(target)
        self.assert_no_registration()
        payload = {f'produto-{key}': value for key, value in self.row.items() if key != 'metadados'}
        payload.update(codigo_interno='EX-NOVO', estado_conservacao='bom', status='disponivel')
        response = self.client.post(target, payload)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].product_form.errors)
        self.assertEqual(response.context['form'].product_form['titulo'].value(), self.row['titulo'])
        self.assert_no_registration()
        payload['produto-categoria'] = self.category.pk
        self.assertEqual(self.client.post(target, payload).status_code, 302)
        self.assertEqual(Produto.objects.count(), 1)
        self.assertEqual(Exemplar.objects.count(), 1)
