from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from acervo.models import Categoria, Exemplar, Produto
from usuarios.models import Perfil


class UserManagementTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user('owner', password='owner-password')
        Perfil.objects.create(usuario=self.owner, tipo='proprietario')
        self.client.force_login(self.owner)

    def create_user(self, username='target', password='target-password', tipo='funcionario', active=True):
        user = User.objects.create_user(username, password=password, is_active=active)
        Perfil.objects.create(usuario=user, tipo=tipo, ativo=active)
        return user

    def test_owner_lists_users_with_actions(self):
        target = self.create_user()
        response = self.client.get(reverse('usuarios:lista'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Ações')
        self.assertContains(response, reverse('usuarios:editar', args=[target.pk]))
        self.assertContains(response, reverse('usuarios:excluir', args=[target.pk]))

    def test_superuser_can_list_users(self):
        superuser = User.objects.create_superuser('superuser', password='super-password')
        self.client.force_login(superuser)
        self.assertEqual(self.client.get(reverse('usuarios:lista')).status_code, 200)

    def test_create_user_creates_profile_and_hashes_password(self):
        response = self.client.post(reverse('usuarios:criar'), {
            'username': 'new-user', 'first_name': 'New', 'last_name': 'User',
            'email': 'new@example.com', 'password1': 'Strong-password-123',
            'password2': 'Strong-password-123', 'tipo': 'administrador', 'ativo': 'on',
        })
        self.assertRedirects(response, reverse('usuarios:lista'))
        user = User.objects.get(username='new-user')
        self.assertTrue(user.check_password('Strong-password-123'))
        self.assertNotEqual(user.password, 'Strong-password-123')
        self.assertTrue(user.is_active)
        self.assertEqual(user.perfil.tipo, 'administrador')
        self.assertTrue(user.perfil.ativo)

    def test_create_rejects_duplicate_username_and_mismatched_passwords(self):
        self.create_user('taken')
        base = {
            'username': 'taken', 'first_name': 'New', 'last_name': 'User',
            'email': 'new@example.com', 'password1': 'Strong-password-123',
            'password2': 'different-password-123', 'tipo': 'funcionario', 'ativo': 'on',
        }
        response = self.client.post(reverse('usuarios:criar'), base)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['form'].is_valid())
        self.assertIn('username', response.context['form'].errors)
        self.assertIn('password2', response.context['form'].errors)

    def test_edit_updates_user_and_profile_without_changing_password(self):
        target = self.create_user(password='original-password')
        response = self.client.post(reverse('usuarios:editar', args=[target.pk]), {
            'username': 'renamed', 'first_name': 'Renamed', 'last_name': 'User',
            'email': 'renamed@example.com', 'tipo': 'administrador',
        })
        self.assertRedirects(response, reverse('usuarios:lista'))
        target.refresh_from_db()
        self.assertEqual(target.username, 'renamed')
        self.assertEqual(target.first_name, 'Renamed')
        self.assertEqual(target.email, 'renamed@example.com')
        self.assertTrue(target.check_password('original-password'))
        self.assertEqual(target.perfil.tipo, 'administrador')
        self.assertFalse(target.is_active)
        self.assertFalse(target.perfil.ativo)

    def test_unauthorized_users_cannot_manage_users(self):
        target = self.create_user()
        for role in ('funcionario', 'administrador'):
            user = User.objects.create_user(role)
            Perfil.objects.create(usuario=user, tipo=role)
            self.client.force_login(user)
            with self.subTest(role=role):
                self.assertEqual(self.client.get(reverse('usuarios:lista')).status_code, 403)
                self.assertEqual(self.client.post(reverse('usuarios:criar'), {}).status_code, 403)
                self.assertEqual(self.client.get(reverse('usuarios:editar', args=[target.pk])).status_code, 403)
                self.assertEqual(self.client.post(reverse('usuarios:excluir', args=[target.pk])).status_code, 403)

    def test_anonymous_user_is_redirected(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse('usuarios:lista')).status_code, 302)

    def test_delete_requires_post_and_removes_allowed_user(self):
        target = self.create_user()
        confirm = self.client.get(reverse('usuarios:excluir', args=[target.pk]))
        self.assertEqual(confirm.status_code, 200)
        self.assertTrue(User.objects.filter(pk=target.pk).exists())
        response = self.client.post(reverse('usuarios:excluir', args=[target.pk]))
        self.assertRedirects(response, reverse('usuarios:lista'))
        self.assertFalse(User.objects.filter(pk=target.pk).exists())

    def test_delete_protected_user_shows_message_and_preserves_records(self):
        target = self.create_user()
        category = Categoria.objects.create(nome='Protected category')
        product = Produto.objects.create(
            tipo='CD', titulo='Protected item', artista_diretor='Artist', categoria=category,
        )
        exemplar = Exemplar.objects.create(produto=product, codigo_interno='PROTECTED', usuario_responsavel=target)
        response = self.client.post(reverse('usuarios:excluir', args=[target.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'possui registros vinculados')
        self.assertTrue(User.objects.filter(pk=target.pk).exists())
        self.assertTrue(Exemplar.objects.filter(pk=exemplar.pk).exists())

    def test_cannot_delete_self(self):
        url = reverse('usuarios:excluir', args=[self.owner.pk])
        self.assertContains(self.client.get(url), 'Você não pode remover a própria conta.')
        self.assertContains(self.client.post(url), 'Você não pode remover a própria conta.')
        self.assertTrue(User.objects.filter(pk=self.owner.pk).exists())

    def test_cannot_delete_last_active_owner(self):
        superuser = User.objects.create_superuser('superuser', password='super-password')
        target = self.create_user('only-owner', tipo='proprietario')
        Perfil.objects.filter(usuario=self.owner).update(tipo='funcionario')
        self.client.force_login(superuser)
        url = reverse('usuarios:excluir', args=[target.pk])
        self.assertContains(self.client.get(url), 'último proprietário ativo')
        self.assertContains(self.client.post(url), 'último proprietário ativo')
        self.assertTrue(User.objects.filter(pk=target.pk).exists())

    def test_owner_cannot_delete_superuser(self):
        superuser = User.objects.create_superuser('superuser', password='super-password')
        url = reverse('usuarios:excluir', args=[superuser.pk])
        self.assertContains(self.client.get(url), 'Somente um superuser')
        self.assertContains(self.client.post(url), 'Somente um superuser')
        self.assertTrue(User.objects.filter(pk=superuser.pk).exists())

    def test_superuser_cannot_delete_self(self):
        superuser = User.objects.create_superuser('superuser', password='super-password')
        self.client.force_login(superuser)
        url = reverse('usuarios:excluir', args=[superuser.pk])
        self.assertContains(self.client.post(url), 'Você não pode remover a própria conta.')
        self.assertTrue(User.objects.filter(pk=superuser.pk).exists())