# PATH: /Archen/Archen/settings.py
import os
from pathlib import Path
from django.urls import reverse_lazy  # type: ignore
# import locale
# import jdatetime

BASE_DIR = Path(__file__).resolve().parent.parent

# NOTE: In production, SECRET_KEY must come from environment for security.
# English comment: Prefer to set SECRET_KEY via environment; fallback is for local dev only.
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-archen-key')

# English comment: DEBUG defaults to True for dev; set DEBUG=0/false in production.
DEBUG = str(os.environ.get('DEBUG', '1')).lower() in {'1', 'true', 'yes'}

# English comment: Allow all in dev; in production set ALLOWED_HOSTS from env.
_env_allowed = os.environ.get('ALLOWED_HOSTS')
ALLOWED_HOSTS: list[str] = (
    [h for h in (_env_allowed.split() if _env_allowed else ['*']) if h]
)
# Trust HTTPS scheme from reverse proxies like Cloudflare Tunnel
# This ensures Django sees requests as secure when X-Forwarded-Proto: https
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
# Allow CSRF for Cloudflare Quick Tunnel URLs
# (e.g., https://<rand>.trycloudflare.com)
# NOTE: Keep this broad only for development; restrict in production.
# English comment: Default CSRF trusted origins for dev (Cloudflare Quick Tunnel).
CSRF_TRUSTED_ORIGINS = ['https://*.trycloudflare.com']

# English comment: If DOMAIN is provided (e.g., archenmobl.com), trust it for HTTPS.
_domain = os.environ.get('DOMAIN')
if _domain:
    # Normalize: strip protocol and slashes if any
    _domain = _domain.replace('http://', '').replace('https://', '').strip('/')
    CSRF_TRUSTED_ORIGINS += [
        f"https://{_domain}",
        f"https://www.{_domain}",
    ]
# CSRF_TRUSTED_ORIGINS = ['http://192.168.31.114:8000']  # Actual computer IP

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'pwa',
    'users',
    'orders',
    'inventory',
    'production_line',
    'jobs',
    'reports',
    'maintenance',
    'accounting',
    'widget_tweaks',
    'django_jalali',
    'csp',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'csp.middleware.CSPMiddleware',
]

# Content Security Policy settings for django-csp >= 4.0
CONTENT_SECURITY_POLICY = {
    "DIRECTIVES": {
        "default-src": ["'self'"],
        # Allow inline/eval in DEBUG for Tailwind CDN convenience (not for strict prod)
        # NOTE: We keep the two CDN hosts here so first-run can populate SW cache.
        "script-src": ["'self'", "'unsafe-inline'", "'unsafe-eval'", "cdn.tailwindcss.com", "code.jquery.com"],
        "style-src": ["'self'", "'unsafe-inline'", "code.jquery.com"],
        "img-src":    ["'self'", "data:", "blob:"],
        "connect-src": ["'self'"],
        "worker-src": ["'self'"],       # For the service worker
        "manifest-src": ["'self'"],     # For manifest.json
    }
}

# django-csp 3.x/4.x compatible explicit settings (keeps current behavior)
# Removed legacy CSP_* variables to comply with django-csp >= 4.0

ROOT_URLCONF = 'Archen.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / "templates"],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'Archen.context_processors.full_name_context',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    }
]

WSGI_APPLICATION = 'Archen.wsgi.application'
ASGI_APPLICATION = 'Archen.asgi.application'

AUTH_USER_MODEL = 'users.CustomUser'

# English comment: Default DB is SQLite. Can be overridden with env vars for Postgres/MySQL.
#_db_engine = os.environ.get('DB_ENGINE', 'django.db.backends.sqlite3')
_db_engine = os.environ.get('DB_ENGINE', 'django.db.backends.postgresql')
if _db_engine == 'django.db.backends.sqlite3':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': os.environ.get('DJANGO_DB_NAME', str(BASE_DIR / 'db.sqlite3')),
        }
    }
