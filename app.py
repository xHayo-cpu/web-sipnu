"""
SIPNU - Sistem Informasi Pelajar Nahdlatul Ulama

Cara menjalankan (lihat README.md untuk langkah lengkap):
    pip install -r requirements.txt
    flask --app app buat-admin NAMA_PENGGUNA
    python app.py
Lalu buka http://127.0.0.1:5000
"""

import os
import re
import time
import uuid
from collections import defaultdict
from datetime import datetime, timedelta
from functools import wraps
from urllib.parse import quote_plus

import click
from flask import (Flask, flash, g, redirect, render_template, request,
                   session, url_for)
from flask_wtf.csrf import CSRFError, CSRFProtect
from PIL import Image
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from models import DAFTAR_KATEGORI, Berita, Pengguna, ProfilKonten, db

app = Flask(__name__)


def _url_database():
    """Ambil alamat database dari variabel DATABASE_URL (mis. Neon). Bawaan: SQLite lokal.
    Alamat Postgres tanpa nama driver dipaksa memakai driver psycopg (v3)."""
    alamat = os.environ.get("DATABASE_URL", "sqlite:///sipnu.db").strip().strip("\"'")
    for awalan in ("postgres://", "postgresql://"):
        if alamat.startswith(awalan):
            return "postgresql+psycopg://" + alamat[len(awalan):]
    return alamat


# Foto disimpan di Cloudinary bila variabel CLOUDINARY_URL diisi (wajib saat online,
# karena penyimpanan file di Render gratis bersifat sementara). Tanpa itu: simpan lokal.
PAKAI_CLOUDINARY = bool(os.environ.get("CLOUDINARY_URL"))
if PAKAI_CLOUDINARY:
    import cloudinary
    import cloudinary.uploader

# ---------------------------------------------------------------------------
# Konfigurasi
# ---------------------------------------------------------------------------
app.config.update(
    # Saat online, WAJIB diganti lewat variabel lingkungan SECRET_KEY.
    SECRET_KEY=os.environ.get("SECRET_KEY", "kunci-pengembangan-ganti-saat-online"),
    SQLALCHEMY_DATABASE_URI=_url_database(),
    SQLALCHEMY_ENGINE_OPTIONS={"pool_pre_ping": True, "pool_recycle": 280},   # aman saat database gratis "tidur"
    MAX_CONTENT_LENGTH=5 * 1024 * 1024,          # batas unggahan 5 MB
    UPLOAD_FOLDER=os.path.join(app.static_folder, "uploads"),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    PERMANENT_SESSION_LIFETIME=timedelta(days=14),   # lama login jika "Ingat saya" dicentang
    # SESSION_COOKIE_SECURE=True,                # aktifkan jika sudah memakai HTTPS
)
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

db.init_app(app)
CSRFProtect(app)          # semua formulir POST wajib membawa csrf_token



def migrasi_admin_lama():
    """Salin akun dari tabel `admin` versi lama (jika ada) ke tabel `pengguna`."""
    if not inspect(db.engine).has_table("admin"):
        return
    baris = db.session.execute(text("SELECT username, password_hash FROM admin")).all()
    for username, sandi_hash in baris:
        if not Pengguna.query.filter_by(username=username).first():
            db.session.add(Pengguna(
                nama_lengkap=username.title(), username=username,
                email=f"{username}@admin.lokal", password_hash=sandi_hash, peran="admin"))
    db.session.commit()


with app.app_context():
    db.create_all()       # membuat tabel bila belum ada
    migrasi_admin_lama()

EKSTENSI_BOLEH = {"jpg", "jpeg", "png", "webp"}

LOKASI_KANTOR = "Jl. Semeru, Banjardowo, Kec. Jombang Kode Pos 61419"

