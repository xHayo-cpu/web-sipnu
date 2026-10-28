// ===== SIPNU - skrip utama =====
document.addEventListener("DOMContentLoaded", function () {
  // Di ponsel, geser menu agar ikon yang aktif terlihat.
  var aktif = document.querySelector('.nav-ikon[aria-current="page"]');
  if (aktif) {
    aktif.scrollIntoView({ block: "nearest", inline: "center" });
  }

  // Beranda: saring kartu berita berdasarkan kategori.
  var chips = document.querySelectorAll(".chip");
  var kartu = document.querySelectorAll(".kartu");
  var kosong = document.getElementById("kosong");

  chips.forEach(function (chip) {
    chip.addEventListener("click", function () {
      var pilih = chip.dataset.filter;
      chips.forEach(function (c) { c.setAttribute("aria-pressed", c === chip ? "true" : "false"); });

      var tampil = 0;
      kartu.forEach(function (k) {
        var cocok = pilih === "semua" || k.dataset.kategori.split(" ").indexOf(pilih) !== -1;
        k.hidden = !cocok;
        if (cocok) tampil++;
      });
      if (kosong) kosong.hidden = tampil > 0;
    });
  });
});

// Formulir berita: tampilkan pratinjau foto yang dipilih.
document.addEventListener("DOMContentLoaded", function () {
  var input = document.getElementById("input-foto");
  var kotak = document.getElementById("pratinjau");
  var gambar = document.getElementById("pratinjau-gambar");
  if (!input || !kotak || !gambar) return;

  input.addEventListener("change", function () {
    var file = input.files && input.files[0];
    if (!file) return;
    gambar.src = URL.createObjectURL(file);
    kotak.hidden = false;
  });
});

// Kolom kata sandi: tombol Lihat / Sembunyi.
document.addEventListener("DOMContentLoaded", function () {
  document.querySelectorAll(".lihat").forEach(function (tombol) {
    tombol.addEventListener("click", function () {
      var input = tombol.parentElement.querySelector("input");
      var tampil = input.type === "password";
      input.type = tampil ? "text" : "password";
      tombol.textContent = tampil ? "Sembunyi" : "Lihat";
      tombol.setAttribute("aria-label", tampil ? "Sembunyikan kata sandi" : "Tampilkan kata sandi");
    });
  });
});


// Tombol tema terang / gelap (pilihan disimpan di peramban).
document.addEventListener("DOMContentLoaded", function () {
  var tombol = document.getElementById("tombol-tema");
  if (!tombol) return;
  tombol.addEventListener("click", function () {
    var root = document.documentElement;
    var baru = root.dataset.tema === "dark" ? "light" : "dark";
    root.dataset.tema = baru;
    try { localStorage.setItem("tema", baru); } catch (e) {}
  });
});

// Latar kolase: foto kegiatan dipotong, diacak, dan disusun otomatis jadi ubin kecil-kecil.
// Susunannya tetap (acak bersandi) agar tidak berubah-ubah antarhalaman.
document.addEventListener("DOMContentLoaded", function () {
  var wadah = document.getElementById("kolase");
  var data = document.getElementById("data-kolase");
  if (!wadah) return;

  var foto = [];
  try { foto = JSON.parse(data.textContent) || []; } catch (e) {}
  var basis = wadah.dataset.basis || "/static/uploads/";
  var gradasi = [
    "linear-gradient(135deg,#0a5a37,#17a56a)", "linear-gradient(135deg,#0e7a4b,#6cc9a0)",
    "linear-gradient(135deg,#14624a,#2fb5a0)", "linear-gradient(135deg,#2d7a3e,#9bd36a)",
    "linear-gradient(135deg,#0b4d46,#3aa6b0)"
  ];

  function acak(seed) {                       // pembangkit acak tetap (mulberry32)
    return function () {
      seed |= 0; seed = (seed + 0x6D2B79F5) | 0;
      var t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  function susun() {
    var rnd = acak(2026);
    var lebar = window.innerWidth, tinggi = window.innerHeight;
    var sel = Math.max(96, Math.min(150, Math.round(lebar / 11)));
    var kol = Math.ceil((lebar * 1.25) / (sel + 8));
    var baris = Math.ceil((tinggi * 1.25) / (sel + 8));
    var total = kol * baris;

    var grid = document.createElement("div");
    grid.className = "kolase-grid";
    grid.style.setProperty("--kol", kol);
    grid.style.setProperty("--sel", sel + "px");

    var terisi = 0, i = 0;
    while (terisi < total * 1.05) {
      var r = rnd(), kelas = "", luas = 1;
      if (r > 0.94) { kelas = "b"; luas = 4; }
      else if (r > 0.82) { kelas = "l"; luas = 2; }
      else if (r > 0.70) { kelas = "t"; luas = 2; }

      var ubin = document.createElement("div");
      ubin.className = "kolase-ubin" + (kelas ? " " + kelas : "");
      if (foto.length) {
        // tiap ubin memotong bagian foto yang berbeda (zoom & posisi acak)
        var zoom = 100 + Math.floor(rnd() * 220);
        ubin.style.backgroundImage = "url('" + basis + encodeURIComponent(foto[Math.floor(rnd() * foto.length)]) + "')";
        ubin.style.backgroundSize = (zoom === 100 ? "cover" : zoom + "%");
        ubin.style.backgroundPosition = Math.floor(rnd() * 100) + "% " + Math.floor(rnd() * 100) + "%";
      } else {
        ubin.style.backgroundImage = gradasi[i % gradasi.length];
      }
      grid.appendChild(ubin);
      terisi += luas; i++;
    }

    wadah.textContent = "";
    wadah.appendChild(grid);
    requestAnimationFrame(function () { grid.classList.add("siap"); });
  }

  susun();
  var tunda;
  window.addEventListener("resize", function () {
    clearTimeout(tunda);
    tunda = setTimeout(susun, 250);
  });
});
