from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('main.urls')),
    path('saling-bagi/', include('saling_bagi.urls')),
    path('saling-beli/', include('saling_beli.urls')),
]
