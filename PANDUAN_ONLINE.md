# Panduan online gratis: Render + Neon + Cloudinary

Render hanya menjalankan kode. Database ada di Neon dan foto di Cloudinary, jadi data tidak hilang saat Render restart atau deploy ulang.

## 1. Buat database di Neon
1. Daftar di neon.com, lalu buat project baru.
2. Salin **connection string** (diawali `postgresql://...`). Pastikan ada `sslmode=require` di ujungnya.

## 2. Buat akun Cloudinary
1. Daftar di cloudinary.com (paket Free, tanpa kartu kredit).
2. Buka Dashboard > API Keys, salin nilai **API Environment variable**, bentuknya `cloudinary://API_KEY:API_SECRET@NAMA_CLOUD`.

## 3. Isi variabel di Render
Service web SIPNU > Environment > tambahkan:

| Nama | Isi |
|---|---|
| `DATABASE_URL` | connection string Neon |
| `CLOUDINARY_URL` | `cloudinary://...` dari Cloudinary |
| `SECRET_KEY` | teks acak panjang (bebas, rahasia) |

Start Command di Render: `gunicorn app:app`

## 4. Kirim kode terbaru ke GitHub
```
git add .
git commit -m "Pakai Neon dan Cloudinary"
git push
```
Render akan deploy otomatis. Jangan pernah menaruh connection string atau kunci di dalam file kode.

## 5. Pindahkan data lama dari komputer Anda (sekali saja)
Jalankan di folder proyek (yang punya `instance/sipnu.db` dan `static/uploads`). Contoh PowerShell:
```
pip install -r requirements.txt
$env:DATABASE_URL="postgresql://...dari Neon..."
$env:CLOUDINARY_URL="cloudinary://...dari Cloudinary..."
flask --app app pindah-data
```
Perintah ini menyalin akun, profil, dan berita, lalu mengunggah foto lama ke Cloudinary. Aman dijalankan ulang: data yang sudah ada tidak digandakan.

Jika ingin mulai dari kosong: dengan dua variabel di atas terisi, jalankan `flask --app app buat-admin NAMA_PENGGUNA`.

## 6. Cek
Buka web Render. Berita lama muncul, lalu coba tambah berita baru dengan foto, dan deploy ulang untuk memastikan datanya tetap ada.

Catatan: web gratis di Render tertidur bila lama tidak dikunjungi, jadi buka pertama kali bisa lambat. Itu normal.
