from datetime import date
from django.core.exceptions import ValidationError


def validar_ano(value):
    if value is not None and not 1 <= value <= date.today().year + 1:
        raise ValidationError('Informe um ano entre 1 e o próximo ano.')


def validar_codigo(value):
    if not value or not value.strip() or any(c.isspace() for c in value):
        raise ValidationError('O código deve ser preenchido e não pode conter espaços.')