# (endpoint, label, isi svg ikon)
MENU = [
    ("beranda", "Beranda",
     '<path d="M3 11.5 12 4l9 7.5"/><path d="M5 10v10h5v-6h4v6h5V10"/>'),
    ("profil", "Profil",
     '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20c0-3.6 2.9-6 6.5-6s6.5 2.4 6.5 6"/>'
     '<path d="M16 5a3.5 3.5 0 0 1 0 6.5"/><path d="M18 14.3c2 .7 3.5 2.5 3.5 5.2"/>'),
    ("susunan", "Susunan Pengurus",
     '<rect x="9" y="3" width="6" height="5" rx="1"/><rect x="3" y="16" width="6" height="5" rx="1"/>'
     '<rect x="15" y="16" width="6" height="5" rx="1"/><path d="M12 8v4M6 16v-4h12v4"/>'),
    ("foto", "Foto Kegiatan",
     '<rect x="3" y="4" width="18" height="16" rx="2.5"/><circle cx="9" cy="10" r="1.8"/>'
     '<path d="m21 16-5-5L6 20"/>'),
    ("administrasi", "Data Administrasi Organisasi",
     '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/>'
     '<path d="M9 14h6M12 11v6"/>'),
]

# Tab yang berubah sesuai status login
MENU_MASUK = ("login", "Masuk",
              '<path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"/><path d="m10 17 5-5-5-5"/><path d="M15 12H3"/>')
MENU_AKUN = ("akun", "Akun Saya",
             '<circle cx="12" cy="8" r="4"/><path d="M4 21c0-4.4 3.6-7 8-7s8 2.6 8 7"/>')
MENU_ADMIN = ("admin", "Kelola Berita",
              '<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"/>')

# Halaman turunan tetap menyalakan tab induknya
ALIAS_TAB = {"admin_tambah": "admin", "admin_ubah": "admin", "detail": "foto", "daftar": "login",
             "admin_profil": "profil"}


@app.before_request
def muat_pengguna():
    """Ambil akun yang sedang login dari database (jadi perubahan peran langsung berlaku)."""
    g.pengguna = None
    if request.endpoint == "static":
        return
    if "pid" in session:
        g.pengguna = db.session.get(Pengguna, session["pid"])
        if g.pengguna is None:            # akun sudah dihapus -> sesi tidak berlaku lagi
            session.clear()


@app.context_processor
def data_umum():
    """Data yang otomatis tersedia di semua template."""
    p = g.get("pengguna")
    menu = list(MENU)
    # Masuk / Akun Saya / Keluar kini ada di menu ikon profil (base.html)
    if p is not None and p.adalah_admin:
        menu.append(MENU_ADMIN)
    return {
        "menu": menu,
        "lokasi": LOKASI_KANTOR,
        "lokasi_maps": quote_plus(LOKASI_KANTOR),
        "pengguna": p,
        "sudah_masuk": p is not None,
        "aktif": ALIAS_TAB.get(request.endpoint, request.endpoint),
        "daftar_kategori": DAFTAR_KATEGORI,
        # foto kegiatan terbaru untuk latar kolase (disusun otomatis oleh app.js)
        "kolase": [foto_url(f) for (f,) in db.session.query(Berita.foto)
                   .filter(Berita.foto.isnot(None)).order_by(Berita.dibuat.desc()).limit(12)],
    }


@app.template_filter("waktu_lalu")
def waktu_lalu(dt):
    """Ubah waktu menjadi teks relatif, mis. '4 menit lalu'."""
    detik = max(int((datetime.now() - dt).total_seconds()), 0)
    for batas, pembagi, satuan in ((60, 1, "detik"), (3600, 60, "menit"),
                                   (86400, 3600, "jam"), (2592000, 86400, "hari"),
                                   (31536000, 2592000, "bulan")):
        if detik < batas:
            return f"{max(detik // pembagi, 1)} {satuan} lalu"
    return f"{detik // 31536000} tahun lalu"


