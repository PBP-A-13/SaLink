# ============================================================
# views.py  ->  "V" di MVT. LOGIKA UTAMA: terima request, olah data, kirim response.
# Alur satu view: urls.py memanggil fungsi -> view ambil/ubah data (model/form) -> render template.
# ============================================================

from django.contrib import messages                        # pesan flash (sukses/error) sekali tampil
from django.contrib.auth.decorators import login_required  # wajib login; kalau belum, redirect ke halaman login
from django.db import IntegrityError, transaction          # IntegrityError: pelanggaran constraint DB; transaction: untuk atomic
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone                          # waktu sekarang sadar timezone
from django.views.decorators.http import require_POST      # hanya izinkan method POST

from .models import Makanan, JanjiTemu
from .forms import MakananForm, JanjiTemuForm


# ------------------------------------------------------------
# 1. DAFTAR MAKANAN (halaman utama, publik tanpa login)
# ------------------------------------------------------------
def index(request):
    makanan_list = Makanan.objects.filter(             # SELECT ... WHERE ...
        is_available=True,                             # hanya yang masih tersedia
        batas_layak_konsumsi__gt=timezone.now()        # __gt = greater than: belum kedaluwarsa
    ).select_related(
        'pemberi'                                      # JOIN ke tabel user sekaligus -> cegah N+1 query di template
    ).order_by('-id')                                  # id terbesar dulu = yang terbaru di atas

    return render(
        request,
        'saling_bagi/saling_bagi.html',                # template yang dipakai
        {'makanan_list': makanan_list}                 # context: variabel yang bisa dipakai di template
    )


# ------------------------------------------------------------
# 2. TAMBAH MAKANAN (pemberi)
# ------------------------------------------------------------
@login_required                                        # belum login -> dilempar ke login
def tambah_makanan(request):
    if request.method == 'POST':                       # user menekan submit
        form = MakananForm(request.POST, request.FILES)   # request.FILES wajib supaya upload foto terbaca

        if form.is_valid():                            # menjalankan semua clean_* dan clean()
            makanan = form.save(commit=False)          # buat objek TAPI belum simpan ke DB
            makanan.pemberi = request.user             # isi field yang tidak ada di form
            makanan.save()                             # baru simpan ke DB

            messages.success(
                request,
                'Makanan berhasil dibagikan!'
            )

            return redirect('saling_bagi:index')       # pola Post/Redirect/Get: refresh tidak submit ulang

    else:                                              # method GET: baru buka halaman
        form = MakananForm()                           # form kosong

    return render(                                     # sampai sini kalau GET atau form tidak valid
        request,                                       # (form invalid ikut dikirim -> error tampil di template)
        'saling_bagi/tambah_makanan.html',
        {'form': form}
    )


# ------------------------------------------------------------
# 3. AJUKAN JANJI TEMU (pengambil) - view paling penting
# ------------------------------------------------------------
@login_required
def ajukan_janji(request, id):                         # id berasal dari URL: ajukan/<int:id>/
    makanan = get_object_or_404(                       # ambil objek, kalau tidak ada -> halaman 404
        Makanan,
        id=id
    )

    # --- Cek awal (untuk pengalaman user, belum aman dari balapan) ---
    if makanan.pemberi == request.user:                # tidak boleh ambil makanan sendiri
        messages.error(
            request,
            'Kamu tidak bisa mengambil makanan milikmu sendiri.'
        )
        return redirect('saling_bagi:index')

    if not makanan.is_available:                       # sudah dipesan orang lain
        messages.warning(
            request,
            'Makanan ini sudah tidak tersedia.'
        )
        return redirect('saling_bagi:index')

    if makanan.batas_layak_konsumsi <= timezone.now(): # sudah kedaluwarsa
        makanan.is_available = False
        makanan.save(update_fields=['is_available'])   # update_fields: hanya tulis kolom ini ke DB

        messages.warning(
            request,
            'Makanan sudah melewati batas layak konsumsi.'
        )
        return redirect('saling_bagi:index')

    if request.method == 'POST':
        form = JanjiTemuForm(
            request.POST,
            makanan=makanan                            # dikirim supaya form bisa validasi terhadap batas konsumsi
        )

        if form.is_valid():
            try:
                with transaction.atomic():             # SEMUA di dalam blok ini berhasil, atau SEMUA dibatalkan (rollback)
                    makanan_terkunci = Makanan.objects.select_for_update().get(
                        id=makanan.id                  # kunci baris makanan; request lain harus antre
                    )                                  # (catatan: SQLite mengabaikan lock ini, Postgres/MySQL memakainya)

                    if not makanan_terkunci.is_available:   # cek ULANG di dalam lock, status bisa berubah sejak cek awal
                        raise ValueError(                   # raise di dalam atomic -> memicu rollback
                            'Makanan sudah dipesan orang lain.'
                        )

                    if makanan_terkunci.batas_layak_konsumsi <= timezone.now():
                        raise ValueError(
                            'Makanan sudah melewati batas konsumsi.'
                        )

                    janji = form.save(commit=False)    # objek JanjiTemu belum disimpan
                    janji.makanan = makanan_terkunci   # isi relasi makanan
                    janji.pengambil = request.user     # isi pengambil = user yang login
                    janji.save()                       # INSERT; di sini UniqueConstraint bisa melempar IntegrityError

                    makanan_terkunci.is_available = False   # kunci makanan supaya tidak bisa diajukan orang lain
                    makanan_terkunci.save(
                        update_fields=['is_available']
                    )

                messages.success(
                    request,
                    'Permintaan janji temu berhasil dikirim! '
                    'Tunggu persetujuan pemberi makanan.'
                )

                return redirect('saling_bagi:janji_temu')

            except (IntegrityError, ValueError):       # ditangkap DI LUAR atomic (setelah rollback)
                messages.error(                        # IntegrityError = constraint DB; ValueError = cek manual kita
                    request,
                    'Makanan sudah dipesan atau tidak lagi tersedia.'
                )
                return redirect('saling_bagi:index')

    else:                                              # GET
        form = JanjiTemuForm(makanan=makanan)

    return render(
        request,
        'saling_bagi/ajukan_janji.html',
        {
            'makanan': makanan,
            'form': form,
        }
    )


