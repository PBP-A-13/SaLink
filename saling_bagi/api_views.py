from django.db.models import Q
from rest_framework import permissions, viewsets
from .models import Makanan, JanjiTemu
from .serializers import MakananSerializer, JanjiTemuSerializer


class MakananViewSet(viewsets.ModelViewSet):
    serializer_class = MakananSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        queryset = Makanan.objects.filter(is_available=True).order_by('-id')
        lokasi = self.request.query_params.get('lokasi')
        search = self.request.query_params.get('search')

        if lokasi and lokasi != 'semua':
            queryset = queryset.filter(lokasi_pengambilan=lokasi)
        if search:
            queryset = queryset.filter(
                Q(nama_makanan__icontains=search) | Q(deskripsi__icontains=search)
            )
        return queryset

    def perform_create(self, serializer):
        serializer.save(pemberi=self.request.user)


class JanjiTemuViewSet(viewsets.ModelViewSet):
    serializer_class = JanjiTemuSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        queryset = JanjiTemu.objects.select_related('makanan', 'pengambil')
        if self.request.user.is_authenticated:
            return queryset.filter(
                Q(pengambil=self.request.user) | Q(makanan__pemberi=self.request.user)
            )
        return queryset.none()

    def perform_create(self, serializer):
        serializer.save(pengambil=self.request.user)