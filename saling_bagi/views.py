from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import Makanan
from .forms import MakananForm # Import form yang baru kita buat
from SaLink.cache_keys import SALING_BAGI_INDEX, invalidate_public_pages

def index(request):
    """
    Halaman utama Bagi: daftar makanan yang baru diupload. (Map dihapus)
    """
    makanan_list = cache.get(SALING_BAGI_INDEX)
    if makanan_list is None:
        makanan_list = list(
            Makanan.objects
            .filter(is_available=True, batas_layak_konsumsi__gt=timezone.now())
            .select_related('pemberi')
            .order_by('-id')
        )
        cache.set(SALING_BAGI_INDEX, makanan_list, timeout=30)

    # Context sekarang lebih bersih karena tidak bawa markers map
    context = {
        'makanan_list': makanan_list,
    }
    return render(request, 'saling_bagi/saling_bagi.html', context)


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
        invalidate_public_pages(cache)
        messages.success(
            request,
            f'Makanan "{makanan.nama_makanan}" berhasil diambil! Temui pemberi di: {makanan.lokasi_pengambilan}.'
        )

    return redirect('saling_bagi:index')


@login_required
def tambah_makanan(request):
    """
    Fungsi baru untuk user membagikan makanan (Fitur Create).
    """
    if request.method == 'POST':
        # request.FILES wajib disertakan kalau form-nya ada upload foto/gambar
        form = MakananForm(request.POST, request.FILES)
        if form.is_valid():
            makanan_baru = form.save(commit=False)
            makanan_baru.pemberi = request.user
            makanan_baru.save()
            invalidate_public_pages(cache)
            messages.success(request, 'Makanan berhasil dibagikan ke mahasiswa lain!')
            return redirect('saling_bagi:index')
    else:
        form = MakananForm()
    
    return render(request, 'saling_bagi/tambah_makanan.html', {'form': form})