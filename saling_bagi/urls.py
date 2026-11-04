# ============================================================
# saling_bagi/urls.py  ->  ROUTING: URL mana dipanggil ke view mana.
# Dipasang di SaLink/urls.py lewat include('saling_bagi.urls') di bawah prefix 'saling-bagi/'.
# Jadi URL lengkapnya: /saling-bagi/ + path di bawah ini.
# ============================================================

from django.urls import path
from . import views                                    # import views.py di app yang sama
from user_page.views import module_login               # view login dari app teman (user_page)


app_name = 'saling_bagi'                               # namespace -> dipakai di template: {% url 'saling_bagi:index' %}

urlpatterns = [
    path('login/', module_login, name='login'),        # /saling-bagi/login/  -> memakai view login milik user_page

    path('', views.index, name='index'),               # /saling-bagi/        -> daftar makanan

    path('tambah/', views.tambah_makanan, name='tambah_makanan'),   # /saling-bagi/tambah/

    path('ajukan/<int:id>/', views.ajukan_janji, name='ajukan_janji'),
    # <int:id> = path converter: hanya angka, dikirim ke view sebagai argumen id
    # contoh: /saling-bagi/ajukan/5/  -> ajukan_janji(request, id=5)

    path('janji-temu/', views.janji_temu, name='janji_temu'),      # halaman dua peran (pemberi & pengambil)

    path(
        'janji-temu/<int:id>/keputusan/',              # tombol Setujui / Tolak (POST)
        views.keputusan_janji,
        name='keputusan_janji'                         # name dipakai di {% url 'saling_bagi:keputusan_janji' janji.id %}
    ),

    path(
        'janji-temu/<int:id>/selesai/',                # tombol Tandai Selesai (POST)
        views.selesaikan_janji,
        name='selesaikan_janji'
    ),
]