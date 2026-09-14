from django.test import TestCase
from django.contrib.auth.models import User
from usuarios.models import Perfil
from acervo.models import Produto, Exemplar, Categoria

class BarcodeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('scanner')
        Perfil.objects.create(usuario=self.user)
        self.client.force_login(self.user)
        self.product = Produto.objects.create(tipo='DVD', titulo='Matrix', artista_diretor='W', ean='789123', categoria=Categoria.objects.create(nome='Drama'))

    def test_consecutive_internal_reads(self):
        for code in ['MT1', 'MT2']:
            item = Exemplar.objects.create(produto=self.product, codigo_interno=code, usuario_responsavel=self.user)
            response = self.client.get('/codigo-barras/', {'codigo': code})
            self.assertEqual(response.context['item'].pk, item.pk)
            self.assertContains(response, 'data-barcode')
        self.assertNotContains(response, 'Exemplar MT1')

    def test_product_without_copies(self):
        response = self.client.get('/codigo-barras/', {'codigo': '789123'})
        self.assertContains(response, 'Item identificado com sucesso')
        self.assertContains(response, 'Nenhum exemplar cadastrado')
        self.assertContains(response, 'Ver no acervo')

    def test_multiple_copies_for_ean(self):
        for code in ['MT1', 'MT2']:
            Exemplar.objects.create(produto=self.product, codigo_interno=code, usuario_responsavel=self.user)
        response = self.client.get('/codigo-barras/', {'codigo': '789123'})
        self.assertEqual(len(response.context['exemplares']), 2)
        self.assertEqual(self.client.get('/api/exemplares/codigo/789123/').json()['tipo_codigo'], 'ean')

    def test_unknown_code_and_explicit_mode(self):
        self.assertContains(self.client.get('/codigo-barras/?codigo=unknown'), 'Código não encontrado no sistema')
        self.assertContains(self.client.get('/codigo-barras/?codigo=unknown'), 'Cadastrar este item')
        Exemplar.objects.create(produto=self.product, codigo_interno='789123', usuario_responsavel=self.user)
        self.assertIsNone(self.client.get('/codigo-barras/?codigo=789123&modo=ean').context['item'])

    def test_internal_code_json_contract(self):
        item = Exemplar.objects.create(produto=self.product, codigo_interno='MT1',
            preco=0, usuario_responsavel=self.user)
        response = self.client.get('/api/exemplares/codigo/MT1/', HTTP_ACCEPT='application/json')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['id'], item.pk)
        self.assertEqual(data['codigo_interno'], 'MT1')
        self.assertEqual(data['status'], 'disponivel')
        self.assertEqual(data['estado_conservacao'], 'bom')
        self.assertEqual(data['preco'], '0.00')
        self.assertEqual(data['produto_detalhe']['titulo'], 'Matrix')
        self.assertEqual(data['produto_detalhe']['tipo'], 'DVD')

    def test_ean_json_contract_and_pagination(self):
        for number in range(21):
            Exemplar.objects.create(produto=self.product, codigo_interno=f'MT{number}',
                usuario_responsavel=self.user)
        response = self.client.get('/api/exemplares/codigo/789123/?modo=ean')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['tipo_codigo'], 'ean')
        self.assertEqual(data['produto']['id'], self.product.pk)
        self.assertEqual(data['produto']['ean'], '789123')
        self.assertEqual(data['produto']['titulo'], 'Matrix')
        self.assertEqual(data['produto']['tipo'], 'DVD')
        self.assertEqual(data['count'], 21)
        self.assertEqual(len(data['results']), 20)
        self.assertIsNone(data['previous'])
        self.assertIn('modo=ean', data['next'])
        second = self.client.get(data['next']).json()
        self.assertEqual(len(second['results']), 1)
        self.assertIsNone(second['next'])
        self.assertIsNotNone(second['previous'])
        self.assertFalse({row['id'] for row in data['results']} & {row['id'] for row in second['results']})
        for row in data['results']:
            self.assertTrue({'id', 'codigo_interno', 'estado_conservacao', 'status', 'preco'} <= row.keys())

    def test_ean_without_copies_json_contract(self):
        data = self.client.get('/api/exemplares/codigo/789123/').json()
        self.assertEqual(data['tipo_codigo'], 'ean')
        self.assertEqual(data['count'], 0)
        self.assertEqual(data['results'], [])
        self.assertIsNone(data['next'])
        self.assertIsNone(data['previous'])

    def test_unknown_code_json_contract(self):
        response = self.client.get('/api/exemplares/codigo/unknown/', HTTP_ACCEPT='application/json')
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()['erro']['codigo'], 'nao_encontrado')

    def test_api_respects_explicit_mode_and_internal_priority(self):
        item = Exemplar.objects.create(produto=self.product, codigo_interno='789123', usuario_responsavel=self.user)
        for mode in ('auto', 'interno'):
            with self.subTest(mode=mode):
                self.assertEqual(self.client.get('/api/exemplares/codigo/789123/', {'modo': mode}).json()['id'], item.pk)
        self.assertEqual(self.client.get('/api/exemplares/codigo/789123/?modo=ean').json()['tipo_codigo'], 'ean')

    def test_lookup_denied_without_active_permission(self):
        self.client.logout()
        self.assertEqual(self.client.get('/api/exemplares/codigo/789123/').status_code, 403)
        self.client.force_login(User.objects.create_user('without-profile'))
        self.assertEqual(self.client.get('/api/exemplares/codigo/789123/').status_code, 403)
        Perfil.objects.filter(usuario=self.user).update(ativo=False)
        self.client.force_login(self.user)
        response = self.client.get('/api/exemplares/codigo/789123/')
        self.assertEqual(response.status_code, 403)
        self.assertNotIn('produto', response.json())

    def test_html_fallback_and_accessible_async_hooks(self):
        item = Exemplar.objects.create(produto=self.product, codigo_interno='MT.1/2', usuario_responsavel=self.user)
        response = self.client.get('/codigo-barras/', {'codigo': item.codigo_interno, 'consulta_html': '1'})
        self.assertEqual(response.context['item'], item)
        self.assertContains(response, 'method="get"')
        self.assertContains(response, 'data-api-url="/api/exemplares/codigo/CODIGO/"')
        self.assertContains(response, 'aria-live="polite"')
        self.assertContains(response, 'aria-busy="false"')
        self.assertContains(response, 'Consultar em página completa')

    def test_reading_interface_is_truthful_and_keeps_form_contract(self):
        response = self.client.get('/codigo-barras/')
        self.assertContains(response, '<h1>Código de barras</h1>', html=True)
        self.assertContains(response, 'Aguardando leitura')
        self.assertContains(response, 'Orientação do processo')
        self.assertContains(response, 'COMO USAR')
        self.assertContains(response, 'name="consulta_html"')
        self.assertContains(response, 'name="modo"')
        self.assertContains(response, 'name="codigo"')
        self.assertContains(response, 'data-state="idle"')
        self.assertNotContains(response, 'Leitor físico conectado')
        self.assertNotContains(response, 'Simular leitura')

    def test_live_status_remains_outside_the_collapsed_form(self):
        from html.parser import HTMLParser

        class FormParser(HTMLParser):
            inside_form = False
            status_inside = None

            def handle_starttag(self, tag, attrs):
                if tag == 'form':
                    self.inside_form = True
                if dict(attrs).get('id') == 'barcode-status':
                    self.status_inside = self.inside_form

            def handle_endtag(self, tag):
                if tag == 'form':
                    self.inside_form = False

        response = self.client.get('/codigo-barras/')
        parser = FormParser()
        parser.feed(response.content.decode())
        self.assertIs(parser.status_inside, False)
        self.assertContains(response, 'aria-live="polite"')
        self.assertContains(response, 'id="barcode-results"')

    def test_html_lookup_renders_matching_visual_state_without_javascript(self):
        for code, state, title in [('789123', 'found', 'Item encontrado'), ('unknown', 'missing', 'Código não encontrado')]:
            with self.subTest(code=code):
                response = self.client.get('/codigo-barras/', {'codigo': code})
                self.assertContains(response, f'data-state="{state}"')
                self.assertContains(response, f'<h2 id="barcode-heading">{title}</h2>', html=True)
                self.assertContains(response, f'value="{code}"')
