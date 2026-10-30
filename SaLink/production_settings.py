"""Production settings layered over the backwards-compatible default settings."""

from .settings import *


DEBUG = False
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'bikin-kunci-rahasia-bebas-salink-2025')
ALLOWED_HOSTS = [host for host in os.environ['DJANGO_ALLOWED_HOSTS'].split(',') if host]
CSRF_TRUSTED_ORIGINS = [origin for origin in os.getenv('DJANGO_CSRF_TRUSTED_ORIGINS', '').split(',') if origin]

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_CROSS_ORIGIN_OPENER_POLICY = 'same-origin'
# PWS menerminasi TLS di proxy; tanpa header ini Django mengira request masih HTTP
# dan SECURE_SSL_REDIRECT menyebabkan redirect loop tak berujung.
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = os.getenv('DJANGO_SECURE_SSL_REDIRECT', '0') == '1'
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = int(os.getenv('DJANGO_HSTS_SECONDS', '31536000'))
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# PWS tidak menjalankan collectstatic saat build. Finders membuat Whitenoise
# menyajikan berkas langsung dari folder static aplikasi.
WHITENOISE_USE_FINDERS = True

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
        'LOCATION': os.getenv('DJANGO_CACHE_DIR', str(BASE_DIR / '.cache' / 'django')),
        'TIMEOUT': 300,
    },
}