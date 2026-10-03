from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from acervo.models import Categoria, Exemplar, Produto
from movimentacoes.models import Movimentacao
from usuarios.models import Perfil


class RESTAPITests(TestCase):
    def setUp(self):
        self.users = {}
        for role in ('funcionario', 'administrador', 'proprietario'):
            user = User.objects.create_user(role)
            Perfil.objects.create(usuario=user, tipo=role)
            self.users[role] = user
        self.category = Categoria.objects.create(nome='Rock', descricao='Musica')
        self.product = Produto.objects.create(
            tipo='CD', titulo='Album', artista_diretor='Band',
            ean='7891234567895', categoria=self.category, ano=2001,
        )
        self.item = Exemplar.objects.create(
            produto=self.product, codigo_interno='MT1', preco=Decimal('10'),
            usuario_responsavel=self.users['funcionario'],
        )
        self.client = APIClient()
        self.client.force_authenticate(self.users['administrador'])
        self.client.defaults['HTTP_ACCEPT'] = 'application/json'

    def product_payload(self, **overrides):
        data = {
            'tipo': 'DVD', 'titulo': 'Filme', 'artista_diretor': 'Diretor',
            'ean': '7891234567896', 'categoria': self.category.pk,
            'ano': 2002, 'gravadora_distribuidora': '', 'descricao': '',
        }
        data.update(overrides)
        return data

    def item_payload(self, **overrides):
        data = {
            'produto': self.product.pk, 'codigo_interno': 'MT2',
            'estado_conservacao': 'bom', 'preco': '12.50',
            'localizacao': 'A1', 'status': 'disponivel',
        }
        data.update(overrides)
        return data

    def test_product_crud_and_serializer_contract(self):
        response = self.client.get('/api/produtos/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['count'], 1)

        response = self.client.get(f'/api/produtos/{self.product.pk}/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['categoria_nome'], 'Rock')

        response = self.client.post('/api/produtos/', self.product_payload())
        self.assertEqual(response.status_code, 201)
        product_id = response.json()['id']
        self.assertEqual(response.json()['tipo'], 'DVD')
        self.assertEqual(response.json()['identificadores'], {})
        self.assertEqual(response.json()['metadados'], {})

        response = self.client.patch(f'/api/produtos/{product_id}/', {'titulo': 'Filme atualizado'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['titulo'], 'Filme atualizado')

        response = self.client.delete(f'/api/produtos/{product_id}/')
        self.assertEqual(response.status_code, 204)

    def test_product_validation_and_protected_delete(self):
        response = self.client.post('/api/produtos/', self.product_payload(tipo='VHS'))
        self.assertEqual(response.status_code, 400)

        response = self.client.delete(f'/api/produtos/{self.product.pk}/')
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()['erro']['codigo'], 'protegido')

    def test_category_crud_and_write_permission(self):
        response = self.client.get('/api/categorias/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['count'], 1)

        response = self.client.get(f'/api/categorias/{self.category.pk}/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['nome'], 'Rock')

        response = self.client.post('/api/categorias/', {'nome': 'Cinema', 'descricao': 'Filmes'})
        self.assertEqual(response.status_code, 201)
        category_id = response.json()['id']

        response = self.client.patch(f'/api/categorias/{category_id}/', {'descricao': 'Atualizada'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['descricao'], 'Atualizada')

        response = self.client.delete(f'/api/categorias/{category_id}/')
        self.assertEqual(response.status_code, 204)

        self.client.force_authenticate(self.users['funcionario'])
        response = self.client.post('/api/categorias/', {'nome': 'Negada'})
        self.assertEqual(response.status_code, 403)

    def test_item_crud_and_business_service(self):
        response = self.client.get('/api/exemplares/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['count'], 1)

        response = self.client.get(f'/api/exemplares/{self.item.pk}/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['titulo'], 'Album')
        self.assertEqual(response.json()['codigo_barras'], 'MT1')

        response = self.client.post('/api/exemplares/', self.item_payload())
        self.assertEqual(response.status_code, 201)
        item_id = response.json()['id']
        self.assertEqual(response.json()['status'], 'disponivel')

        response = self.client.patch(f'/api/exemplares/{item_id}/', {'localizacao': 'A2'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['localizacao'], 'A2')

        response = self.client.delete(f'/api/exemplares/{item_id}/')
        self.assertEqual(response.status_code, 204)
        self.assertEqual(Exemplar.objects.get(pk=item_id).status, 'cancelado')

    def test_item_validation_and_employee_delete_permission(self):
        response = self.client.post('/api/exemplares/', self.item_payload(codigo_interno='MT3', status='vendido'))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['erro']['codigo'], 'validacao')

        self.client.force_authenticate(self.users['funcionario'])
        response = self.client.delete(f'/api/exemplares/{self.item.pk}/')
        self.assertEqual(response.status_code, 403)

    def test_movimentacoes_are_read_only(self):
        self.assertFalse(Movimentacao.objects.filter(item=self.item).exists())
        self.item.status = 'vendido'
        self.item.save(update_fields=['status'])
        movement = Movimentacao.objects.create(
            item=self.item, usuario=self.users['administrador'], tipo='venda',
            anterior={'status': 'disponivel'}, novo={'status': 'vendido'},
        )

        response = self.client.get('/api/movimentacoes/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['count'], 1)

        response = self.client.get(f'/api/movimentacoes/{movement.pk}/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['item_titulo'], 'Album')

        response = self.client.post('/api/movimentacoes/', {})
        self.assertEqual(response.status_code, 405)

    def test_api_permissions_for_anonymous_inactive_and_missing_profile(self):
        self.client.force_authenticate(user=None)
        self.assertEqual(self.client.get('/api/produtos/').status_code, 403)

        inactive = User.objects.create_user('inactive')
        Perfil.objects.create(usuario=inactive, tipo='administrador', ativo=False)
        self.client.force_authenticate(inactive)
        self.assertEqual(self.client.get('/api/produtos/').status_code, 403)

        missing = User.objects.create_user('missing-profile')
        self.client.force_authenticate(missing)
        self.assertEqual(self.client.get('/api/produtos/').status_code, 403)

    def test_payload_validation_and_read_only_metadata(self):
        payload = self.product_payload(
            identificadores={'forged': True}, metadados={'forged': True}, origem='forged',
        )
        response = self.client.post('/api/produtos/', payload, format='json')
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data['identificadores'], {})
        self.assertEqual(data['metadados'], {})
        self.assertEqual(data['origem'], '')
