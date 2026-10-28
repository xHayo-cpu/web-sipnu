<<<<<<< HEAD
# SIPNU – Sistem Informasi Pelajar Nahdlatul Ulama

Website berita + akun pengguna. Ada dua jenis akun:

| Peran | Cara mendapatkan | Bisa apa |
|---|---|---|
| **Anggota** | Mendaftar sendiri di tab **Masuk → Daftar** | Login, melihat Akun Saya, ganti kata sandi |
| **Admin** | Dibuat lewat terminal (lihat langkah 2) | Semua hak anggota + tab **Kelola Berita** (tambah/ubah/hapus berita dan foto) |

## 1. Persiapan (sekali saja)

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # macOS / Linux
pip install -r requirements.txt
```

Di VS Code: `Ctrl+Shift+P` → **Python: Select Interpreter** → pilih `.venv`.

## 2. Buat akun admin pertama

```bash
flask --app app buat-admin NAMA_PENGGUNA
```

Anda akan diminta mengisi nama lengkap, email, dan kata sandi (minimal 8 karakter).

Perintah lain yang berguna:

```bash
flask --app app jadikan-admin NAMA_PENGGUNA   # naikkan anggota menjadi admin
flask --app app daftar-akun                   # lihat semua akun (tanpa kata sandi)
flask --app app contoh-data                   # isi berita contoh (opsional)
```

> Sebelumnya sudah punya database dengan akun admin lama? Cukup jalankan aplikasi:
> akun dari tabel `admin` lama otomatis disalin ke tabel `pengguna`.

## 3. Jalankan

```bash
python app.py
```

Buka http://127.0.0.1:5000

## 4. Di mana data login disimpan?

Semua akun ada di **satu tabel `pengguna`** pada database SQLite
`instance/sipnu.db`:

| Kolom | Isi |
|---|---|
| `id` | nomor akun |
| `nama_lengkap` | nama yang ditampilkan |
| `username` | nama pengguna (unik, huruf kecil) |
| `email` | email (unik, huruf kecil) |
| `password_hash` | **hasil hash** kata sandi, bukan kata sandi asli |
| `peran` | `anggota` atau `admin` |
| `dibuat` | waktu pendaftaran |

Cara kerjanya:

1. **Daftar:** kata sandi diubah menjadi hash dengan `generate_password_hash()`
   (satu arah, sudah memakai salt acak), lalu hash itu yang disimpan.
2. **Masuk:** kata sandi yang diketik dibandingkan dengan hash memakai
   `check_password_hash()`. Kata sandi asli tidak pernah disimpan dan tidak bisa dibaca kembali.
3. **Sesi:** setelah berhasil masuk, cookie hanya berisi **ID akun** (ditandatangani dengan
   `SECRET_KEY`), bukan kata sandi. Peran dibaca ulang dari database di setiap
   permintaan, sehingga perubahan peran langsung berlaku.

Yang **tidak boleh** dilakukan: menyimpan kata sandi apa adanya, mengirim kata sandi
lewat alamat URL, atau membagikan file `instance/sipnu.db` dan `SECRET_KEY`.

## 5. Struktur proyek

```
sipnu/
├── app.py              rute, login/daftar, unggah foto, perintah terminal
├── models.py           tabel: Pengguna, Berita
├── requirements.txt
├── instance/sipnu.db   database (dibuat otomatis)
├── templates/
│   ├── base.html       kerangka: header, teks berjalan, sidebar
│   ├── masuk.html      halaman Masuk / Daftar
│   ├── akun.html       Akun Saya + ganti kata sandi
│   ├── beranda.html, berita.html
│   ├── admin.html, form_berita.html
│   └── profil / susunan / foto / pendaftaran .html
└── static/
    ├── css/style.css
    ├── js/app.js
    └── uploads/        foto berita yang diunggah
```

## 6. Pengamanan yang sudah ada

- Kata sandi di-hash; pesan gagal login sengaja umum (tidak membocorkan akun mana yang ada).
- Pembatas percobaan: 5 kali salah → dikunci 10 menit; pendaftaran dibatasi 10 per jam per perangkat.
- Semua formulir POST memakai token CSRF; keluar (logout) juga lewat POST.
- Halaman admin dan aksi tambah/ubah/hapus hanya untuk peran `admin`; peran tidak bisa
  dipaksa lewat formulir pendaftaran.
- Foto: hanya JPG/PNG/WEBP, isi diperiksa benar-benar gambar, maks. 5 MB, nama diganti acak.
- Teks dari pengguna di-escape otomatis (aman dari sisipan HTML/script).

## 7. Sebelum dipasang online

1. Atur `SECRET_KEY` lewat variabel lingkungan:
   ```bash
   python -c "import secrets; print(secrets.token_hex(32))"
   ```
2. Hapus `debug=True`, jalankan dengan `gunicorn app:app`.
3. Pakai HTTPS, lalu aktifkan `SESSION_COOKIE_SECURE=True` di `app.py`.
4. Pastikan hosting menyimpan `instance/sipnu.db` dan `static/uploads/` secara permanen;
   cadangkan keduanya secara berkala.
5. Pembatas percobaan disimpan di memori satu server. Untuk beberapa server, ganti dengan
   Flask-Limiter + Redis. Untuk pengunjung banyak, ganti SQLite dengan PostgreSQL
   (cukup ubah `DATABASE_URL`).
6. Belum ada fitur "lupa kata sandi" dan verifikasi email (butuh layanan pengirim email).
   Sementara itu, admin bisa mengatur ulang kata sandi lewat terminal:
   `flask --app app buat-admin NAMA_PENGGUNA`.
=======
# web-sipnu
>>>>>>> 7ba34b3b84201106777f61bd34913d5ae363a74c
