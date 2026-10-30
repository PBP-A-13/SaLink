# SaLink

SaLink adalah platform Django untuk komunitas universitas yang ingin memanfaatkan kembali sumber daya secara lokal melalui jual-beli barang bekas, peminjaman, berbagi makanan berlebih, berbagi tebengan, dan halaman akun bersama.

Produk ini dirancang untuk alur kampus yang sederhana: pengguna dapat menjelajah tanpa login, login hanya ketika melakukan aksi yang mengubah data, dan bertemu di titik kampus yang mudah dikenali seperti Perpusat UI dan Stasiun UI.

## Area Produk

| Area | Tujuan | Alur utama |
| --- | --- | --- |
| Saling Beli | Marketplace barang bekas dan hibah gratis | Menjelajah, melihat detail, menawar (nego), memesan (COD), konfirmasi 2-arah, chat, dan mengelola listing |
| Saling Pinjam | Akses sementara terhadap barang yang dibutuhkan | Menjelajah, mengajukan, menyetujui, dan melacak pengembalian |
| Saling Bagi | Redistribusi makanan berlebih | Melihat makanan tersedia dan mengambil porsi |
| Saling Nebeng | Berbagi perjalanan di area kampus | Mencari rute, menawarkan tebengan, bergabung, dan mengelola booking |
| User Page | Identitas dan aksi akun bersama | Mendaftar, login, mengubah profil, dan kembali ke modul asal |

## Endpoint API Saling Beli

Modul `saling_beli` menyediakan REST / JSON API yang lengkap untuk integrasi client-side, mobile, atau pengujian otomatis:

### 1. Data Listing & Barang
- `GET /saling-beli/json/` atau `GET /saling-beli/json/all/`: Mengambil daftar seluruh barang dagangan dalam format JSON.
- `POST /saling-beli/create/`: Menambahkan listing barang baru (memerlukan autentikasi, payload JSON).
- `GET /saling-beli/<uuid:listing_id>/`: Mengambil detail informasi 1 barang tertentu.
- `PUT / PATCH /saling-beli/<uuid:listing_id>/update/`: Memperbarui data barang (hanya pemilik barang).
- `DELETE /saling-beli/<uuid:listing_id>/delete/`: Menghapus data barang (hanya pemilik barang).
- `POST /saling-beli/<uuid:listing_id>/upload-image/`: Mengunggah atau mengganti foto barang via multipart form data.

### 2. Transaksi & Penawaran Nego
- `POST /saling-beli/detail/<uuid:listing_id>/offer/`: Mengajukan penawaran harga (nego) terhadap barang.
- `POST /saling-beli/offer/<uuid:offer_id>/respond/`: Menyetujui (`accept`) atau menolak (`reject`) penawaran harga oleh penjual.
- `POST /saling-beli/detail/<uuid:listing_id>/order/`: Membuat pesanan langsung (*Buy Now*) dengan harga normal.
- `POST /saling-beli/order/<uuid:order_id>/update-stage/`: Memperbarui tahapan status transaksi / tracker COD 2-arah (`BUKTI_DIUNGGAH`, `DIKONFIRMASI`, `JANJI_TEMU_COD`, `SELESAI`, `BATAL`).

### 3. Komunikasi & Notifikasi
- `GET / POST /saling-beli/detail/<uuid:listing_id>/chats/`: Mengambil riwayat pesan atau mengirim pesan chat antar pembeli dan penjual.
- `GET /saling-beli/api/notifications/`: Mengambil daftar notifikasi milik pengguna yang sedang login.
- `GET /saling-beli/api/notifications/stream/`: Endpoint *long-polling* untuk streaming pembaruan notifikasi secara realtime.
- `POST /saling-beli/api/notifications/mark-read/`: Menandai seluruh notifikasi yang belum dibaca menjadi terbaca.

## Screenshot dan GIF

Screenshot dan GIF untuk rilis diletakkan di [`docs/media`](docs/media/README.md). Gunakan data seed yang sudah dianonimkan dan ukuran desktop/mobile yang tercantum di sana. Jangan pernah memasukkan kredensial, cookie sesi, atau percakapan pribadi ke dalam dokumentasi.

