"""Provisionamento explícito do primeiro superusuário, sem credenciais em argumentos."""
import os
from io import StringIO

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.management import BaseCommand, CommandError, call_command
from django.db import transaction


class Command(BaseCommand):
    help = 'Cria somente o primeiro superusuário usando DJANGO_SUPERUSER_*.'

    def handle(self, *args, **options):
        User = get_user_model()
        try:
            with transaction.atomic():
                if User.objects.filter(is_superuser=True).exists():
                    self.stdout.write('Superusuário já existe; nenhuma alteração realizada.')
                    return
                username = os.environ.get('DJANGO_SUPERUSER_USERNAME', '')
                email = os.environ.get('DJANGO_SUPERUSER_EMAIL', '')
                password = os.environ.get('DJANGO_SUPERUSER_PASSWORD', '')
                if not all(value.strip() for value in (username, email, password)):
                    raise ValueError('Missing bootstrap environment')
                if User.objects.filter(username=username).exists():
                    raise ValueError('Existing account must not be promoted')
                # createsuperuser não interativo não executa os validadores de senha.
                validate_password(password, User(username=username, email=email))
                call_command('createsuperuser', interactive=False, verbosity=0,
                             stdout=StringIO(), stderr=StringIO())
        except Exception:
            # Não propagar mensagens que possam incluir dados de entrada ou SQL.
            raise CommandError(
                'Não foi possível criar o administrador. Confira as variáveis '
                'DJANGO_SUPERUSER_*, a política de senha e a disponibilidade do banco.'
            ) from None
        self.stdout.write('Primeiro superusuário criado com sucesso.')
