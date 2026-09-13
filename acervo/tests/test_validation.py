from datetime import date
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.contrib.auth.models import User
from acervo.models import Produto, Exemplar, Categoria
from acervo.forms import ProdutoForm
from acervo.services import salvar_exemplar
from usuarios.models import Perfil


class ValidationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('manager')
        Perfil.objects.create(usuario=self.user, tipo='administrador')
        self.category = Categoria.objects.create(nome='Rock')
        self.product = Produto.objects.create(titulo='Test', tipo='CD', artista_diretor='Band', categoria=self.category)
        self.client.force_login(self.user)

    def test_negative_price_rejected_by_service_and_api(self):
        with self.assertRaises(ValidationError):
            salvar_exemplar(usuario=self.user, dados={'produto': self.product, 'codigo_interno': 'MT1', 'preco': -1})
        response = self.client.post('/api/exemplares/', {'produto': self.product.pk, 'codigo_interno': 'MT1', 'preco': -1})
        self.assertEqual(response.status_code, 400)
        self.assertIn('erro', response.json())
        self.assertFalse(Exemplar.objects.exists())

    def test_year_bounds(self):
        for year in (-1, 0, date.today().year + 2):
            self.product.ano = year
            with self.assertRaises(ValidationError):
                self.product.full_clean()

    def test_category_protect_returns_conflict(self):
        response = self.client.delete(f'/api/categorias/{self.category.pk}/')
        self.assertEqual(response.status_code, 409)
        self.assertTrue(Categoria.objects.filter(pk=self.category.pk).exists())

    def test_duplicate_internal_code(self):
        payload = {'produto': self.product.pk, 'codigo_interno': 'MT1'}
        self.assertEqual(self.client.post('/api/exemplares/', payload).status_code, 201)
        self.assertEqual(self.client.post('/api/exemplares/', payload).status_code, 400)
        self.assertEqual(Exemplar.objects.count(), 1)

    def test_required_product_fields(self):
        self.assertFalse(ProdutoForm({}).is_valid())

    def test_category_length_server_validation(self):
        response = self.client.post('/categorias/', {'nome': 'x' * 101})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Categoria.objects.count(), 1)
