"""Production settings layered over the backwards-compatible default settings."""

from .settings import *


DEBUG = False
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'bikin-kunci-rahasia-bebas-salink-2025')
ALLOWED_HOSTS = [host for host in os.environ['DJANGO_ALLOWED_HOSTS'].split(',') if host]
CSRF_TRUSTED_ORIGINS = [origin for origin in os.getenv('DJANGO_CSRF_TRUSTED_ORIGINS', '').split(',') if origin]

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_CROSS_ORIGIN_OPENER_POLICY = 'same-origin'
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = int(os.getenv('DJANGO_HSTS_SECONDS', '31536000'))
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
        'LOCATION': os.getenv('DJANGO_CACHE_DIR', str(BASE_DIR / '.cache' / 'django')),
        'TIMEOUT': 300,
    },
}
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')