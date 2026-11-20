from django.urls import include, path
from rest_framework.routers import DefaultRouter
from .api_views import MakananViewSet, JanjiTemuViewSet

router = DefaultRouter()
router.register(r'makanan', MakananViewSet, basename='api-makanan')
router.register(r'janji-temu', JanjiTemuViewSet, basename='api-janji-temu')

urlpatterns = [
    path('', include(router.urls)),
]