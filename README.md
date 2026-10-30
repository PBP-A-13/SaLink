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

## Dokumentasi Endpoint & API Setiap Modul

Seluruh modul pada SaLink dilengkapi dengan endpoint yang mendukung pengujian otomatis, integrasi client-side, AJAX, maupun integrasi mobile REST:

---

### 1. Modul Saling Beli (`saling_beli`)
Prefix URL: `/saling-beli/`

#### A. Data Listing & Katalog (Web & JSON REST)
- `GET /saling-beli/`: Menampilkan halaman katalog belanja dengan fitur pencarian, filter kategori, sorting harga/waktu, riwayat terakhir dilihat (Session), dan barang tersimpan (Cookie).
- `GET /saling-beli/json/` atau `GET /saling-beli/json/all/`: Mengambil daftar seluruh barang dagangan aktif dalam format JSON.
- `POST /saling-beli/create/`: Menambahkan listing barang baru melalui REST API (autentikasi required, payload JSON).
- `GET /saling-beli/tambah/`: Halaman formulir HTML untuk menambah barang baru atau hibah gratis.
- `GET /saling-beli/detail/<uuid:listing_id>/`: Halaman detail informasi barang, riwayat nego, dan panel aksi transaksi.
- `GET /saling-beli/<uuid:listing_id>/`: Mengambil detail data barang dalam format JSON.
- `GET /saling-beli/edit/<uuid:listing_id>/` & `POST`: Halaman form edit barang milik pengguna yang sedang login.
- `PUT / PATCH /saling-beli/<uuid:listing_id>/update/`: REST API untuk memperbarui data barang milik penjual.
- `POST /saling-beli/hapus/<uuid:listing_id>/`: Menghapus data barang dari katalog (khusus pemilik barang).
- `DELETE /saling-beli/<uuid:listing_id>/delete/`: REST API untuk menghapus barang dari katalog.
- `POST /saling-beli/<uuid:listing_id>/upload-image/`: Mengunggah atau mengganti foto barang via multipart form data.

#### B. Transaksi, Nego Harga, & COD 2-Arah
- `POST /saling-beli/detail/<uuid:listing_id>/offer/`: Mengajukan penawaran harga (nego) terhadap barang.
- `POST /saling-beli/offer/<uuid:offer_id>/respond/`: Menyetujui (`accept`) atau menolak (`reject`) penawaran harga oleh penjual.
- `POST /saling-beli/detail/<uuid:listing_id>/order/`: Membuat pesanan langsung (*Buy Now*) dengan harga katalog normal.
- `POST /saling-beli/order/<uuid:order_id>/update-stage/`: Memperbarui tahapan status transaksi / tracker COD 2-arah (`BUKTI_DIUNGGAH`, `DIKONFIRMASI`, `JANJI_TEMU_COD`, `SELESAI`, `BATAL`).

#### C. Percakapan & Notifikasi Realtime
- `GET / POST /saling-beli/detail/<uuid:listing_id>/chats/`: Mengambil riwayat percakapan atau mengirim pesan baru per listing barang.
- `GET /saling-beli/api/notifications/`: Mengambil daftar notifikasi akun pengguna yang sedang login (JSON).
- `GET /saling-beli/api/notifications/stream/`: Endpoint *long-polling* untuk streaming pembaruan notifikasi transaksi/chat secara realtime.
- `POST /saling-beli/api/notifications/mark-read/`: Menandai seluruh notifikasi yang belum dibaca menjadi terbaca.

---

### 2. Modul Saling Pinjam (`saling_pinjam`)
Prefix URL: `/saling-pinjam/`

- `GET /saling-pinjam/`: Halaman utama peminjaman barang, kalender interaktif peminjaman bulan berjalan, filter pencarian kategori, dan ringkasan pinjaman aktif.
- `GET /saling-pinjam/create/`: Halaman formulir untuk mendaftarkan barang baru yang ingin dipinjamkan ke mahasiswa lain.
- `POST /saling-pinjam/create/`: Memproses penambahan data barang pinjaman baru (login required).
- `GET /saling-pinjam/<uuid:id>/`: Halaman detail barang yang dipinjamkan beserta spesifikasi dan lokasi pengambilan.
- `POST /saling-pinjam/<uuid:id>/request/`: Mengajukan permohonan pinjam atas suatu barang beserta durasi dan catatan peminjaman.
- `GET /saling-pinjam/my-borrows/`: Dashboard pelacakan pinjaman:
  1. Pengajuan yang diajukan pengguna (sebagai peminjam).
  2. Pengajuan yang masuk atas barang milik pengguna (sebagai pemilik).
  3. Daftar inventaris barang yang sedang dipinjamkan.
