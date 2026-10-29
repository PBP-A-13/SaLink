
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import Makanan
from .forms import MakananForm


def index(request):
    makanan_list = Makanan.objects.filter(
        is_available=True,
        batas_layak_konsumsi__gt=timezone.now()
    ).select_related('pemberi').order_by('-id')

    return render(
        request,
        'saling_bagi/saling_bagi.html',
        {'makanan_list': makanan_list}
    )


@login_required
def tambah_makanan(request):
    if request.method == 'POST':
        form = MakananForm(request.POST, request.FILES)

        if form.is_valid():
            makanan = form.save(commit=False)
            makanan.pemberi = request.user
            makanan.save()

            messages.success(
                request,
                'Makanan berhasil dibagikan!'
            )
            return redirect('saling_bagi:index')
    else:
        form = MakananForm()

    return render(
        request,
        'saling_bagi/tambah_makanan.html',
        {'form': form}
    )


@login_required
@require_POST
def ambil_makanan(request, id):
    makanan = get_object_or_404(Makanan, id=id)

    if makanan.pemberi == request.user:
        messages.error(
            request,
            'Kamu tidak bisa mengambil makanan milikmu sendiri.'
        )
    elif not makanan.is_available:
        messages.warning(
            request,
            'Makanan ini sudah diambil.'
        )
    elif makanan.batas_layak_konsumsi <= timezone.now():
        makanan.is_available = False
        makanan.save(update_fields=['is_available'])

        messages.warning(
            request,
            'Maaf, makanan ini sudah melewati batas konsumsi.'
        )
    else:
        makanan.is_available = False
        makanan.save(update_fields=['is_available'])

        messages.success(
            request,
            f'Makanan berhasil diambil! Lokasi: '
            f'{makanan.lokasi_pengambilan}.'
        )

    return redirect('saling_bagi:index')
