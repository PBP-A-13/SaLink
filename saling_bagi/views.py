import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import Makanan


def index(request):
    """
    Halaman utama Bagi: map lokasi makanan + daftar makanan yang baru diupload.
    """
    makanan_list = (
        Makanan.objects
        .filter(is_available=True, batas_layak_konsumsi__gt=timezone.now())
        .select_related('pemberi')
        .order_by('-id')
    )

    # Data pin untuk map Leaflet
    markers = [
        {
            'id': m.id,
            'nama': m.nama_makanan,
            'lokasi': m.lokasi_pengambilan,
            'lat': m.latitude,
            'lng': m.longitude,
        }
        for m in makanan_list
        if m.latitude is not None and m.longitude is not None
    ]

    context = {
        'makanan_list': makanan_list,
        'markers': markers,
    }
    return render(request, 'saling_bagi/index.html', context)


@login_required
@require_POST
def ambil_makanan(request, id):
    """
    Mengambil makanan yang dibagikan: status makanan jadi tidak tersedia.
    """
    makanan = get_object_or_404(Makanan, id=id)

    if makanan.pemberi == request.user:
        messages.error(request, 'Kamu tidak bisa mengambil makanan milikmu sendiri.')
    elif not makanan.is_available:
        messages.warning(request, 'Maaf, makanan ini sudah diambil orang lain.')
    else:
        makanan.is_available = False
        makanan.save()
        messages.success(
            request,
            f'Makanan "{makanan.nama_makanan}" berhasil diambil! Ambil di: {makanan.lokasi_pengambilan}.'
        )

    return redirect('saling_bagi:index')