- `GET / POST /saling-pinjam/request/<uuid:request_id>/status/<str:new_status>/`: Aksi persetujuan status pinjaman oleh pemilik barang (`APPROVED`, `REJECTED`, `ONGOING`, `RETURNED`).

---

### 3. Modul Saling Bagi (`saling_bagi`)
Prefix URL: `/saling-bagi/`

- `GET /saling-bagi/`: Menampilkan etalase makanan berlebih yang masih layak konsumsi (belum kedaluwarsa) dari mahasiswa UI.
- `GET /saling-bagi/tambah/`: Halaman form untuk membagikan makanan berlebih beserta input foto, porsi, lokasi, dan batas konsumsi.
- `POST /saling-bagi/tambah/`: Menyimpan data makanan baru yang dibagikan ke platform.
- `GET /saling-bagi/ajukan/<int:id>/`: Form pengajuan janji temu pengambilan makanan.
- `POST /saling-bagi/ajukan/<int:id>/`: Memproses booking pengambilan makanan (mengunci status makanan secara atomik agar tidak bentrok).
- `GET /saling-bagi/janji-temu/`: Dashboard pelacakan status janji temu (daftar pengambilan saya & makanan yang saya bagikan).
- `POST /saling-bagi/janji-temu/<int:id>/keputusan/`: Menyetujui (`disetujui`) atau menolak (`ditolak`) janji temu pengambilan makanan oleh pihak pemberi.
- `POST /saling-bagi/janji-temu/<int:id>/selesai/`: Menandai serah terima makanan telah berhasil diselesaikan di titik temu.

---

### 4. Modul Saling Nebeng (`saling_tebeng`)
Prefix URL: `/saling-nebeng/` (alias: `/saling-tebeng/`, `/nebeng/`)

- `GET /saling-nebeng/`: Menampilkan daftar jadwal tebengan aktif, filter rute asal-tujuan kampus, dan ketersediaan kursi.
- `GET /saling-nebeng/nebeng/tawarkan/`: Halaman form untuk driver menawarkan jadwal tebengan motor/mobil.
- `POST /saling-nebeng/nebeng/tawarkan/`: Memproses publikasi jadwal tebengan baru beserta kuota penumpang dan kontak.
- `POST /saling-nebeng/nebeng/jadwal/<int:schedule_id>/gabung/`: Mengajukan bergabung tebengan oleh calon penumpang.
- `POST /saling-nebeng/nebeng/jadwal/<int:schedule_id>/batal/`: Membatalkan jadwal tebengan oleh driver.
- `GET /saling-nebeng/nebeng/saya/`: Dashboard perjalanan saya: mengelola status booking penumpang dan tawaran berkendara driver.
- `POST /saling-nebeng/nebeng/booking/<int:booking_id>/batal/`: Membatalkan keikutsertaan tebengan oleh penumpang.
- `GET /saling-nebeng/nebeng/pesan/`: Daftar percakapan aktif antar driver dan penumpang untuk koordinasi titik jemput.
- `GET /saling-nebeng/nebeng/jadwal/<int:schedule_id>/chat/`: Ruang percakapan per jadwal tebengan.
- `GET /saling-nebeng/nebeng/jadwal/<int:schedule_id>/chat/pesan/`: **REST JSON API** untuk mengambil seluruh riwayat chat perjalanan.
- `POST /saling-nebeng/nebeng/jadwal/<int:schedule_id>/chat/pesan/`: **REST JSON API** untuk mengirim pesan chat baru (payload JSON: `{"message": "..."}`).
- `POST /saling-nebeng/nebeng/jadwal/<int:schedule_id>/chat/gabung/`: Konfirmasi bergabung langsung dari ruang percakapan.

---

### 5. Modul User Page & Akun Bersama (`user_page`)
Prefix URL: `/akun/`

- `GET /akun/login/`: Halaman masuk (*login*) akun SaLink dengan dukungan parameter `next` untuk mengembalikan pengguna ke modul asalnya.
- `POST /akun/login/`: Memproses autentikasi kredensial pengguna.
- `GET /akun/register/`: Halaman pendaftaran mahasiswa baru.
- `POST /akun/register/`: Memproses pembuatan akun baru dan otomatis menginisialisasi profil pengguna.
- `POST /akun/logout/`: Mengakhiri sesi login pengguna.
- `GET /akun/profile/`: Halaman manajemen profil akun bersama (menampilkan username, email, nama lengkap, dan foto avatar).
- `POST /akun/profile/`: Memperbarui data pengguna, termasuk validasi keunikan username baru dan pengunggahan foto profil/avatar.
- `POST /akun/delete-account/`: Zona Bahaya untuk menghapus akun pengguna secara permanen dari sistem beserta seluruh data terkait.

