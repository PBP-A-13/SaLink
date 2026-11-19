// ============================================================
// saling_bagi.js  ->  FRONTEND murni (jalan di browser, bukan di server).
// Tidak ada fetch/AJAX ke backend. Hanya memanipulasi HTML yang sudah di-render Django.
// ============================================================

document.addEventListener("DOMContentLoaded", function () {   // tunggu seluruh HTML selesai dimuat baru jalankan kode

    // ========================================
    // BAGIAN 1: Tampilkan/sembunyikan input "lokasi lainnya" (halaman tambah makanan)
    // ========================================

    const lokasiSelect = document.getElementById("id_lokasi_pengambilan");   // dropdown lokasi (id otomatis dari Django form)
    const lokasiContainer = document.getElementById(
        "lokasi-lainnya-container"                    // div pembungkus input tambahan
    );
    const lokasiInput = document.getElementById("id_lokasi_lainnya");        // input teks lokasi lainnya

    function toggleLokasiLainnya() {
        if (!lokasiSelect || !lokasiContainer) return;   // halaman ini tidak punya elemennya -> berhenti (aman)

        const isLainnya = lokasiSelect.value === "lainnya";   // true kalau user memilih "Lainnya"

        lokasiContainer.hidden = !isLainnya;          // tampil hanya kalau "lainnya"

        if (lokasiInput) {
            lokasiInput.required = isLainnya;         // wajib diisi hanya kalau "lainnya" (validasi sisi browser)

            if (!isLainnya) {
                lokasiInput.value = "";               // bukan "lainnya" -> kosongkan isinya
            }
        }
    }

    if (lokasiSelect) {
        lokasiSelect.addEventListener("change", toggleLokasiLainnya);   // jalankan tiap pilihan berubah
        toggleLokasiLainnya();                        // jalankan sekali saat awal (untuk kondisi default/form error)
    }


    // ========================================
    // BAGIAN 2: Search dan filter lokasi (halaman daftar makanan)
    // CLIENT-SIDE: hanya menyembunyikan kartu yang sudah ada di halaman.
    // ========================================

    const searchInput = document.getElementById("bagiSearch");        // kolom pencarian
    const locationSelect = document.getElementById("bagiLocation");   // dropdown filter lokasi
    const resultCount = document.getElementById("bagiResultCount");   // teks "N makanan tersedia"
    const noResults = document.getElementById("bagiNoResults");       // pesan "tidak ada hasil"
    const foodGrid = document.getElementById("bagiFoodGrid");         // wadah semua kartu

    if (!foodGrid) return;                            // bukan halaman daftar makanan -> berhenti di sini

    const cards = Array.from(
        foodGrid.querySelectorAll(".bagi-food-card")  // kumpulkan semua kartu menjadi array
    );

    function filterFoods() {
        const keyword = searchInput
            ? searchInput.value.toLowerCase().trim()  // kata kunci huruf kecil, tanpa spasi pinggir
            : "";

        const selectedLocation = locationSelect
            ? locationSelect.value
            : "";                                     // "" = semua lokasi

        let visibleCount = 0;                         // penghitung kartu yang lolos filter

        cards.forEach(function (card) {
            const name = (card.dataset.name || "").toLowerCase();         // dari atribut data-name di HTML
            const description = (
                card.dataset.description || ""                            // dari data-description
            ).toLowerCase();

            const cardLocation = card.dataset.location || "";             // dari data-location

            const matchesKeyword =
                name.includes(keyword) ||
                description.includes(keyword);        // cocok jika kata kunci ada di nama ATAU deskripsi

            const matchesLocation =
                selectedLocation === "" ||            // tidak memfilter lokasi, atau...
                cardLocation === selectedLocation;    // ...lokasi kartu sama dengan pilihan

            const isVisible = matchesKeyword && matchesLocation;   // harus lolos keduanya

            card.hidden = !isVisible;                 // sembunyikan/tampilkan kartu

            if (isVisible) {
                visibleCount++;
            }
        });

        if (resultCount) {
            resultCount.textContent =
                visibleCount + " makanan tersedia";   // update teks jumlah
        }

        if (noResults) {
            noResults.hidden = visibleCount !== 0;    // tampilkan pesan kosong hanya kalau 0 hasil
        }
    }

    if (searchInput) {
        searchInput.addEventListener("input", filterFoods);       // filter tiap ketikan
    }

    if (locationSelect) {
        locationSelect.addEventListener("change", filterFoods);   // filter tiap ganti lokasi
    }

    filterFoods();                                    // jalankan sekali saat halaman dibuka
});