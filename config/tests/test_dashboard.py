from decimal import Decimal
from django.contrib.auth.models import User
from django.test import TestCase
from usuarios.models import Perfil
from acervo.models import Exemplar, Produto, Categoria

class DashboardTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('dashboard')
        Perfil.objects.create(usuario=self.user)
        self.client.force_login(self.user)
        self.product = Produto.objects.create(titulo='Album', tipo='CD', artista_diretor='Band', categoria=Categoria.objects.create(nome='Rock'))

    def test_indicators_and_excluded_sales(self):
        for n, status in enumerate(['disponivel', 'reservado', 'vendido', 'cancelado']):
            Exemplar.objects.create(produto=self.product, codigo_interno=str(n), preco=10, status=status, usuario_responsavel=self.user)
        response = self.client.get('/')
        self.assertEqual(response.context['valor_estoque'], Decimal('20'))
        self.assertEqual(dict(response.context['indicadores'])['Produtos'], 1)
        self.assertEqual(dict(response.context['indicadores'])['Exemplares'], 4)
        self.assertNotContains(response, '1.842')

    def test_pagination_and_search(self):
        Exemplar.objects.bulk_create([Exemplar(produto=self.product, codigo_interno=str(n), usuario_responsavel=self.user) for n in range(23)])
        page = self.client.get('/acervo/?q=Album&page=2')
        self.assertEqual(len(page.context['itens']), 3)
        self.assertContains(page, 'q=Album')
        self.assertEqual(self.client.get('/acervo/?page=bad').status_code, 200)