---

### 6. Halaman Terpadu & Edukasi Transaksi (`main`)
Prefix URL: `/`

- `GET /`: Halaman Beranda utama (Hero banner SaLink, menu cepat 4 modul layanan, dan preview barang prelove).
- `GET /panduan-cod/`: Panduan keamanan transaksi, etika bertransaksi langsung, dan rekomendasi titik temu COD di area kampus UI.
- `GET /faq/`: Tanya jawab (FAQ) seputar platform dan syarat & ketentuan penggunaan layanan.

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

## Disclosure AI

AI digunakan sebagai asisten untuk eksplorasi, penyusunan kode, pembuatan test, dan dokumentasi. AI tidak diperlakukan sebagai sumber kebenaran atau pengganti maintainer.

Review manual tetap wajib karena AI dapat salah memahami batas kepemilikan modul, menghasilkan routing yang menunjuk template atau migration yang tidak ada, membocorkan data pada screenshot/log, menyebabkan data cache basi, atau melebih-lebihkan kualitas aksesibilitas dan keamanan production. Keamanan production juga bergantung pada infrastruktur, secret, konfigurasi database, HTTPS, backup, dan monitoring di luar sesi coding.

Keputusan yang harus dipelihara manusia meliputi batas modul, kebijakan autentikasi, TTL dan titik invalidation cache, default environment, perintah CI, dan dokumentasi akhir. Setiap perubahan berbantuan AI tetap harus melewati review, system check, test, dan smoke test browser manual.

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

**Saling Beli**

* **Tujuan & Strategi Prompt:** 
  Meminta panduan AI untuk merancang arsitektur alur transaksi COD 2-arah dengan 5 tahapan status verifikasi (`MENUNGGU_TRANSFER` hingga `SELESAI`), penanganan validasi penawaran harga nego (harga tawar harus < harga asli dan > 0), pembuatan data migration untuk seed data barang awal di server PWS, serta penyesuaian CSS navbar floating agar sticky dan tidak terdorong saat scroll.

* **Batasan & Kelemahan AI yang Ditemukan:**
  * **Mengganggu Test Suite Otomatis:** Saat menyusun file data migration seed barang, AI memasukkan data langsung ke database saat `python manage.py test` berjalan di GitHub Actions CI. Akibatnya, 4 unit test gagal karena database pengujian tidak bersih (*MultipleObjectsReturned*).
  * **Saran Fitur Berlebihan (Over-engineering):** Ketika ditanya mengenai letak penyimpanan fitur tombol "Simpan", AI sempat berhalusinasi membuat model database baru (`SavedItem`) dan mengubah puluhan baris kode, padahal arsitektur awal tugas kelompok cukup memanfaatkan Cookie browser (`salink_saved_items`) dan Session.
  * **Masalah Caching Aset CSS:** Solusi CSS navbar sticky dari AI sempat tidak mempan di browser pengguna karena browser meng-cache stylesheet lama tanpa mendeteksi query version string yang baru.

* **Perbaikan Manual yang Dilakukan:**
  * Menambahkan pengecekan manual kondisi test (`if 'test' in sys.argv or 'test_' in db_name`) pada fungsi migrasi `seed_saling_beli_data` agar proses seeding dilewati saat CI testing berjalan dan hanya dieksekusi saat deploy migrasi normal.
  * Membatalkan penambahan model baru, lalu secara manual membaca cookie `salink_saved_items` di `views.py` dan menampilkannya sebagai section kartu di katalog Saling Beli.
  * Memasang inline style sticky pada `_navbar.html` dan menambahkan parameter versi cache-busting (`?v=...`) agar navbar sticky aktif seketika di seluruh halaman Saling Beli tanpa terhambat cache browser.


**Saling Pinjam**

* **Tujuan & Strategi Prompt:** 
  Menggunakan prompt AI untuk menanyakan implementasi pustaka bawaan Python `calendar.Calendar` guna merender grid tanggal bulan berjalan di halaman katalog pinjam, menyusun state machine status barang pinjaman (`AVAILABLE` -> `BORROWED` -> `RETURNED`), serta merancang form validasi tanggal pinjam dan tanggal kembali.

