from django.contrib.auth.models import User
from django.test import TestCase
from acervo.models import Categoria, Item, Produto
from usuarios.models import Perfil


class AccessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.users = {}
        for role in ('funcionario', 'administrador', 'proprietario'):
            user = User.objects.create_user(role, password='test-password', is_staff=True)
            Perfil.objects.create(usuario=user, tipo=role)
            cls.users[role] = user
        cls.category = Categoria.objects.create(nome='Rock')
        cls.product = Produto.objects.create(tipo='CD', titulo='Album', artista_diretor='Artist', categoria=cls.category, ean='123')
        cls.item = Item.objects.create(produto=cls.product, codigo_interno='123', usuario_responsavel=cls.users['funcionario'])

    def test_anonymous_private_pages(self):
        for url in ('/', '/usuarios/lista/', '/movimentacoes/', '/categorias/', '/acervo/', '/codigo-barras/', '/configuracoes/'):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 302)

    def test_anonymous_writes(self):
        self.assertEqual(self.client.post('/categorias/', {'nome': 'Unwanted'}).status_code, 302)
        for url in ('/api/itens/', '/api/categorias/', '/api/movimentacoes/'):
            self.assertEqual(self.client.post(url, {}).status_code, 403)
            self.assertEqual(self.client.get(url).status_code, 403)
        self.assertFalse(Categoria.objects.filter(nome='Unwanted').exists())

    def test_employee_cannot_administer(self):
        self.client.force_login(self.users['funcionario'])
        for url in ('/usuarios/lista/', '/admin/', f'/acervo/item/{self.item.pk}/excluir/'):
            self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.post('/categorias/', {'nome': 'Denied'}).status_code, 403)
        self.assertEqual(self.client.post('/api/categorias/', {'nome': 'Denied'}).status_code, 403)
        self.assertEqual(self.client.delete(f'/api/itens/{self.item.pk}/').status_code, 403)

    def test_manager_can_create_categories_both_channels(self):
        self.client.force_login(self.users['administrador'])
        self.assertEqual(self.client.post('/categorias/', {'nome': 'Jazz'}).status_code, 302)
        self.assertEqual(self.client.post('/api/categorias/', {'nome': 'Drama'}).status_code, 201)

    def test_inactive_profile_blocks_both_channels(self):
        user = self.users['proprietario']
        Perfil.objects.filter(usuario=user).update(ativo=False)
        self.client.force_login(user)
        for url in ('/', '/usuarios/lista/', '/api/itens/', '/admin/'):
            self.assertEqual(self.client.get(url).status_code, 403)

    def test_missing_profile_is_denied(self):
        self.client.force_login(User.objects.create_user('no-profile'))
        self.assertEqual(self.client.get('/api/itens/').status_code, 403)

    def test_employee_can_read_api(self):
        self.client.force_login(self.users['funcionario'])
        self.assertEqual(self.client.get('/api/itens/').status_code, 200)