else:
    # English comment: Generic RDBMS config (PostgreSQL/MySQL) from environment.
    DATABASES = {
        'default': {
            'ENGINE': _db_engine, 
            'NAME': os.environ.get('DB_NAME','archenmo_db'),
            'USER': os.environ.get('DB_USER','archenmo_archenmo'),
            'PASSWORD': os.environ.get('DB_PASSWORD','uuX61R09aT![Vl'),
            'HOST': os.environ.get('DB_HOST','127.0.0.1'),
            'PORT': os.environ.get('DB_PORT','5432'),
            # English comment: For managed SSL DBs, allow optional connection options.
            # 'OPTIONS': json.loads(os.environ.get('DB_OPTIONS', '{}')) if needed
        }
    }

LANGUAGE_CODE = 'fa'
TIME_ZONE = 'Asia/Tehran'
USE_I18N = True
USE_L10N = True
USE_TZ = True

LOCALE_PATHS = [
    BASE_DIR / 'locale',
]

# English: STATIC_URL must be absolute to avoid broken links on nested URLs
STATIC_URL = '/static/'
STATICFILES_DIRS = [
    BASE_DIR / "static",
]
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Media files (used in DEBUG for local development and by servers in prod)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

SESSION_EXPIRE_AT_BROWSER_CLOSE = False
SESSION_COOKIE_AGE = 60 * 60 * 24 * 14  # 14 days

PWA_APP_NAME = 'صنایع چوبی آرچن'
PWA_APP_DESCRIPTION = "سیستم مدیریت تولید و سفارش‌ها مبلمان"
PWA_APP_THEME_COLOR = '#2365D1'
PWA_APP_BACKGROUND_COLOR = "#92E2DE"
PWA_APP_DISPLAY = 'standalone'
PWA_APP_SCOPE = '/'
PWA_APP_ORIENTATION = 'portrait'
PWA_APP_OFFLINE_PAGE = 'offline.html'  # Offline page template
PWA_SERVICE_WORKER_PATH = BASE_DIR / "static" / "serviceworker.js"

PWA_APP_START_URL = '/'
PWA_APP_ICONS = [
    {
        'src': '/static/icons/icon-192x192.png',
        'sizes': '192x192',
        'purpose': 'any maskable',  # prefer maskable; supply transparent assets
    },
    {
        'src': '/static/icons/icon-512x512.png',
        'sizes': '512x512',
        'purpose': 'any maskable',
    }
]
PWA_APP_LANG = 'fa'

LOGIN_URL = reverse_lazy("login")          
LOGIN_REDIRECT_URL = reverse_lazy("dashboard")
LOGOUT_REDIRECT_URL = reverse_lazy("login")


# In production, tighten CSP (drop unsafe-inline/eval and external CDNs).
# In DEBUG, send report-only header using new v4 setting name.
if DEBUG:
    # Use report-only so development isn't blocked by CSP
    CONTENT_SECURITY_POLICY_REPORT_ONLY = CONTENT_SECURITY_POLICY
    CONTENT_SECURITY_POLICY = None
else:
    # Production: allow inline for compatibility with current templates and jQuery UI
    # English: If you later refactor to external JS/CSS files, you can tighten CSP.
    CONTENT_SECURITY_POLICY = {
        "DIRECTIVES": {
            "default-src": ["'self'"],
            "script-src": ["'self'", "'unsafe-inline'", "'unsafe-eval'"],
            "style-src": ["'self'", "'unsafe-inline'"],
            "img-src":    ["'self'", "data:"],
            "connect-src": ["'self'"],
            "worker-src": ["'self'"],
            "manifest-src": ["'self'"],
        }
    }

# --- Static files: enable WhiteNoise in production for robust static serving ---
# We add the middleware dynamically in production to keep dev friction low.
if not DEBUG:
    # Insert WhiteNoise right after SecurityMiddleware
    try:
        idx = MIDDLEWARE.index('django.middleware.security.SecurityMiddleware')
        MIDDLEWARE.insert(idx + 1, 'whitenoise.middleware.WhiteNoiseMiddleware')
    except ValueError:
        # Fallback: append if SecurityMiddleware not found (should not happen)
        MIDDLEWARE.append('whitenoise.middleware.WhiteNoiseMiddleware')
    # English: Use non-manifest storage to avoid hashed path mismatches on shared hosts
    # and to keep URLs predictable (/static/...). Enable gzip/brotli via WhiteNoise.
    STATICFILES_STORAGE = 'whitenoise.storage.CompressedStaticFilesStorage'