# ---------------------------------------------------------------------------
# Bantuan: login & foto
# ---------------------------------------------------------------------------
def wajib_login(fungsi):
    """Dekorator: halaman untuk semua akun yang sudah login."""
    @wraps(fungsi)
    def pembungkus(*args, **kwargs):
        if g.pengguna is None:
            flash("Silakan masuk terlebih dahulu.", "galat")
            return redirect(url_for("login"))
        return fungsi(*args, **kwargs)
    return pembungkus


def wajib_admin(fungsi):
    """Dekorator: halaman khusus admin."""
    @wraps(fungsi)
    @wajib_login
    def pembungkus(*args, **kwargs):
        if not g.pengguna.adalah_admin:
            flash("Halaman ini khusus admin.", "galat")
            return redirect(url_for("beranda"))
        return fungsi(*args, **kwargs)
    return pembungkus


# Pembatas percobaan (di memori; untuk beberapa server gunakan Flask-Limiter + Redis)
PERCOBAAN = defaultdict(list)


def dibatasi(kunci, batas, detik):
    sekarang = time.time()
    PERCOBAAN[kunci] = [t for t in PERCOBAAN[kunci] if sekarang - t < detik]
    return len(PERCOBAAN[kunci]) >= batas


def catat(kunci):
    PERCOBAAN[kunci].append(time.time())


# Hash pura-pura: agar waktu respons sama baik akun ada maupun tidak
HASH_PURA = generate_password_hash("kata-sandi-pura-pura")

POLA_USERNAME = re.compile(r"^[a-z0-9_]{3,30}$")
POLA_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def masuk_sebagai(pengguna, ingat=False):
    session.clear()                      # cegah session fixation
    session["pid"] = pengguna.id         # yang disimpan di cookie hanya ID akun
    session.permanent = ingat


def periksa_kata_sandi(sandi, ulang, username=""):
    galat = []
    if len(sandi) < 8:
        galat.append("Kata sandi minimal 8 karakter.")
    elif len(sandi) > 128:
        galat.append("Kata sandi maksimal 128 karakter.")
    elif username and sandi.lower() == username:
        galat.append("Kata sandi tidak boleh sama dengan nama pengguna.")
    if sandi != ulang:
        galat.append("Ulangi kata sandi tidak sama.")
    return galat


def simpan_foto(file):
    """Validasi lalu simpan foto. Mengembalikan nama file (lokal) atau alamat https (Cloudinary).
    Mengembalikan None jika tidak ada file."""
    if not file or not file.filename:
        return None
    ekstensi = os.path.splitext(file.filename)[1].lower().lstrip(".")
    if ekstensi not in EKSTENSI_BOLEH:
        raise ValueError("Format foto harus JPG, PNG, atau WEBP.")
    try:                                  # pastikan isinya benar-benar gambar
        with Image.open(file.stream) as gambar:
            gambar.verify()
    except Exception:
        raise ValueError("File yang diunggah bukan gambar yang valid.")
    file.stream.seek(0)
    nama = uuid.uuid4().hex                      # nama acak, nama asli tidak dipakai
    if PAKAI_CLOUDINARY:
        try:
            hasil = cloudinary.uploader.upload(
                file.stream, folder="sipnu", public_id=nama, resource_type="image",
                transformation=[{"width": 1600, "crop": "limit"}, {"quality": "auto"}])
        except Exception as e:
            app.logger.exception("Unggah ke Cloudinary gagal")
            alasan = " ".join(str(e).split())[:200] or type(e).__name__
            raise ValueError(f"Foto gagal diunggah ke penyimpanan. Alasan: {alasan}")
        return hasil["secure_url"]
    nama = f"{nama}.{ekstensi}"
    file.save(os.path.join(app.config["UPLOAD_FOLDER"], nama))
    return nama


POLA_CLOUDINARY = re.compile(r"/upload/(?:v\d+/)?(.+)\.[A-Za-z0-9]+$")


