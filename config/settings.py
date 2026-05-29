from pathlib import Path
from decouple import config, Csv, UndefinedValueError
import os

BASE_DIR = Path(__file__).resolve().parent.parent

# ── Segurança Principal ────────────────────────────────────────────────────────
# python-decouple lê do .env automaticamente e lança UndefinedValueError
# se uma variável obrigatória (sem default) não estiver definida.
SECRET_KEY    = config('SECRET_KEY')
DEBUG         = config('DEBUG', default=False, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1', cast=Csv())

# Guard de segurança: impede subir para produção com chave fraca ou debug ativo
_INSECURE_KEYS = {'dev-secret-key-inseguro-troque-em-producao', 'change-me', 'insecure'}
if not DEBUG and (len(SECRET_KEY) < 40 or any(k in SECRET_KEY for k in _INSECURE_KEYS)):
    raise RuntimeError(
        "SECRET_KEY insegura detectada em modo produção (DEBUG=False). "
        "Gere uma chave forte: python -c \"from django.core.management.utils "
        "import get_random_secret_key; print(get_random_secret_key())\""
    )

# ── Modo Teste ─────────────────────────────────────────────────────────────────
# Aceita qualquer senha no login — apenas quando DEBUG=True.
# Ative em .env: TEST_MODE=True
# NUNCA suba para produção com TEST_MODE=True.
TEST_MODE = DEBUG and config('TEST_MODE', default=False, cast=bool)

# ── Apps Instalados ────────────────────────────────────────────────────────────
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',         # exigido pelo django-allauth
    # Terceiros
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    'axes',              # rate limiting / bloqueio por tentativas
    # django-allauth (autenticação social + Google OAuth)
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    # Apps do projeto
    'users',
    'consultations',
    'lumi',
]

# ── LUMI — IA Clínica ─────────────────────────────────────────────────────────
OPENAI_API_KEY = config('OPENAI_API_KEY', default='')

# ── Middleware ─────────────────────────────────────────────────────────────────
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',    # arquivos estáticos em produção
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'axes.middleware.AxesMiddleware',               # rate limiting (após auth middleware)
    'allauth.account.middleware.AccountMiddleware', # exigido pelo django-allauth >= 0.56
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'users.middleware.EmailVerificationMiddleware', # força verificação de e-mail
    'users.middleware.RBACPatientAccessMiddleware', # bloqueia acesso sem vínculo ativo
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

# ── Banco de Dados ─────────────────────────────────────────────────────────────
# Prioridade:
#   1. DATABASE_URL  → Railway / DigitalOcean injetam automaticamente
#   2. USE_SQLITE    → SQLite para dev local sem PostgreSQL
#   3. DB_*          → variáveis individuais (PostgreSQL local)
import dj_database_url

try:
    _DATABASE_URL = config('DATABASE_URL')
except UndefinedValueError:
    _DATABASE_URL = None

if _DATABASE_URL:
    DATABASES = {
        'default': dj_database_url.parse(
            _DATABASE_URL,
            conn_max_age=600,
            conn_health_checks=True,
            ssl_require=not DEBUG,   # SSL obrigatório em produção (Supabase exige)
        )
    }
elif config('USE_SQLITE', default=False, cast=bool):
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE':   'django.db.backends.postgresql',
            'NAME':     config('DB_NAME',     default='liddis_db'),
            'USER':     config('DB_USER',     default='postgres'),
            'PASSWORD': config('DB_PASSWORD', default=''),
            'HOST':     config('DB_HOST',     default='localhost'),
            'PORT':     config('DB_PORT',     default='5432'),
            'OPTIONS':  {'connect_timeout': 10},
        }
    }

# ── Autenticação ───────────────────────────────────────────────────────────────
AUTH_USER_MODEL = 'users.CustomUser'

LOGIN_URL             = '/login/'
LOGIN_REDIRECT_URL    = '/dashboard/'
LOGOUT_REDIRECT_URL   = '/'

AUTHENTICATION_BACKENDS = [
    'axes.backends.AxesStandaloneBackend',          # deve vir primeiro
    'users.backends.EmailOrUsernameBackend',        # login por e-mail ou username
    'allauth.account.auth_backends.AuthenticationBackend',  # backend do allauth (Google OAuth)
    'django.contrib.auth.backends.ModelBackend',   # fallback padrão
]

# Insere TestModeBackend apenas em desenvolvimento com TEST_MODE=True
if TEST_MODE:
    AUTHENTICATION_BACKENDS.insert(1, 'users.backends.TestModeBackend')

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
     'OPTIONS': {'min_length': 8}},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ── Segurança de Sessão ────────────────────────────────────────────────────────
SESSION_COOKIE_HTTPONLY = True          # JS não acessa o cookie de sessão
SESSION_COOKIE_SAMESITE = 'Lax'        # proteção CSRF básica
SESSION_COOKIE_AGE      = 60 * 60 * 8  # sessão expira em 8 horas
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

