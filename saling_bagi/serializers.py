from rest_framework import serializers
from .models import Makanan, JanjiTemu


class MakananSerializer(serializers.ModelSerializer):
    pemberi = serializers.CharField(source='pemberi.username', read_only=True)
    nama_lokasi = serializers.ReadOnlyField()

    class Meta:
        model = Makanan
        fields = [
            'id',
            'nama_makanan',
            'deskripsi',
            'porsi',
            'foto',
            'lokasi_pengambilan',
            'lokasi_lainnya',
            'nama_lokasi',
            'batas_layak_konsumsi',
            'is_available',
            'pemberi',
        ]
        read_only_fields = ['id', 'pemberi', 'nama_lokasi']


class JanjiTemuSerializer(serializers.ModelSerializer):
    pengambil = serializers.CharField(source='pengambil.username', read_only=True)
    makanan_nama = serializers.CharField(source='makanan.nama_makanan', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = JanjiTemu
        fields = [
            'id',
            'makanan',
            'makanan_nama',
            'pengambil',
            'waktu_janji',
            'status',
            'status_display',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'pengambil', 'created_at', 'updated_at']