Arah visual produk juga tersedia di [file Figma SaLink](https://www.figma.com/design/mLX7a6qFC62AiaaPumui8N/SaLink).

## Menjalankan Secara Lokal

Persyaratan: Python 3.13+, Git, dan virtual environment.

PowerShell:

```powershell
py -3.13 -m venv env
.\env\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
python manage.py migrate
python manage.py runserver
```

Buka <http://127.0.0.1:8000/>.

Untuk environment yang sudah tersedia:

```powershell
.\env\Scripts\Activate.ps1
python manage.py check
python manage.py test
```

## Konfigurasi Environment

`SaLink.settings` tetap menjadi konfigurasi default yang kompatibel untuk development. Production menggunakan `SaLink.production_settings`:

```powershell
$env:DJANGO_SETTINGS_MODULE = "SaLink.production_settings"
$env:DJANGO_SECRET_KEY = "gunakan-secret-random-yang-panjang"
$env:DJANGO_ALLOWED_HOSTS = "domain-anda.example"
$env:DJANGO_CSRF_TRUSTED_ORIGINS = "https://domain-anda.example"
python manage.py check --deploy
```

Jangan commit `.env`, secret production, database, media upload, atau static files hasil generate. Lihat [`.env.example`](.env.example).

## Arsitektur

- Django 5.2 dengan template server-rendered dan namespace URL per aplikasi.
- SQLite menjadi database default lokal; gunakan database terkelola untuk production.
- WhiteNoise melayani static assets pada deployment sederhana.
- Development menggunakan cache in-process. Production menggunakan file-based cache Django secara default dan dapat dikonfigurasi melalui `DJANGO_CACHE_DIR`.
- Homepage publik dan daftar Saling Bagi memakai server-side cache berumur pendek. Aksi mutasi makanan menghapus cache publik terkait agar status ketersediaan tidak terlalu lama basi.
- Fitur peta eksternal bersifat opsional. Halaman publik tetap dapat digunakan ketika tile map atau API pihak ketiga sedang tidak tersedia; informasi lokasi penting tetap disimpan di data aplikasi.

## Standar Aksesibilitas dan Interaksi

UI bersama menyediakan skip navigation untuk keyboard, focus state yang terlihat, layout desktop/mobile responsif, dukungan `prefers-reduced-motion`, heading dan label semantik, serta autentikasi hanya pada aksi yang mengubah data.

Saat menambahkan komponen baru, pertahankan akses keyboard, kontras focus yang terbaca, label yang bermakna, dan fallback tanpa animasi.

## CI/CD

GitHub Actions berjalan pada push dan pull request melalui [`.github/workflows/ci.yml`](.github/workflows/ci.yml): memasang dependency, menjalankan Django check, mendeteksi migration drift pada modul yang dikelola, dan menjalankan test suite. Deployment tetap terpisah dan sebaiknya menjalankan migration, `collectstatic`, `check --deploy`, serta smoke test dengan environment production sebelum traffic dialihkan.

## Disclosure AI

AI digunakan sebagai asisten untuk eksplorasi, penyusunan kode, pembuatan test, dan dokumentasi. AI tidak diperlakukan sebagai sumber kebenaran atau pengganti maintainer.

Review manual tetap wajib karena AI dapat salah memahami batas kepemilikan modul, menghasilkan routing yang menunjuk template atau migration yang tidak ada, membocorkan data pada screenshot/log, menyebabkan data cache basi, atau melebih-lebihkan kualitas aksesibilitas dan keamanan production. Keamanan production juga bergantung pada infrastruktur, secret, konfigurasi database, HTTPS, backup, dan monitoring di luar sesi coding.

Keputusan yang harus dipelihara manusia meliputi batas modul, kebijakan autentikasi, TTL dan titik invalidation cache, default environment, perintah CI, dan dokumentasi akhir. Setiap perubahan berbantuan AI tetap harus melewati review, system check, test, dan smoke test browser manual.

## Tim

| Nama | NPM |
| --- | --- |
| KEIZORA JELITA WOHINGATI | 2506597510 |
| HADYASALHA ALINA ANINDYA | 2506620406 |
| MUHAMMAD HASBI ASSIDDIQ | 2506624360 |
| BALQIS RAIHANA | 2506625981 |
| BAGAS MAHENDRA SRIKASTA | 2506656551 |

## Tautan

- Deployment: <https://muhammad-hasbi52-salink.pws.cs.ui.ac.id/>
- Design: <https://www.figma.com/design/mLX7a6qFC62AiaaPumui8N/SaLink>

## AI Disclosure (Transparansi Penggunaan AI)

**Saling Bagi** 

* **Tujuan & Strategi Prompt:** 
  Memberikan *prompt* berupa potongan kode (`urls.py`, `settings.py`) dan *log error* mentah dari terminal. Tujuannya untuk mencari tahu kenapa gambar/media gagal dimuat di server PWS (berkaitan dengan `DEBUG=False`), mencari solusi bentrok Git (`non-fast-forward`), dan menanyakan sintaks dasar *template inheritance* Django untuk memasang *footer*.

* **Batasan & Kelemahan AI yang Ditemukan:**
  * **Kurang Paham Struktur Proyek:** AI sempat menyarankan untuk menaruh *routing* gambar di file `saling_bagi/urls.py`, padahal agar bisa jalan di PWS, *routing* itu wajib ditaruh di level root (`SaLink/urls.py`). 
  * **Tidak Tahu Konvensi Kelompok:** AI hanya memberikan contoh sintaks umum (seperti `{% extends 'base.html' %}`). AI tidak tahu kalau kelompok kami menggunakan konvensi penamaan khusus seperti `_footer.html`.
  * **Gagal Membaca State Lokal:** AI sempat menyarankan perbaikan kodingan saat web error `ERR_CONNECTION_REFUSED`, padahal masalah aslinya sesederhana *server* lokal (`localhost:8000`) belum dinyalakan lewat `runserver`.

* **Perbaikan Manual yang dilakukan:**
  * Menyadari instruksi *routing* AI salah sasaran, sehingga secara manual memindahkan dan menyesuaikan konfigurasi *routing* media tersebut ke *entry point* yang benar di `SaLink/urls.py`.
  * Saat merapikan riwayat Git, AI menyuruh langsung menggunakan `git revert`. Karena sedang mengedit file CSS secara lokal, eksekusi itu gagal. Harus inisiatif merangkai alur manual: mengamankan kodingan dengan `git stash`, melakukan *revert* dua kali, lalu mengembalikan CSS menggunakan `git stash pop` agar desain *front-end* tidak hilang.
  * Daripada menelan mentah-mentah kode dari AI, menginspeksi file HTML milik rekan sekelompok (fitur *Saling Tebeng*) untuk menyesuaikan tag pemanggilan `{% include "_footer.html" %}` agar desain *footer* selaras dengan UI aplikasi lainnya.
