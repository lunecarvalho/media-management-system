"""Provisionamento explícito de um avaliador, sem credenciais em argumentos."""
import os

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management import BaseCommand, CommandError
from django.db import IntegrityError
from django.db import transaction

from usuarios.models import Perfil


class Command(BaseCommand):
    help = 'Cria um avaliador usando DJANGO_EVALUATOR_*.'

    def handle(self, *args, **options):
        User = get_user_model()
        username = os.environ.get('DJANGO_EVALUATOR_USERNAME', '').strip()
        email = os.environ.get('DJANGO_EVALUATOR_EMAIL', '').strip()
        password = os.environ.get('DJANGO_EVALUATOR_PASSWORD', '')

        if not username or not email or not password.strip():
            raise CommandError(
                'Informe DJANGO_EVALUATOR_USERNAME, DJANGO_EVALUATOR_EMAIL e '
                'DJANGO_EVALUATOR_PASSWORD.'
            )

        existing = User.objects.filter(username=username).first()
        if existing is not None:
            perfil = Perfil.objects.filter(usuario=existing).first()
            if (
                existing.is_active
                and not existing.is_staff
                and not existing.is_superuser
                and perfil is not None
                and perfil.ativo
                and perfil.tipo == 'avaliador'
            ):
                self.stdout.write('Avaliador já existe; nenhuma alteração realizada.')
                return
            raise CommandError(
                'O nome de usuário já existe e não corresponde a um avaliador seguro; '
                'nenhuma alteração foi realizada.'
            )

        try:
            validate_password(password, User(username=username, email=email))
        except ValidationError as exc:
            raise CommandError(
                'A senha não atende à política configurada; nenhuma alteração foi realizada.'
            ) from exc

        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password,
                    is_active=True,
                )
                user.is_staff = False
                user.is_superuser = False
                user.save(update_fields=['is_staff', 'is_superuser'])
                Perfil.objects.create(usuario=user, tipo='avaliador', ativo=True)
        except IntegrityError as exc:
            raise CommandError(
                'Não foi possível criar o avaliador; nenhuma alteração foi realizada.'
            ) from exc

        self.stdout.write('Avaliador criado com sucesso.')
