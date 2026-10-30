# Deploy otomatis ke PWS

Dokumen ini menjelaskan cara kerja CD `Deploy to PWS` dan cara menyiapkannya.

## Alur

```
push / merge ke main
        │
        ▼
SaLink CI  ── gagal ──►  deploy tidak dijalankan
        │ sukses
        ▼
Deploy to PWS  ──►  git push ke repo PWS  ──►  PWS build & restart otomatis
```

Workflow CD tidak menjalankan tes ulang. Ia menunggu workflow **SaLink CI** selesai
dengan kesimpulan `success` pada branch `main`, lalu mendorong commit yang sama ke PWS.

## Prasyarat

1. Project PWS sudah dibuat dan statusnya **Running**.
2. Kredensial yang dipakai adalah **akun pemilik project PWS tersebut**. Jangan memakai
   akun pribadi orang lain hanya karena project-nya dipakai bersama.
3. URL Git PWS berbentuk:

   ```
   https://pws.cs.ui.ac.id/<username-pws>/<nama-app>
   ```

## Konfigurasi di GitHub

Buka **Settings → Secrets and variables → Actions**.

### Secrets

| Nama | Isi |
|---|---|
| `PWS_USERNAME` | username PWS pemilik project, contoh `muhammad.hasbi52` |
| `PWS_PASSWORD` | password PWS / Git password dari dashboard PWS |
| `PWS_TOKEN` | alternatif: dipakai bila `PWS_PASSWORD` tidak diisi |

### Variables

| Nama | Isi |
|---|---|
| `PWS_REPO_URL` | opsional. Default: `https://pws.cs.ui.ac.id/muhammad.hasbi52/salink` |
| `PWS_BRANCH` | opsional, default `main` |

Hanya satu workflow deploy yang aktif: `.github/workflows/deploy-pws.yml`.
Workflow lama `deploy.yml` dihapus agar satu push tidak menghasilkan dua status deploy.

Variable dan secret hanya perlu diisi sekali oleh admin repositori.

## Environment variable di PWS

Isi lewat tab **Environs** pada project PWS:

```env
DJANGO_SETTINGS_MODULE=SaLink.production_settings
DJANGO_SECRET_KEY=<string-acak-panjang>
DJANGO_ALLOWED_HOSTS=<domain-pws-anda>
DJANGO_CSRF_TRUSTED_ORIGINS=https://<domain-pws-anda>
```

`production_settings.py` memaksa `DEBUG=False`, jadi `DJANGO_DEBUG` tidak wajib.

## Setelah deploy pertama

Build PWS tidak otomatis menjalankan migrasi. Buka tab **Terminal** project PWS:

```bash
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser
```

Lakukan `migrate` lagi setiap kali ada migrasi baru yang ikut ter-deploy.

## Menjalankan manual

**Actions → Deploy to PWS → Run workflow**, lalu pilih ref (default `main`).
Berguna untuk deploy ulang tanpa commit baru, misalnya setelah mengubah environment
variable di PWS.

## Troubleshooting

| Gejala | Penyebab umum |
|---|---|
| `401` / diminta kredensial berulang | `PWS_USERNAME`/`PWS_PASSWORD` salah, atau URL memakai `http://` |
| `403` | Akun tersebut bukan pemilik/member project di `PWS_REPO_URL` |
| `src refspec ... does not match` | `PWS_BRANCH` tidak cocok dengan branch yang ada di PWS |
| Build PWS gagal | Cek `Procfile` (saat ini kosong), `requirements.txt`, dan log build |
| Deploy tidak pernah jalan | Nama workflow CI bukan `SaLink CI`, atau CI tidak sukses di `main` |

## Catatan keamanan

- Jangan menaruh `PWS_PASSWORD` atau `DJANGO_SECRET_KEY` di repository, README, atau chat.
- Gunakan akun/project PWS khusus untuk deployment bila memungkinkan.
- Workflow mendorong branch deploy secara fast-forward. Jika ditolak (misalnya branch PWS
  punya commit yang tidak ada di `main`), workflow mencoba **force push** agar isi branch
  deploy kembali sama dengan `main`. Karena itu, jangan melakukan push manual ke branch
  tersebut — perubahan manual bisa tertimpa pada deploy berikutnya.
- `SECRET_KEY` Django berbeda dari password PWS. Jangan pernah menukar keduanya.
