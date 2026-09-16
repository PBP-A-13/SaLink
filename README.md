# SaLink — Student Sustainability App

## Deskripsi Aplikasi
SaLink adalah platform web berbasis Django yang mempertemukan mahasiswa untuk saling berbagi dan memanfaatkan kembali sumber daya lewat lima layanan: Saling Beli (marketplace barang bekas), Saling Pinjam (peminjaman barang), Saling Bagi (berbagi makanan berlebih), Saling Tebeng (ride-sharing), dan User Page (profil, reputasi, serta pencapaian sustainability pengguna).

Aplikasi ini menjawab tekanan hidup sehari-hari yang khas dialami mahasiswa: barang kos yang menumpuk tanpa saluran jual yang mudah, ketergantungan pada transportasi kampus yang tidak efisien, kebutuhan membeli barang sekali pakai yang mubazir, ongkir mahal untuk transaksi barang bekas sesama warga kampus, serta makanan sisa acara kepanitiaan/seminar yang berpotensi terbuang. Di sisi lain, mahasiswa juga menghadapi kekhawatiran keamanan, baik saat bertransaksi dengan orang asing maupun saat menebeng dengan yang belum dikenal.

SaLink menjawab pain tersebut lewat interaksi hyper-local antar mahasiswa terverifikasi SSO UI/KTM: transaksi COD tanpa ongkir di titik-titik populer kampus (Perpusat, Stasiun UI, Kantin Fakultas), akses tanpa perlu membeli lewat opsi pinjam, dan sistem reputasi pengguna yang mengurangi risiko penipuan maupun kecanggungan interaksi.

**Manfaat bagi masyarakat (khususnya komunitas mahasiswa):**
- **Efisiensi biaya hidup** — harga barang bekas & makanan jauh di bawah pasar, akses pinjam tanpa beli, tebengan patungan
- **Kemudahan hyper-local** — solusi satu pintu tanpa perlu bergabung ke banyak grup chat terpisah, transaksi tanpa ongkir
- **Dampak lingkungan terukur** — reduksi food waste, barang tak terpakai, dan emisi karbon yang bisa dilihat lewat metrik di profil pengguna
- **Koneksi sosial kampus** — memperluas relasi lintas jurusan/angkatan lewat budaya saling bantu

## Anggota Kelompok
| Nama | NPM |
|---|---|
| KEIZORA JELITA WOHINGATI | 2506597510 |
| HADYASALHA ALINA ANINDYA | 2506620406 |
| MUHAMMAD HASBI ASSIDDIQ | 2506624360 |
| BALQIS RAIHANA | 2506625981 |
| BAGAS MAHENDRA SRIKASTA | 2506656551 |

## Daftar Modul & Pembagian Kerja
| Modul | Deskripsi | Penanggung Jawab |
|---|---|---|
| Saling Beli (Marketplace Secondhand) | CRUD listing barang bekas mahasiswa (jual/kasih) — furnitur, elektronik, dsb — dengan kategori, kondisi barang, dan filter harga, memungkinkan barang kos yang menumpuk tetap punya nilai guna | Balqis |
| Saling Pinjam | CRUD request pinjam-meminjam barang antar mahasiswa (jas, koper, alat elektronik) beserta status dan jadwal pengembalian, sehingga tidak perlu membeli barang yang hanya dipakai 1-2 kali | Bagas |
| Saling Bagi (Makanan) | CRUD listing makanan berlebih dari acara kepanitiaan/seminar yang bisa diklaim mahasiswa lain sebelum terbuang, dengan filter lokasi dan waktu | Hasbi |
| Saling Tebeng | CRUD posting & request tebengan antar mahasiswa berdasarkan rute dan jadwal, terintegrasi OpenStreetMap untuk menekan ketergantungan pada antrean Bikun dan ojol mahal | Hadya |
| User Page | CRUD profil pengguna (bio, fakultas, foto), rating/review antar pengguna pasca-transaksi, dan badge/achievement sustainability (estimasi reduksi emisi CO2 & food waste) sebagai dasar kepercayaan lintas modul | Keizora |

## Sumber Public API
**OpenStreetMap (Overpass API)** — digunakan untuk menampilkan lokasi terkait (misalnya titik pengambilan barang/makanan, lokasi drop-point) berdasarkan data peta nyata.

Dokumentasi: https://wiki.openstreetmap.org/wiki/Overpass_API

## Jenis/Peran Pengguna
1. **Pemberi/Penjual** — memposting barang untuk dijual/dikasih (Saling Beli), menawarkan barang untuk dipinjamkan (Saling Pinjam), membagikan makanan berlebih (Saling Bagi), atau membuka tebengan (Saling Tebeng).
2. **Penerima/Pencari** — mencari dan membeli/mengambil barang bekas (Saling Beli), meminjam barang yang dibutuhkan sementara (Saling Pinjam), mengklaim makanan berlebih (Saling Bagi), atau memesan tebengan yang tersedia (Saling Tebeng)

## Tautan Deployment
🔗 *Akan diisi setelah deploy ke PWS — Checkpoint 2*

## Tautan Desain Figma
🔗 *https://www.figma.com/design/mLX7a6qFC62AiaaPumui8N/SaLink?node-id=0-1&t=JJDhM32RmaUpT8tI-1*