CSRF_COOKIE_HTTPONLY = False   # False = padrão Django; True impede forms server-rendered após rotação de sessão
CSRF_COOKIE_SAMESITE = 'Lax'

# ── Segurança HTTPS (ativas apenas em produção) ────────────────────────────────
if not DEBUG:
    SECURE_PROXY_SSL_HEADER          = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT              = True
    SECURE_HSTS_SECONDS              = 31536000   # 1 ano
    SECURE_HSTS_INCLUDE_SUBDOMAINS   = True
    SECURE_HSTS_PRELOAD              = True
    SESSION_COOKIE_SECURE            = True
    CSRF_COOKIE_SECURE               = True
    SECURE_CONTENT_TYPE_NOSNIFF      = True
    SECURE_BROWSER_XSS_FILTER        = True

X_FRAME_OPTIONS = 'DENY'

# ── Rate Limiting — django-axes ────────────────────────────────────────────────
AXES_ENABLED              = True
AXES_FAILURE_LIMIT        = 5          # bloqueia após 5 tentativas falhas
AXES_COOLOFF_TIME         = 1          # desbloqueia após 1 hora
AXES_LOCKOUT_TEMPLATE     = 'users/bloqueado.html'
AXES_RESET_ON_SUCCESS     = True       # zera o contador após login bem-sucedido
AXES_LOCKOUT_PARAMETERS   = ['username', 'ip_address']

# ── E-mail ─────────────────────────────────────────────────────────────────────
#
# EMAIL_PROVIDER define qual provedor usar:
#   console   → imprime no terminal (desenvolvimento)
#   resend    → Resend.com  (recomendado — 3 000 e-mails/mês grátis)
#   sendgrid  → SendGrid    (100/dia grátis)
#   gmail     → Gmail SMTP  (500/dia — use App Password, não a senha normal)
#   smtp      → qualquer servidor SMTP personalizado
#
EMAIL_PROVIDER = config('EMAIL_PROVIDER', default='console')

if EMAIL_PROVIDER == 'console':
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

elif EMAIL_PROVIDER == 'resend':
    # Resend usa SMTP com API Key como senha
    # Crie em: https://resend.com → API Keys
    EMAIL_BACKEND       = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST          = 'smtp.resend.com'
    EMAIL_PORT          = 587
    EMAIL_USE_TLS       = True
    EMAIL_HOST_USER     = 'resend'                              # literal "resend"
    EMAIL_HOST_PASSWORD = config('RESEND_API_KEY', default='')       # re_xxxxxxxxxxxx

elif EMAIL_PROVIDER == 'sendgrid':
    # SendGrid usa SMTP com API Key como senha
    # Crie em: https://app.sendgrid.com → Settings → API Keys
    EMAIL_BACKEND       = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST          = 'smtp.sendgrid.net'
    EMAIL_PORT          = 587
    EMAIL_USE_TLS       = True
    EMAIL_HOST_USER     = 'apikey'                              # literal "apikey"
    EMAIL_HOST_PASSWORD = config('SENDGRID_API_KEY', default='')     # SG.xxxxxxxxxxxx

elif EMAIL_PROVIDER == 'gmail':
    # Gmail requer "App Password" (não a senha normal)
    # Ative em: conta Google → Segurança → Verificação em duas etapas → App passwords
    EMAIL_BACKEND       = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST          = 'smtp.gmail.com'
    EMAIL_PORT          = 587
    EMAIL_USE_TLS       = True
    EMAIL_HOST_USER     = config('GMAIL_USER', default='')           # seu@gmail.com
    EMAIL_HOST_PASSWORD = config('GMAIL_APP_PASSWORD', default='')   # xxxx xxxx xxxx xxxx

else:  # smtp — configuração manual
    EMAIL_BACKEND       = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST          = config('EMAIL_HOST', default='localhost')
    EMAIL_PORT          = int(config('EMAIL_PORT', default='587'))
    EMAIL_USE_TLS       = config('EMAIL_USE_TLS', default='True') == 'True'
    EMAIL_HOST_USER     = config('EMAIL_HOST_USER', default='')
    EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')

DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='LIDDIS <noreply@liddis.com.br>')

# ── SMS (Twilio) — ativo quando TWILIO_ACCOUNT_SID estiver configurado ─────────
TWILIO_ACCOUNT_SID  = config('TWILIO_ACCOUNT_SID', default='')
TWILIO_AUTH_TOKEN   = config('TWILIO_AUTH_TOKEN', default='')
TWILIO_PHONE_NUMBER = config('TWILIO_PHONE_NUMBER', default='')
SMS_ENABLED = bool(TWILIO_ACCOUNT_SID)

# ── REST Framework ─────────────────────────────────────────────────────────────
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '30/minute',
        'user': '200/minute',
    },
}

