from collections import Counter
from html.parser import HTMLParser

from django.test import TestCase
from django.contrib.auth.models import User
from acervo.models import Categoria, Produto, Exemplar
from usuarios.models import Perfil


class FormAssociationsParser(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.ids = Counter()
        self.controls = {}
        self.labels = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get('id'):
            self.ids[attrs['id']] += 1
        if tag in ('input', 'select', 'textarea') and attrs.get('id'):
            self.controls[attrs['id']] = attrs
        if tag == 'label' and attrs.get('for'):
            self.labels.append(attrs['for'])


class CadastroInterfaceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('cadastro-interface')
        Perfil.objects.create(usuario=self.user)
        self.category = Categoria.objects.create(nome='Geral')
        self.product = Produto.objects.create(tipo='CD', titulo='Existente', artista_diretor='Artista', categoria=self.category)
        self.client.force_login(self.user)

    def payload(self, tipo='CD'):
        return {'codigo_interno': 'NOVO-' + tipo, 'estado_conservacao': 'bom', 'preco': '12.50',
                'localizacao': 'A1', 'status': 'disponivel', 'produto': '', 'produto-tipo': tipo,
                'produto-titulo': 'Titulo ' + tipo, 'produto-artista_diretor': 'Autor',
                'produto-ean': '7890001' if tipo == 'CD' else '7890002',
                'produto-categoria': str(self.category.pk), 'produto-ano': '2020',
                'produto-gravadora_distribuidora': 'Editora', 'produto-descricao': 'Descricao'}

    def assert_accessible_associations(self, response, invalid_id):
        self.assertEqual(response.status_code, 200)
        page = FormAssociationsParser(response.content.decode())
        self.assertTrue(all(count == 1 for count in page.ids.values()), page.ids)
        for control_id, attrs in page.controls.items():
            if attrs.get('type') != 'hidden':
                self.assertIn(control_id, page.labels)
            for reference in attrs.get('aria-describedby', '').split():
                self.assertEqual(page.ids[reference], 1, (control_id, reference))
        invalid = page.controls[invalid_id]
        self.assertEqual(invalid['aria-invalid'], 'true')
        self.assertIn(invalid_id + '_error', invalid['aria-describedby'].split())
        self.assertIn('id_produto_helptext', page.controls['id_produto']['aria-describedby'].split())
        self.assertContains(response, 'Selecione um produto existente ou preencha os dados abaixo.')

    def test_registration_error_and_help_references_have_unique_targets(self):
        for field in ('produto-titulo', 'codigo_interno'):
            with self.subTest(field=field):
                data = self.payload()
                data[field] = ''
                response = self.client.post('/acervo/cadastrar/', data)
                self.assert_accessible_associations(response, 'id_' + field)
        self.assertEqual(Exemplar.objects.count(), 0)

    def test_edit_error_and_help_references_have_unique_targets(self):
        exemplar = Exemplar.objects.create(produto=self.product, codigo_interno='EDIT1', usuario_responsavel=self.user)
        response = self.client.post(f'/acervo/item/{exemplar.pk}/editar/', {
            'produto': self.product.pk, 'codigo_interno': 'EDIT1',
            'estado_conservacao': 'bom', 'status': 'disponivel', 'preco': '-1',
        })
        self.assert_accessible_associations(response, 'id_preco')

    def test_get_renders_single_flow_and_no_js_fallback(self):
        response = self.client.get('/acervo/cadastrar/')
        self.assertContains(response, 'data-item-registration', count=1)
        self.assertContains(response, '>Cancelar</a>', count=1)
        self.assertContains(response, '>Cadastrar item</button>', count=1)
        self.assertContains(response, 'id="produto-existente" data-existing-product>')
        self.assertContains(response, 'id="produto-novo" data-new-product>')
        self.assertContains(response, '<option value="CD">CD</option>', html=True)
        self.assertContains(response, '<option value="DVD">DVD</option>', html=True)
        self.assertNotContains(response, 'Novo produto (preencha somente')

    def test_existing_product_creates_only_copy(self):
        response = self.client.post('/acervo/cadastrar/', {'produto': self.product.pk,
            'codigo_interno': 'EX1', 'estado_conservacao': 'bom', 'status': 'disponivel'})
        self.assertRedirects(response, '/acervo/')
        self.assertEqual(Produto.objects.count(), 1)
        self.assertEqual(Exemplar.objects.get().produto_id, self.product.pk)

    def test_new_cd_and_dvd_without_javascript(self):
        for tipo in ('CD', 'DVD'):
            with self.subTest(tipo=tipo):
                response = self.client.post('/acervo/cadastrar/', self.payload(tipo))
                self.assertRedirects(response, '/acervo/')
                exemplar = Exemplar.objects.get(codigo_interno='NOVO-' + tipo)
                self.assertEqual(exemplar.produto.tipo, tipo)
                self.assertEqual(exemplar.produto.ean, self.payload(tipo)['produto-ean'])
                self.assertEqual(exemplar.movimentacoes.count(), 1)

    def test_product_errors_preserve_values_and_do_not_save(self):
        for field, value in [('produto-tipo', ''), ('produto-tipo', 'VHS'), ('produto-categoria', ''), ('produto-titulo', '')]:
            with self.subTest(field=field, value=value):
                data = self.payload()
                data[field] = value
                response = self.client.post('/acervo/cadastrar/', data)
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context['form'].product_form.errors)
                self.assertContains(response, 'value="A1"')
                self.assertContains(response, 'value="7890001"')
                self.assertContains(response, 'role="alert"')
                self.assertEqual(Exemplar.objects.count(), 0)
                self.assertEqual(Produto.objects.count(), 1)

    def test_copy_error_preserves_both_product_paths(self):
        for existing in (False, True):
            with self.subTest(existing=existing):
                data = self.payload()
                data['preco'] = '-1'
                if existing:
                    data['produto'] = str(self.product.pk)
                response = self.client.post('/acervo/cadastrar/', data)
                self.assertEqual(response.status_code, 200)
                self.assertIn('preco', response.context['form'].errors)
                self.assertEqual(response.context['form'].product_form['titulo'].value(), 'Titulo CD')
                self.assertEqual(bool(response.context['form']['produto'].value()), existing)
                self.assertEqual(Exemplar.objects.count(), 0)
                self.assertEqual(Produto.objects.count(), 1)

    def test_preselected_product_and_permissions(self):
        response = self.client.get('/acervo/cadastrar/', {'produto': self.product.pk})
        self.assertEqual(str(response.context['form']['produto'].value()), str(self.product.pk))
        Perfil.objects.filter(usuario=self.user).update(ativo=False)
        self.assertEqual(self.client.post('/acervo/cadastrar/', self.payload()).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get('/acervo/cadastrar/').status_code, 302)
        self.assertEqual(Exemplar.objects.count(), 0)