def hapus_foto(nama):
    if not nama:
        return
    if nama.startswith("http"):                  # foto di Cloudinary
        cocok = POLA_CLOUDINARY.search(nama)
        if PAKAI_CLOUDINARY and cocok:
            try:
                cloudinary.uploader.destroy(cocok.group(1), resource_type="image")
            except Exception:
                app.logger.exception("Hapus foto di Cloudinary gagal")
        return
    jalur = os.path.join(app.config["UPLOAD_FOLDER"], os.path.basename(nama))
    if os.path.isfile(jalur):
        os.remove(jalur)


@app.template_global("foto_url")
def foto_url(nama):
    """Alamat gambar: langsung dipakai jika sudah https (Cloudinary), selain itu dari static/uploads."""
    if not nama:
        return ""
    return nama if nama.startswith("http") else url_for("static", filename="uploads/" + nama)


def baca_formulir():
    """Ambil & periksa isian formulir berita. Mengembalikan (data, daftar_galat)."""
    data = {
        "judul": request.form.get("judul", "").strip(),
        "deskripsi": request.form.get("deskripsi", "").strip(),
        "kategori": [k for k in request.form.getlist("kategori") if k in DAFTAR_KATEGORI],
    }
    galat = []
    if not data["judul"]:
        galat.append("Judul wajib diisi.")
    elif len(data["judul"]) > 200:
        galat.append("Judul maksimal 200 karakter.")
    if not data["deskripsi"]:
        galat.append("Deskripsi wajib diisi.")
    if not data["kategori"]:
        data["kategori"] = ["Berita"]
    return data, galat


# ---------------------------------------------------------------------------
# Halaman publik
# ---------------------------------------------------------------------------
@app.route("/")
def beranda():
    """Beranda: kegiatan terbaru di atas, lalu pintasan ke Susunan, Profil, dan Administrasi."""
    return render_template(
        "beranda.html",
        kegiatan=Berita.query.order_by(Berita.dibuat.desc()).limit(4).all(),
    )


@app.route("/berita/<int:id>")
def detail(id):
    return render_template("berita.html", b=db.get_or_404(Berita, id))


@app.route("/profil")
def profil():
    konten = db.session.get(ProfilKonten, 1)
    return render_template("profil.html", konten=konten)


@app.route("/admin/profil", methods=["GET", "POST"])
@wajib_admin
def admin_profil():
    konten = db.session.get(ProfilKonten, 1)
    data = {
        "judul": konten.judul if konten else "Sejarah Kepengurusan Ranting IPNU IPPNU",
        "isi": konten.isi if konten else "",
    }
    if request.method == "POST":
        data = {
            "judul": request.form.get("judul", "").strip(),
            "isi": request.form.get("isi", "").strip(),
        }
        galat = []
        if not data["judul"]:
            galat.append("Judul wajib diisi.")
        elif len(data["judul"]) > 200:
            galat.append("Judul maksimal 200 karakter.")
        if not data["isi"]:
            galat.append("Isi wajib diisi.")

        foto_baru = None
        if not galat:
            try:
                foto_baru = simpan_foto(request.files.get("foto"))
            except ValueError as e:
                galat.append(str(e))

        if not galat:
            if konten is None:
                konten = ProfilKonten(id=1, judul=data["judul"], isi=data["isi"], foto=foto_baru,
                                      diperbarui_oleh=g.pengguna.username)
                db.session.add(konten)
            else:
                konten.judul, konten.isi = data["judul"], data["isi"]
                konten.diperbarui_oleh = g.pengguna.username
                if foto_baru:                      # ganti foto: hapus yang lama
                    hapus_foto(konten.foto)
                    konten.foto = foto_baru
            db.session.commit()
            flash("Konten Profil berhasil disimpan.", "sukses")
            return redirect(url_for("profil"))
        for pesan in galat:
            flash(pesan, "galat")
    return render_template("form_profil.html", data=data, konten=konten)


