
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import Makanan, JanjiTemu
from .forms import MakananForm, JanjiTemuForm


def index(request):
    makanan_list = Makanan.objects.filter(
        is_available=True,
        batas_layak_konsumsi__gt=timezone.now()
    ).select_related('pemberi').order_by('-id')

    context = {
        'makanan_list': makanan_list,
        'lokasi_choices': Makanan.LOKASI_CHOICES,
    }

    return render(request, 'saling_bagi/index.html', context)


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
def ajukan_janji(request, id):
    makanan = get_object_or_404(
        Makanan,
        id=id
    )

    if makanan.pemberi == request.user:
        messages.error(
            request,
            'Kamu tidak bisa mengambil makanan milikmu sendiri.'
        )
        return redirect('saling_bagi:index')

    if not makanan.is_available:
        messages.warning(
            request,
            'Makanan ini sudah tidak tersedia.'
        )
        return redirect('saling_bagi:index')

    if makanan.batas_layak_konsumsi <= timezone.now():
        makanan.is_available = False
        makanan.save(update_fields=['is_available'])

        messages.warning(
            request,
            'Makanan sudah melewati batas layak konsumsi.'
        )
        return redirect('saling_bagi:index')

    if request.method == 'POST':
        form = JanjiTemuForm(
            request.POST,
            makanan=makanan
        )

        if form.is_valid():
            try:
                with transaction.atomic():
                    makanan_terkunci = Makanan.objects.select_for_update().get(
                        id=makanan.id
                    )

                    if not makanan_terkunci.is_available:
                        raise ValueError(
                            'Makanan sudah dipesan orang lain.'
                        )

                    if makanan_terkunci.batas_layak_konsumsi <= timezone.now():
                        raise ValueError(
                            'Makanan sudah melewati batas konsumsi.'
                        )

                    janji = form.save(commit=False)
                    janji.makanan = makanan_terkunci
                    janji.pengambil = request.user
                    janji.save()

                    makanan_terkunci.is_available = False
                    makanan_terkunci.save(
                        update_fields=['is_available']
                    )

                messages.success(
                    request,
                    'Permintaan janji temu berhasil dikirim! '
                    'Tunggu persetujuan pemberi makanan.'
                )

                return redirect('saling_bagi:janji_temu')

            except (IntegrityError, ValueError):
                messages.error(
                    request,
                    'Makanan sudah dipesan atau tidak lagi tersedia.'
                )
                return redirect('saling_bagi:index')

    else:
        form = JanjiTemuForm(makanan=makanan)

    return render(
        request,
        'saling_bagi/ajukan_janji.html',
        {
            'makanan': makanan,
            'form': form,
        }
    )


@login_required
def janji_temu(request):
    janji_dibuat = JanjiTemu.objects.filter(
        pengambil=request.user
    ).select_related(
        'makanan',
        'makanan__pemberi'
    )

    janji_diterima = JanjiTemu.objects.filter(
        makanan__pemberi=request.user
    ).select_related(
        'makanan',
        'pengambil'
    )

    return render(
        request,
        'saling_bagi/janji_temu.html',
        {
            'janji_dibuat': janji_dibuat,
            'janji_diterima': janji_diterima,
        }
    )


@login_required
@require_POST
def keputusan_janji(request, id):
    with transaction.atomic():
        janji = get_object_or_404(
            JanjiTemu.objects.select_for_update(),
            id=id
        )

        if janji.makanan.pemberi != request.user:
            messages.error(
                request,
                'Kamu tidak memiliki izin untuk mengubah janji temu ini.'
            )
            return redirect('saling_bagi:janji_temu')

        if janji.status != 'PENDING':
            messages.warning(
                request,
                'Janji temu ini sudah diproses.'
            )
            return redirect('saling_bagi:janji_temu')

        keputusan = request.POST.get('keputusan')

        if keputusan == 'approve':
            if janji.makanan.batas_layak_konsumsi <= timezone.now():
                janji.status = 'REJECTED'
                janji.save(update_fields=['status', 'updated_at'])

                makanan = janji.makanan
                makanan.is_available = False
                makanan.save(update_fields=['is_available'])

                messages.warning(
                    request,
                    'Permintaan tidak dapat disetujui karena makanan '
                    'sudah melewati batas konsumsi.'
                )
            else:
                janji.status = 'APPROVED'
                janji.save(update_fields=['status', 'updated_at'])

                messages.success(
                    request,
                    'Janji temu berhasil disetujui!'
                )

        elif keputusan == 'reject':
            janji.status = 'REJECTED'
            janji.save(update_fields=['status', 'updated_at'])

            makanan = janji.makanan

            makanan.is_available = (
                makanan.batas_layak_konsumsi > timezone.now()
            )

            makanan.save(update_fields=['is_available'])

            messages.success(
                request,
                'Permintaan janji temu ditolak. '
                'Makanan kembali tersedia jika masih layak konsumsi.'
            )

        else:
            messages.error(
                request,
                'Pilihan keputusan tidak valid.'
            )

    return redirect('saling_bagi:janji_temu')


@login_required
@require_POST
def selesaikan_janji(request, id):
    janji = get_object_or_404(
        JanjiTemu.objects.select_related('makanan'),
        id=id
    )

    if janji.makanan.pemberi != request.user:
        messages.error(
            request,
            'Hanya pemberi makanan yang dapat menyelesaikan janji temu.'
        )

    elif janji.status != 'APPROVED':
        messages.warning(
            request,
            'Hanya janji temu yang disetujui yang dapat diselesaikan.'
        )

    else:
        janji.status = 'COMPLETED'
        janji.save(update_fields=['status', 'updated_at'])

        messages.success(
            request,
            'Penyerahan makanan berhasil ditandai selesai!'
        )

    return redirect('saling_bagi:janji_temu')
