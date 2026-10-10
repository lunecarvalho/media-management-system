"""Produção Render: PostgreSQL obrigatório, TLS e proxy específicos da plataforma."""
import os
import re
from urllib.parse import urlsplit
from django.core.exceptions import ImproperlyConfigured

for name in ('DEBUG', 'SECRET_KEY', 'DATABASE_URL', 'ALLOWED_HOSTS', 'CSRF_TRUSTED_ORIGINS'):
    if not os.environ.get(name, '').strip():
        raise ImproperlyConfigured(f'Render exige {name} no ambiente do processo.')

from .settings import *  # noqa: F403,E402
from .settings import DEBUG, SECRET_KEY, DATABASES, ALLOWED_HOSTS, CSRF_TRUSTED_ORIGINS, CORS_ALLOWED_ORIGINS

if DEBUG:
    raise ImproperlyConfigured('Render exige DEBUG=False.')
if len(set(SECRET_KEY)) < 5 or SECRET_KEY != SECRET_KEY.strip():
    raise ImproperlyConfigured('SECRET_KEY deve ser forte e sem espaços nas extremidades.')
if not ALLOWED_HOSTS or any(not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?', h)
                            or '..' in h for h in ALLOWED_HOSTS):
    raise ImproperlyConfigured('ALLOWED_HOSTS deve conter somente hosts exatos.')
if not CSRF_TRUSTED_ORIGINS:
    raise ImproperlyConfigured('Informe pelo menos uma origem CSRF HTTPS explícita.')
for origin in CSRF_TRUSTED_ORIGINS + CORS_ALLOWED_ORIGINS:
    try:
        parsed = urlsplit(origin)
        parsed.port  # Valida portas malformadas ou fora do intervalo permitido.
    except ValueError:
        raise ImproperlyConfigured('Origem HTTPS inválida.') from None
    if (parsed.scheme != 'https' or not parsed.hostname or '*' in origin
            or parsed.username or parsed.password or parsed.path
            or parsed.query or parsed.fragment):
        raise ImproperlyConfigured('Origens devem ser HTTPS explícitas, sem wildcard ou caminho.')
    if origin in CSRF_TRUSTED_ORIGINS and parsed.hostname not in ALLOWED_HOSTS:
        raise ImproperlyConfigured('Origem CSRF deve corresponder a um host autorizado.')

database = DATABASES['default']
if database['ENGINE'] != 'django.db.backends.postgresql' or not database.get('HOST'):
    raise ImproperlyConfigured('Render exige PostgreSQL com hostname; SQLite é somente desenvolvimento.')
options = database.setdefault('OPTIONS', {})
# Certificados internos Render são autoassinados: require criptografa, sem
# autenticar hostname/CA. Esta exceção está isolada; AWS continua verify-full.
mode = options.setdefault('sslmode', 'require')
if mode not in ('require', 'verify-full'):
    raise ImproperlyConfigured('Render exige TLS require ou verify-full.')
if mode == 'verify-full' and not options.get('sslrootcert'):
    raise ImproperlyConfigured('verify-full exige sslrootcert.')
try:
    timeout = int(options.get('connect_timeout', 5))
except (ValueError, TypeError):
    raise ImproperlyConfigured('connect_timeout deve ser inteiro entre 1 e 30.') from None
if not 1 <= timeout <= 30:
    raise ImproperlyConfigured('connect_timeout deve estar entre 1 e 30.')
options['connect_timeout'] = timeout

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_REDIRECT_EXEMPT = [r'^health/$']