@app.route("/susunan")
def susunan():
    return render_template("susunan.html")


@app.route("/foto")
def foto():
    """Foto Kegiatan: semua berita yang diunggah admin tampil di sini."""
    berita = Berita.query.order_by(Berita.dibuat.desc()).limit(30).all()
    semua = berita[1:]
    jumlah = {k: sum(k in b.kategori_list for b in semua) for k in DAFTAR_KATEGORI}
    return render_template(
        "foto.html",
        utama=berita[0] if berita else None,
        terbaru=berita[1:4],
        semua=semua,
        kategori=DAFTAR_KATEGORI,
        jumlah=jumlah,
    )


@app.route("/administrasi")
def administrasi():
    return render_template("administrasi.html")


# ---------------------------------------------------------------------------
# Masuk, daftar, dan akun saya
# ---------------------------------------------------------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if g.pengguna:
        return redirect(url_for("akun"))
    data = {"identitas": ""}
    if request.method == "POST":
        data["identitas"] = request.form.get("identitas", "").strip().lower()
        kunci = f"masuk:{request.remote_addr}:{data['identitas']}"
        if dibatasi(kunci, 5, 600):
            flash("Terlalu banyak percobaan. Coba lagi dalam 10 menit.", "galat")
            return render_template("masuk.html", mode="masuk", data=data), 429
        p = Pengguna.query.filter(
            (Pengguna.username == data["identitas"]) | (Pengguna.email == data["identitas"])
        ).first()
        sandi = request.form.get("password", "")
        sah = check_password_hash(p.password_hash if p else HASH_PURA, sandi)
        if p and sah:
            PERCOBAAN.pop(kunci, None)
            masuk_sebagai(p, ingat=bool(request.form.get("ingat")))
            flash(f"Selamat datang, {p.nama_lengkap}.", "sukses")
            return redirect(url_for("admin" if p.adalah_admin else "beranda"))
        catat(kunci)
        flash("Nama pengguna/email atau kata sandi salah.", "galat")   # pesan sengaja umum
    return render_template("masuk.html", mode="masuk", data=data)


@app.route("/daftar", methods=["GET", "POST"])
def daftar():
    if g.pengguna:
        return redirect(url_for("akun"))
    data = {"nama_lengkap": "", "username": "", "email": ""}
    if request.method == "POST":
        data = {
            "nama_lengkap": " ".join(request.form.get("nama_lengkap", "").split()),
            "username": request.form.get("username", "").strip().lower(),
            "email": request.form.get("email", "").strip().lower(),
        }
        sandi = request.form.get("password", "")
        ulang = request.form.get("ulang", "")

        kunci = f"daftar:{request.remote_addr}"
        if dibatasi(kunci, 10, 3600):
            flash("Terlalu banyak pendaftaran dari perangkat ini. Coba lagi nanti.", "galat")
            return render_template("masuk.html", mode="daftar", data=data), 429
        catat(kunci)

        galat = []
        if not 3 <= len(data["nama_lengkap"]) <= 80:
            galat.append("Nama lengkap 3 sampai 80 karakter.")
        if not POLA_USERNAME.match(data["username"]):
            galat.append("Nama pengguna 3-30 karakter: huruf kecil, angka, atau garis bawah.")
        elif Pengguna.query.filter_by(username=data["username"]).first():
            galat.append("Nama pengguna sudah dipakai.")
        if not POLA_EMAIL.match(data["email"]) or len(data["email"]) > 120:
            galat.append("Format email tidak valid.")
        elif Pengguna.query.filter_by(email=data["email"]).first():
            galat.append("Email sudah terdaftar.")
        galat += periksa_kata_sandi(sandi, ulang, data["username"])

        if not galat:
            p = Pengguna(**data, password_hash=generate_password_hash(sandi), peran="anggota")
            db.session.add(p)
            try:
                db.session.commit()
            except IntegrityError:            # jaga-jaga jika dua orang mendaftar bersamaan
                db.session.rollback()
                galat.append("Nama pengguna atau email sudah dipakai.")
            else:
                masuk_sebagai(p)
                flash("Akun berhasil dibuat. Selamat bergabung di SIPNU!", "sukses")
                return redirect(url_for("akun"))
        for g_ in galat:
            flash(g_, "galat")
    return render_template("masuk.html", mode="daftar", data=data)


