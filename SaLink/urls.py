# ============================================================
# SaLink/urls.py  ->  ROUTER UTAMA project. Semua request masuk ke sini dulu,
# lalu dibagi ke urls.py masing-masing app berdasarkan awalan URL.
# ============================================================

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path         # re_path = path dengan regex
from django.views.generic import RedirectView          # view bawaan untuk redirect
from django.views.static import serve                  # view bawaan untuk melayani file statis/media

urlpatterns = [
    path('admin/', admin.site.urls),
    path('akun/', include('user_page.urls')),
    path('api/v1/auth/', include('user_page.api_urls')),
    path('', include('main.urls')),
    path('saling-bagi/', include('saling_bagi.urls')),
    path('admin/', admin.site.urls),                   # /admin/ -> panel admin Django
    path('akun/', include('user_page.urls')),          # /akun/...        -> app login/profil
    path('', include('main.urls')),                    # /                -> halaman home
    path('saling-bagi/', include('saling_bagi.urls')), # /saling-bagi/... -> BAGIAN KITA (diteruskan ke urls app)
    path('saling-beli/', include('saling_beli.urls')),
    path('saling-pinjam/', include('saling_pinjam.urls')),
    path('saling-nebeng/', include('saling_tebeng.urls')),
    path('favicon.ico', RedirectView.as_view(url='/static/favicon/favicon.ico', permanent=False)),

    # Beberapa path lama (typo 'tebeng') dialihkan ke path yang benar 'nebeng'
    path(
        'saling-tebeng/',
        RedirectView.as_view(url='/saling-nebeng/', permanent=False),   # permanent=False -> redirect 302 (sementara)
    ),
    path(
        'saling-tebeng/<path:path>',                   # <path:path> menangkap sisa URL (boleh ada '/')
        RedirectView.as_view(
            url='/saling-nebeng/%(path)s',             # sisa URL ditempel ke tujuan
            permanent=False,
            query_string=True,                         # ?param=... ikut terbawa
        ),
    ),
    path(
        'saling_tebeng/',
        RedirectView.as_view(url='/saling-nebeng/', permanent=False),
    ),
    path('nebeng/', RedirectView.as_view(url='/saling-nebeng/', permanent=False)),
]

# Melayani file upload (foto makanan) di /media/...
# Biasanya hanya aktif saat DEBUG, tapi di PWS dipaksa aktif karena WhiteNoise tidak melayani media.
# Jujur ke asdos: ini solusi praktis, bukan best practice produksi (idealnya pakai storage/CDN).
urlpatterns += [
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
]


# ============================================================
# saling_bagi/admin.py  (file terpisah, digabung di sini biar ringkas)
# ============================================================
# from django.contrib import admin
# from .models import Makanan
#
# admin.site.register(Makanan)     # daftarkan model ke /admin/ supaya data bisa dikelola lewat UI
#                                  # (JanjiTemu belum didaftarkan -> kandidat live coding)