* **Batasan & Kelemahan AI yang Ditemukan:**
  * **Kelalaian Validasi Logika Bisnis:** AI tidak memasukkan proteksi validasi terhadap pemilik barang, sehingga seorang pengguna sempat bisa meminjam barang yang ia daftarkan sendiri.
  * **Off-by-One Hari Kalender:** Kode kalender yang diberikan AI menggunakan konfigurasi hari pertama default (Senin), yang membuat tanggal bergeser tidak sesuai dengan kalender standar kampus yang dimulai dari hari Minggu.
  * **Template Form Tidak Responsif:** Markup HTML yang digenerate AI memakai layout tabel kaku yang rusak ketika diakses dari layar smartphone.

* **Perbaikan Manual yang Dilakukan:**
  * Menuliskan validasi pertahanan diri manual di `views.py`: `if item.owner == request.user` untuk mencegah peminjaman barang milik sendiri dengan pesan peringatan yang ramah.
  * Mengonfigurasi parameter `firstweekday=6` (Minggu) pada fungsi `build_calendar` agar susunan tanggal hari libur dan hari kerja di kalender pas dan akurat.
  * Merombak styling tabel menjadi grid berbasis kartu CSS yang fleksibel agar kalender dan inventaris dashboard `my_borrows` nyaman dilihat di semua ukuran layar.


**Saling Nebeng**

* **Tujuan & Strategi Prompt:** 
  Memberikan prompt untuk menyusun sistem pencarian tebengan berdasarkan lokasi asal dan tujuan kampus, mekanisme pemotongan kuota kursi penumpang otomatis saat booking dikonfirmasi, serta pembuatan REST JSON API untuk percakapan chat instan antara driver dan calon penumpang.

* **Batasan & Kelemahan AI yang Ditemukan:**
  * **Pemberian URL yang Tidak Konsisten:** AI sempat menyarankan rute URL `/saling-tebeng/` padahal kesepakatan URL tim adalah `/saling-nebeng/`, memicu inkonsistensi tautan di navbar.
  * **Potensi Race Condition Kuota Kursi:** AI tidak menerapkan penguncian database atau validasi kapasitas sisa saat banyak penumpang mengajukan booking bersamaan, yang berisiko menyebabkan *overcapacity* kendaraan.
  * **Payload API Kurang Sanitasi:** Endpoint pesan chat yang dibuat AI sempat menerima string kosong dan tidak membatasi panjang teks, membuka celah error basis data.

* **Perbaikan Manual yang Dilakukan:**
  * Menambahkan validasi kapasitas sisa kursi secara eksplisit sebelum status booking dialihkan menjadi diterima.
  * Menambahkan sanitasi ketat pada endpoint chat (`message.strip()`, validasi batas 2.000 karakter, dan pengecekan tipe JSON) serta membatasi akses thread chat hanya kepada pihak driver dan penumpang yang terlibat.
  * Mendaftarkan konfigurasi `RedirectView` di root `SaLink/urls.py` untuk mengarahkan rute lama `/saling-tebeng/` dan `/nebeng/` ke `/saling-nebeng/` secara transparan.


**User Page & Akun Bersama**

* **Tujuan & Strategi Prompt:** 
  Meminta panduan AI mengenai implementasi Django signals (`post_save`) untuk otomatis mengaitkan objek model `UserProfile` saat `User` berhasil terdaftar, menyusun form profil kustom dengan upload foto avatar, serta menangani parameter `?next=` pada halaman login agar pengguna kembali ke modul awal mereka setelah masuk.

* **Batasan & Kelemahan AI yang Ditemukan:**
  * **Error Validasi Username Unik:** AI memberikan kode validasi `clean_username` yang mengecek duplikasi ke seluruh database tanpa mengecualikan ID pengguna yang sedang mengedit profilnya sendiri, sehingga pengguna tidak bisa menyimpan perubahan bio tanpa mengganti username.
  * **Lupa Atribut Form Upload:** Template profil yang disarankan AI tidak menyertakan atribut `enctype="multipart/form-data"`, sehingga foto avatar yang diunggah pengguna tidak terkirim ke server (`request.FILES` kosong).
  * **Celah Keamanan Penghapusan Akun:** AI menyarankan endpoint delete account melalui method HTTP `GET` biasa, yang rawan memicu penghapusan akun tidak sengaja melalui crawling browser atau tautan prefetch.

* **Perbaikan Manual yang Dilakukan:**
  * Memperbaiki logika form validation dengan `.exclude(pk=self.instance.pk)` agar username yang tidak diubah tetap lolos validasi tanpa pesan bentrok.
  * Menambahkan atribut `enctype="multipart/form-data"` pada tag form di `profile.html` dan menghubungkannya dengan `request.FILES` di view `profile()`.
  * Memperketat endpoint `delete-account` agar hanya menerima method `POST` dengan verifikasi token CSRF dan dialog peringatan konfirmasi ganda di bagian Zona Bahaya.
