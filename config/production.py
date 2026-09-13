"""Entrada obrigatória para a aplicação de produção (AWS)."""
import os
from django.core.exceptions import ImproperlyConfigured

for name in ('DEBUG', 'SECRET_KEY', 'DATABASE_URL', 'ALLOWED_HOSTS'):
    if not os.environ.get(name, '').strip():
        raise ImproperlyConfigured(f'Produção exige {name} no ambiente do processo; .env não é fonte de credenciais.')

from .settings import *  # noqa: F403
from .settings import DEBUG, DATABASES, ALLOWED_HOSTS
from .settings import CSRF_TRUSTED_ORIGINS, CORS_ALLOWED_ORIGINS

if DEBUG:
    raise ImproperlyConfigured('Produção exige DEBUG=False.')
if DATABASES['default']['ENGINE'] != 'django.db.backends.postgresql':
    raise ImproperlyConfigured('Produção exige PostgreSQL configurado por DATABASE_URL.')
options = DATABASES['default'].get('OPTIONS', {})
if options.get('sslmode') != 'verify-full' or not options.get('sslrootcert'):
    raise ImproperlyConfigured('Produção exige sslmode=verify-full e sslrootcert para verificar o RDS.')
if not ALLOWED_HOSTS or '*' in ALLOWED_HOSTS:
    raise ImproperlyConfigured('Informe explicitamente os domínios de produção.')
if any(host.startswith('.') or '/' in host for host in ALLOWED_HOSTS):
    raise ImproperlyConfigured('ALLOWED_HOSTS deve conter hosts exatos, sem esquema, caminho ou wildcard.')
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_REDIRECT_EXEMPT = [r'^health/$']
if any(not origin.startswith('https://') or '*' in origin for origin in CSRF_TRUSTED_ORIGINS + CORS_ALLOWED_ORIGINS):
    raise ImproperlyConfigured('Produção aceita apenas origens HTTPS explícitas para CSRF/CORS.')
