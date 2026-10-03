from decimal import Decimal
from unittest.mock import patch
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django.contrib.auth.models import User
from acervo.models import Produto, Categoria, Exemplar
from acervo.services import TRANSITIONS, salvar_exemplar, excluir_exemplar
from usuarios.models import Perfil


class ServicesTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('operator')
        Perfil.objects.create(usuario=self.user, tipo='administrador')
        self.product = Produto.objects.create(tipo='CD', titulo='Album', artista_diretor='Band', categoria=Categoria.objects.create(nome='Jazz'))
        self.item = salvar_exemplar(usuario=self.user, dados={'produto': self.product, 'codigo_interno': 'MT1', 'preco': Decimal('10')})

    def change(self, **data):
        self.item = salvar_exemplar(usuario=self.user, exemplar=self.item, dados=data)

    def test_new_exemplar_must_start_available(self):
        with self.assertRaises(ValidationError):
            salvar_exemplar(usuario=self.user, dados={
                'produto': self.product, 'codigo_interno': 'MT-RESERVED', 'status': 'reservado',
            })
        self.assertFalse(Exemplar.objects.filter(codigo_interno='MT-RESERVED').exists())

    def test_service_authorization_for_edit_and_exclusion(self):
        employee = User.objects.create_user('employee')
        Perfil.objects.create(usuario=employee, tipo='funcionario')
        inactive = User.objects.create_user('inactive')
        Perfil.objects.create(usuario=inactive, tipo='administrador', ativo=False)
        missing_profile = User.objects.create_user('missing-profile')

        updated = salvar_exemplar(usuario=employee, exemplar=self.item,
                                  dados={'localizacao': 'B1'})
        self.assertEqual(updated.localizacao, 'B1')
        with self.assertRaises(PermissionDenied):
            excluir_exemplar(self.item, employee)
        for user in (inactive, missing_profile):
            with self.subTest(user=user.username), self.assertRaises(PermissionDenied):
                salvar_exemplar(usuario=user, exemplar=self.item, dados={'localizacao': 'C1'})

    def test_transition_matrix(self):
        statuses = dict(Exemplar.STATUS_CHOICES)
        for old, allowed in TRANSITIONS.items():
            for new in statuses:
                if old == new:
                    continue
                with self.subTest(old=old, new=new):
                    item = Exemplar.objects.create(
                        produto=self.product, codigo_interno=f'MT-{old}-{new}', status=old,
                        usuario_responsavel=self.user,
                    )
                    if new in allowed:
                        salvar_exemplar(usuario=self.user, exemplar=item, dados={'status': new})
                        item.refresh_from_db()
                        self.assertEqual(item.status, new)
                    else:
                        with self.assertRaises(ValidationError):
                            salvar_exemplar(usuario=self.user, exemplar=item, dados={'status': new})
                        item.refresh_from_db()
                        self.assertEqual(item.status, old)

    def test_reserve_sell_and_cancel(self):
        self.change(status='reservado')
        self.change(status='disponivel')
        self.change(status='vendido')
        self.change(status='disponivel')
        self.assertEqual(list(self.item.movimentacoes.values_list('tipo', flat=True)), ['cancelamento', 'venda', 'cancelamento_reserva', 'reserva', 'entrada'])

    def test_invalid_transition(self):
        self.change(status='vendido')
        with self.assertRaises(ValidationError):
            self.change(status='reservado')
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, 'vendido')

    def test_audit_values_and_retirement(self):
        self.change(preco=Decimal('0'), localizacao='A2')
        movement = self.item.movimentacoes.get(tipo='alteracao_preco')
        self.assertEqual(movement.anterior['preco'], '10.00')
        self.assertEqual(movement.novo['preco'], '0')
        excluir_exemplar(self.item, self.user)
        self.assertTrue(Exemplar.objects.filter(pk=self.item.pk).exists())
        with self.assertRaises(ProtectedError):
            self.item.delete()

    @patch('acervo.services.event', side_effect=RuntimeError('database failure'))
    def test_rollback_when_history_fails(self, mocked):
        with self.assertRaises(RuntimeError):
            self.change(localizacao='lost')
        self.item.refresh_from_db()
        self.assertEqual(self.item.localizacao, '')

    def test_employee_cannot_cancel_sale(self):
        self.change(status='vendido')
        self.user.perfil.tipo = 'funcionario'
        self.user.perfil.save()
        with self.assertRaises(PermissionDenied):
            self.change(status='disponivel')

    def test_stale_update_rejected(self):
        stale = Exemplar.objects.get(pk=self.item.pk)
        self.change(localizacao='first')
        with self.assertRaises(ValidationError):
            salvar_exemplar(usuario=self.user, exemplar=stale, dados={'localizacao': 'second'})
