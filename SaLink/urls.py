from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path  
from django.views.generic import RedirectView
from django.views.static import serve           

urlpatterns = [
    path('admin/', admin.site.urls),
    path('akun/', include('user_page.urls')),
    path('', include('main.urls')),
    path('saling-bagi/', include('saling_bagi.urls')),
    path('saling-beli/', include('saling_beli.urls')),
    path('saling-pinjam/', include('saling_pinjam.urls')),
    path('saling-nebeng/', include('saling_tebeng.urls')),
    path('favicon.ico', RedirectView.as_view(url='/static/favicon/favicon.ico', permanent=False)),
    path(
        'saling-tebeng/',
        RedirectView.as_view(url='/saling-nebeng/', permanent=False),
    ),
    path(
        'saling-tebeng/<path:path>',
        RedirectView.as_view(
            url='/saling-nebeng/%(path)s',
            permanent=False,
            query_string=True,
        ),
    ),
    path(
        'saling_tebeng/',
        RedirectView.as_view(url='/saling-nebeng/', permanent=False),
    ),
    path('nebeng/', RedirectView.as_view(url='/saling-nebeng/', permanent=False)),
]

# GANTI blok "if settings.DEBUG" dengan kode paksa ini:
urlpatterns += [
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
]