@app.route("/akun")
@wajib_login
def akun():
    return render_template("akun.html")


@app.route("/akun/sandi", methods=["POST"])
@wajib_login
def ganti_sandi():
    lama = request.form.get("lama", "")
    baru = request.form.get("baru", "")
    ulang = request.form.get("ulang", "")
    galat = []
    if not check_password_hash(g.pengguna.password_hash, lama):
        galat.append("Kata sandi lama salah.")
    if baru and baru == lama:
        galat.append("Kata sandi baru harus berbeda dari yang lama.")
    galat += periksa_kata_sandi(baru, ulang, g.pengguna.username)
    if galat:
        for g_ in galat:
            flash(g_, "galat")
    else:
        g.pengguna.password_hash = generate_password_hash(baru)
        db.session.commit()
        flash("Kata sandi berhasil diganti.", "sukses")
    return redirect(url_for("akun"))


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("Anda sudah keluar.", "sukses")
    return redirect(url_for("beranda"))


# ---------------------------------------------------------------------------
# Kelola berita (khusus admin)
# ---------------------------------------------------------------------------
@app.route("/admin")
@wajib_admin
def admin():
    daftar = Berita.query.order_by(Berita.dibuat.desc()).all()
    return render_template("admin.html", daftar=daftar)


@app.route("/admin/tambah", methods=["GET", "POST"])
@wajib_admin
def admin_tambah():
    data = {"judul": "", "deskripsi": "", "kategori": ["Berita"]}
    if request.method == "POST":
        data, galat = baca_formulir()
        nama_foto = None
        if not galat:
            try:
                nama_foto = simpan_foto(request.files.get("foto"))
            except ValueError as e:
                galat.append(str(e))
        if not galat:
            db.session.add(Berita(
                judul=data["judul"], deskripsi=data["deskripsi"],
                kategori=",".join(data["kategori"]), foto=nama_foto,
                penulis=g.pengguna.username,
            ))
            db.session.commit()
            flash("Berita berhasil ditambahkan.", "sukses")
            return redirect(url_for("admin"))
        for pesan in galat:
            flash(pesan, "galat")
    return render_template("form_berita.html", data=data, berita=None)


@app.route("/admin/ubah/<int:id>", methods=["GET", "POST"])
@wajib_admin
def admin_ubah(id):
    b = db.get_or_404(Berita, id)
    data = {"judul": b.judul, "deskripsi": b.deskripsi, "kategori": b.kategori_list}
    if request.method == "POST":
        data, galat = baca_formulir()
        foto_baru = None
        if not galat:
            try:
                foto_baru = simpan_foto(request.files.get("foto"))
            except ValueError as e:
                galat.append(str(e))
        if not galat:
            b.judul, b.deskripsi = data["judul"], data["deskripsi"]
            b.kategori = ",".join(data["kategori"])
            if foto_baru:                          # ganti foto: hapus yang lama
                hapus_foto(b.foto)
                b.foto = foto_baru
            db.session.commit()
            flash("Perubahan disimpan.", "sukses")
            return redirect(url_for("admin"))
        for pesan in galat:
            flash(pesan, "galat")
    return render_template("form_berita.html", data=data, berita=b)


@app.route("/admin/hapus/<int:id>", methods=["POST"])
@wajib_admin
def admin_hapus(id):
    b = db.get_or_404(Berita, id)
    hapus_foto(b.foto)
    db.session.delete(b)
    db.session.commit()
    flash("Berita dihapus.", "sukses")
    return redirect(url_for("admin"))