# ------------------------------------------------------------
# 4. HALAMAN JANJI TEMU (dua peran dalam satu halaman)
# ------------------------------------------------------------
@login_required
def janji_temu(request):
    janji_dibuat = JanjiTemu.objects.filter(           # janji yang SAYA ajukan (saya = pengambil)
        pengambil=request.user
    ).select_related(
        'makanan',
        'makanan__pemberi'                             # '__' menelusuri relasi: janji -> makanan -> pemberi
    )

    janji_diterima = JanjiTemu.objects.filter(         # janji yang masuk ke makanan SAYA (saya = pemberi)
        makanan__pemberi=request.user                  # filter lewat relasi: makanan.pemberi == saya
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


# ------------------------------------------------------------
# 5. SETUJUI / TOLAK JANJI (pemberi)
# ------------------------------------------------------------
@login_required
@require_POST                                          # GET -> 405. Aksi yang mengubah data tidak boleh lewat link biasa
def keputusan_janji(request, id):
    with transaction.atomic():
        janji = get_object_or_404(
            JanjiTemu.objects.select_for_update(),     # kunci baris janji, cegah dua klik bersamaan
            id=id
        )

        if janji.makanan.pemberi != request.user:      # OTORISASI: hanya pemilik makanan yang boleh memutuskan
            messages.error(
                request,
                'Kamu tidak memiliki izin untuk mengubah janji temu ini.'
            )
            return redirect('saling_bagi:janji_temu')

        if janji.status != 'PENDING':                  # sudah diproses, jangan diproses dua kali
            messages.warning(
                request,
                'Janji temu ini sudah diproses.'
            )
            return redirect('saling_bagi:janji_temu')

        keputusan = request.POST.get('keputusan')      # nilai dari <input type="hidden" name="keputusan">

        if keputusan == 'approve':
            if janji.makanan.batas_layak_konsumsi <= timezone.now():   # makanan keburu kedaluwarsa
                janji.status = 'REJECTED'              # otomatis ditolak
                janji.save(update_fields=['status', 'updated_at'])   # updated_at harus disebut manual kalau pakai update_fields

                makanan = janji.makanan
                makanan.is_available = False           # kedaluwarsa, tidak tersedia lagi
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

            makanan.is_available = (                   # tersedia lagi HANYA jika belum kedaluwarsa
                makanan.batas_layak_konsumsi > timezone.now()
            )

            makanan.save(update_fields=['is_available'])

            messages.success(
                request,
                'Permintaan janji temu ditolak. '
                'Makanan kembali tersedia jika masih layak konsumsi.'
            )

        else:                                          # nilai keputusan diutak-atik / tidak dikenal
            messages.error(
                request,
                'Pilihan keputusan tidak valid.'
            )

    return redirect('saling_bagi:janji_temu')


# ------------------------------------------------------------
# 6. TANDAI SELESAI (pemberi)
# ------------------------------------------------------------
@login_required
@require_POST
def selesaikan_janji(request, id):
    janji = get_object_or_404(
        JanjiTemu.objects.select_related('makanan'),   # ambil makanan sekalian (dipakai cek pemberi)
        id=id
    )

    if janji.makanan.pemberi != request.user:          # hanya pemberi
        messages.error(
            request,
            'Hanya pemberi makanan yang dapat menyelesaikan janji temu.'
        )

    elif janji.status != 'APPROVED':                   # hanya dari status APPROVED
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

    return redirect('saling_bagi:janji_temu')          # semua cabang berakhir di sini (pesan tampil via messages)