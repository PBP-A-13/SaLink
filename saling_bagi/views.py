from django.shortcuts import render
from .models import Makanan

def show_saling_bagi(request):
    # Mengambil semua data makanan yang masih tersedia dari database
    makanan_tersedia = Makanan.objects.filter(is_available=True)
    
    # Membungkus data untuk dikirim ke HTML
    context = {
        'daftar_makanan': makanan_tersedia,
    }
    
    return render(request, "saling_bagi/main.html", context)