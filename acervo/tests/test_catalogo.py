from django.test import TestCase
from django.contrib.auth.models import User
from acervo.models import Produto, Exemplar, Categoria
from acervo.forms import ItemForm
from usuarios.models import Perfil


class CatalogoTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('catalogo')
        Perfil.objects.create(usuario=self.user)
        self.category = Categoria.objects.create(nome='Cinema')
        self.product = Produto.objects.create(tipo='DVD', titulo='Matrix', artista_diretor='Wachowski', ean='789123', categoria=self.category)

    def test_multiple_copies_same_product(self):
        for code in ('MT00001', 'MT00002'):
            Exemplar.objects.create(produto=self.product, codigo_interno=code, usuario_responsavel=self.user)
        self.assertEqual(self.product.exemplares.count(), 2)

    def test_form_existing_product(self):
        form = ItemForm({'produto': self.product.pk, 'codigo_interno': 'MT03', 'estado_conservacao': 'bom', 'status': 'disponivel', 'preco': '0'}, usuario=self.user)
        self.assertTrue(form.is_valid(), form.errors)
        form.instance.usuario_responsavel = self.user
        self.assertEqual(form.save().produto, self.product)