from datetime import timedelta
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME':  timedelta(minutes=int(config('JWT_ACCESS_MINUTES', default='60'))),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=int(config('JWT_REFRESH_DAYS', default='7'))),
    'ROTATE_REFRESH_TOKENS':  True,
    'BLACKLIST_AFTER_ROTATION': True,
}

# ── CORS ───────────────────────────────────────────────────────────────────────
CORS_ALLOWED_ORIGINS = [o for o in config('CORS_ORIGINS', default='http://localhost:5173,http://localhost:3000').split(',') if o]

# ── CSRF Trusted Origins ───────────────────────────────────────────────────────
# Necessário para requisições POST de domínios externos (frontend separado, Railway, etc.)
# Em desenvolvimento: localhost já é confiável por padrão.
# Em produção: defina CSRF_TRUSTED_ORIGINS=https://seudominio.com no .env
_csrf_default = 'http://localhost:8000,http://127.0.0.1:8000' if DEBUG else ''
CSRF_TRUSTED_ORIGINS = [o for o in os.getenv('CSRF_TRUSTED_ORIGINS', _csrf_default).split(',') if o]

# ── Arquivos Estáticos (whitenoise em produção) ────────────────────────────────
STATIC_URL       = '/static/'
STATIC_ROOT      = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL  = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# ── Google Cloud Storage (produção) ───────────────────────────────────────────
# Em Cloud Run o filesystem é efêmero — todos os uploads devem ir para GCS.
# Variável obrigatória em prod: GCS_BUCKET_NAME
GCS_BUCKET_NAME = config('GCS_BUCKET_NAME', default='')
if not DEBUG and GCS_BUCKET_NAME:
    DEFAULT_FILE_STORAGE = 'storages.backends.gcloud.GoogleCloudStorage'
    GS_BUCKET_NAME       = GCS_BUCKET_NAME
    GS_DEFAULT_ACL       = None   # uniform bucket-level IAM policy
    GS_QUERYSTRING_AUTH  = False  # URLs diretas — acesso via view proxy autenticada
    GS_FILE_OVERWRITE    = False  # preserva histórico
    GS_OBJECT_PARAMETERS = {
        'cache_control': 'private, no-cache',  # dados médicos: sem cache público
    }
    MEDIA_URL = f'https://storage.googleapis.com/{GCS_BUCKET_NAME}/'

# ── Internacionalização ────────────────────────────────────────────────────────
LANGUAGE_CODE = 'pt-br'
TIME_ZONE     = 'America/Sao_Paulo'
USE_I18N      = True
USE_TZ        = True

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ── Monitoramento de Erros — Sentry ───────────────────────────────────────────
SENTRY_DSN = config('SENTRY_DSN', default='')
if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration()],
        traces_sample_rate=0.2,   # 20% das requisições para performance
        send_default_pii=False,   # não envia dados pessoais para o Sentry
        environment='production' if not DEBUG else 'development',
    )

# ── Sites Framework (exigido pelo django-allauth) ──────────────────────────────
SITE_ID     = 1
SITE_DOMAIN = config('SITE_DOMAIN', default='localhost:8000')
SITE_NAME   = config('SITE_NAME', default='LIDDIS')

# ── django-allauth ─────────────────────────────────────────────────────────────
ACCOUNT_LOGIN_METHODS         = {'email'}    # login por e-mail (não username)
ACCOUNT_SIGNUP_FIELDS         = ['email*', 'password1*', 'password2*']  # campos obrigatórios
ACCOUNT_EMAIL_VERIFICATION    = 'none'       # verificação OTP própria (não a do allauth)
ACCOUNT_ADAPTER               = 'users.adapters.CustomAccountAdapter'
ACCOUNT_DEFAULT_HTTP_PROTOCOL = 'http' if DEBUG else 'https'

SOCIALACCOUNT_ADAPTER      = 'users.adapters.CustomSocialAccountAdapter'
SOCIALACCOUNT_AUTO_SIGNUP  = True            # cria conta automaticamente no 1º login Google
SOCIALACCOUNT_EMAIL_REQUIRED = True
SOCIALACCOUNT_QUERY_EMAIL  = True
SOCIALACCOUNT_STORE_TOKENS = False

SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'APP': {
            'client_id': config('GOOGLE_CLIENT_ID', default=''),
            'secret':    config('GOOGLE_SECRET', default=''),
            'key':       '',
        },
        'SCOPE': ['profile', 'email'],
        'AUTH_PARAMS': {'access_type': 'online'},
        'VERIFIED_EMAIL': True,              # Google já verifica o e-mail
    }
}

# ── Logging ────────────────────────────────────────────────────────────────────
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{levelname}] {asctime} {module}: {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'liddis': {                  # use logging.getLogger('liddis') no código
            'handlers': ['console'],
            'level': 'DEBUG' if DEBUG else 'INFO',   # INFO em prod: registra eventos, silencia debug
            'propagate': False,
        },
        'django.request': {
            'handlers': ['console'],
            'level': 'ERROR',
            'propagate': False,
        },
    },
}
