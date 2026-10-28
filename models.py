"""Model database SIPNU: Pengguna (admin & anggota) dan Berita."""

import re
from datetime import datetime

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

DAFTAR_KATEGORI = ["Berita", "Daerah", "Kaderisasi", "Informasi"]


class Pengguna(db.Model):
    """Semua akun yang bisa login. Kolom `peran` menentukan haknya."""
    __tablename__ = "pengguna"

    id = db.Column(db.Integer, primary_key=True)
    nama_lengkap = db.Column(db.String(80), nullable=False)
    username = db.Column(db.String(30), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)   # BUKAN kata sandi asli
    peran = db.Column(db.String(10), nullable=False, default="anggota")  # "anggota" / "admin"
    dibuat = db.Column(db.DateTime, nullable=False, default=datetime.now)

    @property
    def adalah_admin(self):
        return self.peran == "admin"

    @property
    def inisial(self):
        kata = self.nama_lengkap.split()
        return "".join(k[0] for k in kata[:2]).upper() or "?"


class ProfilKonten(db.Model):
    """Konten halaman Profil (sejarah kepengurusan ranting). Satu baris saja (id=1)."""
    __tablename__ = "profil_konten"

    id = db.Column(db.Integer, primary_key=True)
    judul = db.Column(db.String(200), nullable=False)
    isi = db.Column(db.Text, nullable=False)
    foto = db.Column(db.String(100))          # hanya nama file di static/uploads/
    diperbarui = db.Column(db.DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)
    diperbarui_oleh = db.Column(db.String(50), nullable=False, default="admin")


class Berita(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    judul = db.Column(db.String(200), nullable=False)
    deskripsi = db.Column(db.Text, nullable=False)
    kategori = db.Column(db.String(100), nullable=False, default="Berita")  # "Berita,Daerah"
    foto = db.Column(db.String(100))          # hanya nama file di static/uploads/
    penulis = db.Column(db.String(50), nullable=False, default="admin")
    dibuat = db.Column(db.DateTime, nullable=False, default=datetime.now)

    @property
    def kategori_list(self):
        return [k for k in self.kategori.split(",") if k]

    @property
    def waktu(self):
        return self.dibuat

    @property
    def ringkas(self):
        """Potongan deskripsi untuk kartu di Beranda."""
        teks = re.sub(r"\s+", " ", self.deskripsi).strip()
        return teks if len(teks) <= 140 else teks[:137].rstrip() + "..."