# ---------------------------------------------------------------------------
# Penanganan galat
# ---------------------------------------------------------------------------
@app.errorhandler(413)
def terlalu_besar(_):
    flash("Ukuran unggahan terlalu besar (maksimal 5 MB).", "galat")
    return redirect(url_for("admin" if g.get("pengguna") and g.pengguna.adalah_admin else "beranda"))


@app.errorhandler(CSRFError)
def csrf_gagal(_):
    flash("Sesi formulir sudah kedaluwarsa. Silakan coba lagi.", "galat")
    return redirect(url_for("beranda"))


# ---------------------------------------------------------------------------
# Perintah terminal
# ---------------------------------------------------------------------------
@app.cli.command("buat-admin")
@click.argument("username")
def buat_admin(username):
    """Membuat akun admin baru (atau memperbarui kata sandi & menjadikannya admin)."""
    username = username.strip().lower()
    if not POLA_USERNAME.match(username):
        raise click.ClickException("Nama pengguna 3-30 karakter: huruf kecil, angka, garis bawah.")
    p = Pengguna.query.filter_by(username=username).first()
    if p is None:
        nama = click.prompt("Nama lengkap")
        email = click.prompt("Email").strip().lower()
        if Pengguna.query.filter_by(email=email).first():
            raise click.ClickException("Email itu sudah dipakai akun lain.")
    sandi = click.prompt("Kata sandi", hide_input=True, confirmation_prompt=True)
    if len(sandi) < 8:
        raise click.ClickException("Kata sandi minimal 8 karakter.")
    if p:
        p.password_hash, p.peran = generate_password_hash(sandi), "admin"
        click.echo(f"Akun '{username}' diperbarui dan menjadi admin.")
    else:
        db.session.add(Pengguna(nama_lengkap=nama, username=username, email=email,
                                password_hash=generate_password_hash(sandi), peran="admin"))
        click.echo(f"Admin '{username}' dibuat.")
    db.session.commit()


@app.cli.command("pindah-data")
@click.option("--sumber", default=None, help="Jalur file SQLite lama (bawaan: instance/sipnu.db).")
def pindah_data(sumber):
    """Menyalin akun, berita, dan profil dari SQLite lokal ke database online (DATABASE_URL),
    lalu mengunggah foto lokal ke Cloudinary (CLOUDINARY_URL)."""
    from sqlalchemy import create_engine
    sumber = sumber or os.path.join(app.instance_path, "sipnu.db")
    if not os.path.isfile(sumber):
        raise click.ClickException(f"File database lama tidak ditemukan: {sumber}")
    if _url_database().startswith("sqlite"):
        raise click.ClickException("DATABASE_URL belum diisi alamat database online (Neon).")
    if not PAKAI_CLOUDINARY:
        raise click.ClickException("CLOUDINARY_URL belum diisi.")

    lama = create_engine("sqlite:///" + os.path.abspath(sumber))
    cache_foto = {}

    def pindahkan_foto(nama):
        """Unggah foto lokal ke Cloudinary (sekali per file). Alamat https dibiarkan."""
        if not nama or nama.startswith("http"):
            return nama
        if nama not in cache_foto:
            jalur = os.path.join(app.config["UPLOAD_FOLDER"], os.path.basename(nama))
            if not os.path.isfile(jalur):
                click.echo(f"  ! foto tidak ada di komputer, dilewati: {nama}")
                cache_foto[nama] = None
            else:
                with open(jalur, "rb") as fh:
                    hasil = cloudinary.uploader.upload(
                        fh, folder="sipnu", public_id=os.path.splitext(os.path.basename(nama))[0],
                        resource_type="image", overwrite=True,
                        transformation=[{"width": 1600, "crop": "limit"}, {"quality": "auto"}])
                cache_foto[nama] = hasil["secure_url"]
                click.echo(f"  foto terunggah: {nama}")
        return cache_foto[nama]

    jumlah = {"pengguna": 0, "profil_konten": 0, "berita": 0}
    with lama.connect() as sambung:
        for model, tabel in ((Pengguna, "pengguna"), (ProfilKonten, "profil_konten"), (Berita, "berita")):
            kolom = [c.name for c in model.__table__.columns]
            baris = sambung.execute(text(f"SELECT * FROM {tabel}")).mappings().all()
            for b in baris:
                data = {k: b[k] for k in kolom if k in b}
                if "foto" in data:
                    data["foto"] = pindahkan_foto(data["foto"])
                for k in ("dibuat", "diperbarui"):          # SQLite mengembalikan teks bila diambil mentah
                    if isinstance(data.get(k), str):
                        data[k] = datetime.fromisoformat(data[k])
                if db.session.get(model, data["id"]) is None:
                    db.session.add(model(**data))
                    jumlah[tabel] += 1
            db.session.commit()

    if db.engine.dialect.name == "postgresql":              # samakan penghitung id setelah salin manual
        for tabel in ("pengguna", "profil_konten", "berita"):
            db.session.execute(text(
                f"SELECT setval(pg_get_serial_sequence('{tabel}', 'id'), COALESCE((SELECT MAX(id) FROM {tabel}), 1))"))
        db.session.commit()
    click.echo(f"Selesai. Disalin: {jumlah['pengguna']} akun, {jumlah['profil_konten']} profil, {jumlah['berita']} berita.")


