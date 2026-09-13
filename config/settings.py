from pathlib import Path
import dj_database_url

from decouple import config
from django.core.exceptions import ImproperlyConfigured
from django.contrib.messages import constants as message_constants

# Build paths inside the project
BASE_DIR = Path(__file__).resolve().parent.parent

INSECURE_SECRET_KEY_DEFAULT = 'django-insecure-dev-key-change-in-production'

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config('SECRET_KEY', default=INSECURE_SECRET_KEY_DEFAULT)

# SECURITY WARNING: don't run with debug turned on in production!
try:
    DEBUG = config('DEBUG', default=False, cast=bool)
except ValueError as exc:
    raise ImproperlyConfigured('DEBUG deve ser True ou False; revise também as variáveis do processo.') from exc

if not DEBUG and (len(SECRET_KEY) < 50 or SECRET_KEY.startswith('django-insecure-') or 'sua-chave' in SECRET_KEY):
    raise ImproperlyConfigured(
        'SECRET_KEY must be set via the SECRET_KEY environment variable when DEBUG=False.'
    )

ALLOWED_HOSTS = [host.strip() for host in config('ALLOWED_HOSTS', default='localhost,127.0.0.1').split(',') if host.strip()]

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third-party apps
    'rest_framework',
    'corsheaders',
    
    # Local apps
    'acervo.apps.AcervoConfig',
    'movimentacoes.apps.MovimentacoesConfig',
    'categorias.apps.CategoriasConfig',
    'usuarios.apps.UsuariosConfig',
    'api.apps.ApiConfig',
    'integracoes.apps.IntegracoesConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'usuarios.middleware.AcessoInternoMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# Database
# Prioridade: DATABASE_URL (Render/Supabase) > DB_HOST definido (Docker/Postgres local) > SQLite (dev local)
DATABASE_URL = config('DATABASE_URL', default='')
DB_HOST = config('DB_HOST', default='')

if DATABASE_URL:
    try:
        DATABASES = {'default': dj_database_url.parse(DATABASE_URL, conn_max_age=60, conn_health_checks=True)}
    except (ValueError, KeyError):
        raise ImproperlyConfigured('DATABASE_URL inválida. Revise o esquema e a codificação das credenciais.') from None
elif DB_HOST:
    DATABASES = {
        'default': {
            'ENGINE': config('DB_ENGINE', default='django.db.backends.postgresql'),
            'NAME': config('DB_NAME', default='mediatrack'),
            'USER': config('DB_USER', default='postgres'),
            'PASSWORD': config('DB_PASSWORD', default=''),
            'HOST': DB_HOST,
            'PORT': config('DB_PORT', default='5432'),
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Sao_Paulo'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'},
}

# Media files (User uploads)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Autenticação
LOGIN_URL = 'usuarios:login'
LOGIN_REDIRECT_URL = 'dashboard'
LOGOUT_REDIRECT_URL = 'usuarios:login'
MESSAGE_TAGS = {message_constants.SUCCESS: 'sucesso', message_constants.ERROR: 'erro', message_constants.WARNING: 'aviso', message_constants.INFO: 'info'}

# Django REST Framework
REST_FRAMEWORK = {
    'EXCEPTION_HANDLER': 'api.exceptions.business_exception_handler',
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'usuarios.permissions.AcessoAPI',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
}

# CORS settings
CORS_ALLOWED_ORIGINS = config(
    'CORS_ALLOWED_ORIGINS',
    default='',
).split(',')
CORS_ALLOWED_ORIGINS = [origin.strip() for origin in CORS_ALLOWED_ORIGINS if origin.strip()]

# CSRF (necessário quando o app roda atrás de um domínio/proxy em produção, ex: Render)
CSRF_TRUSTED_ORIGINS = [
    origem.strip() for origem in config('CSRF_TRUSTED_ORIGINS', default='').split(',') if origem.strip()
]

# API Base URLs (para integração futura)
MUSICBRAINZ_API_URL = config('MUSICBRAINZ_API_URL', default='https://musicbrainz.org/ws/2/')
MUSICBRAINZ_USER_AGENT = config('MUSICBRAINZ_USER_AGENT', default='MediaTrack/1.0 (https://github.com/lunecarvalho/media-management-system)')
MOVIES_DATASET_PATH = config('MOVIES_DATASET_PATH', default='')
TMDB_API_KEY = config('TMDB_API_KEY', default='')

LOGGING = {
    'version': 1, 'disable_existing_loggers': False,
    'handlers': {'console': {'class': 'logging.StreamHandler'}},
    'loggers': {'mediatrack': {'handlers': ['console'], 'level': 'INFO', 'propagate': False}},
}

# Segurança adicional em produção (DEBUG=False)
if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = config('SECURE_SSL_REDIRECT', default=True, cast=bool)
    if config('TRUST_PROXY_HEADERS', default=False, cast=bool):
        SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_HSTS_SECONDS = config('SECURE_HSTS_SECONDS', default=31536000, cast=int)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    X_FRAME_OPTIONS = 'DENY'

