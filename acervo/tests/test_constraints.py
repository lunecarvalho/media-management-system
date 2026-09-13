from django.db import IntegrityError, transaction
from django.test import TestCase
from django.contrib.auth.models import User
from acervo.models import Categoria, Produto, Exemplar


class ConstraintTests(TestCase):
    def test_database_rejects_negative_price_and_year(self):
        user = User.objects.create_user('constraints')
        category = Categoria.objects.create(nome='Test')
        product = Produto.objects.create(tipo='CD', titulo='A', artista_diretor='B', categoria=category)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Exemplar.objects.create(produto=product, codigo_interno='MT', preco=-1, usuario_responsavel=user)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Produto.objects.filter(pk=product.pk).update(ano=-1)
