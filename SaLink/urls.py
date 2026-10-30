from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('akun/', include('user_page.urls')),
    path('', include('main.urls')),
    path('saling-bagi/', include('saling_bagi.urls')),
    path('saling-beli/', include('saling_beli.urls')),
    path('saling-pinjam/', include('saling_pinjam.urls')),
    path('saling-nebeng/', include('saling_tebeng.urls')),
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

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