@app.cli.command("jadikan-admin")
@click.argument("username")
def jadikan_admin(username):
    """Menaikkan anggota yang sudah mendaftar menjadi admin."""
    p = Pengguna.query.filter_by(username=username.strip().lower()).first()
    if not p:
        raise click.ClickException("Akun tidak ditemukan.")
    p.peran = "admin"
    db.session.commit()
    click.echo(f"'{p.username}' sekarang admin.")


@app.cli.command("daftar-akun")
def daftar_akun():
    """Menampilkan semua akun (tanpa kata sandi)."""
    for p in Pengguna.query.order_by(Pengguna.id):
        click.echo(f"{p.id:>3}  {p.username:<20} {p.peran:<8} {p.email}")


@app.cli.command("contoh-data")
def contoh_data():
    """Mengisi beberapa berita contoh (opsional, untuk mencoba tampilan)."""
    contoh = [
        ("Resmi Dibuka, Konfercab PC IPNU IPPNU Kota Yogyakarta Usung Semangat Legasi Berkelanjutan",
         "Konferensi cabang resmi dibuka dan menjadi ruang bagi kader untuk menyusun arah organisasi ke depan.",
         "Berita,Kaderisasi", timedelta(minutes=4)),
        ("PC IPNU-IPPNU Padang Lawas Bersama Pemdes Panarian Peringati Maulid Nabi",
         "Peringatan Maulid Nabi digelar bersama pemerintah desa dan diikuti para pelajar setempat.",
         "Berita,Daerah", timedelta(hours=23)),
        ("PAC IPNU-IPPNU Plered Gelar Maulid Nabi, Perkuat Silaturahmi Keluarga Besar NU",
         "Kegiatan dihadiri pengurus dan warga sebagai wadah mempererat silaturahmi.",
         "Berita,Daerah", timedelta(hours=23)),
        ("Pelajar NU Kota Tangerang Didorong Jadi Kreator Konten Positif",
         "Pelajar diajak memanfaatkan media sosial untuk menyebarkan konten yang bermanfaat.",
         "Informasi", timedelta(days=5)),
    ]
    for judul, isi, kategori, selisih in contoh:
        db.session.add(Berita(judul=judul, deskripsi=isi, kategori=kategori,
                              dibuat=datetime.now() - selisih))
    db.session.commit()
    click.echo(f"{len(contoh)} berita contoh ditambahkan.")


if __name__ == "__main__":
    app.run(debug=True)
