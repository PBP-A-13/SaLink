from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('main.urls')),
    path('saling-bagi/', include('saling_bagi.urls')),
    path('saling-beli/', include('saling_beli.urls')),
    path('saling-pinjam/', include('saling_pinjam.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
