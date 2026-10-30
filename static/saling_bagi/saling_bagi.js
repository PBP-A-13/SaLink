document.addEventListener("DOMContentLoaded", function () {


    const lokasiSelect = document.getElementById("id_lokasi_pengambilan");
    const lokasiContainer = document.getElementById(
        "lokasi-lainnya-container"
    );
    const lokasiInput = document.getElementById("id_lokasi_lainnya");

    function toggleLokasiLainnya() {
        if (!lokasiSelect || !lokasiContainer) return;

        const isLainnya = lokasiSelect.value === "lainnya";

        lokasiContainer.hidden = !isLainnya;

        if (lokasiInput) {
            lokasiInput.required = isLainnya;

            if (!isLainnya) {
                lokasiInput.value = "";
            }
        }
    }

    if (lokasiSelect) {
        lokasiSelect.addEventListener("change", toggleLokasiLainnya);
        toggleLokasiLainnya();
    }


    // ========================================
    // FOOD SEARCH AND LOCATION FILTER
    // ========================================

    const searchInput = document.getElementById("bagiSearch");
    const locationSelect = document.getElementById("bagiLocation");
    const resultCount = document.getElementById("bagiResultCount");
    const noResults = document.getElementById("bagiNoResults");
    const foodGrid = document.getElementById("bagiFoodGrid");

    if (!foodGrid) return;

    const cards = Array.from(
        foodGrid.querySelectorAll(".bagi-food-card")
    );

    function filterFoods() {
        const keyword = searchInput
            ? searchInput.value.toLowerCase().trim()
            : "";

        const selectedLocation = locationSelect
            ? locationSelect.value
            : "";

        let visibleCount = 0;

        cards.forEach(function (card) {
            const name = (card.dataset.name || "").toLowerCase();
            const description = (
                card.dataset.description || ""
            ).toLowerCase();

            const cardLocation = card.dataset.location || "";

            const matchesKeyword =
                name.includes(keyword) ||
                description.includes(keyword);

            const matchesLocation =
                selectedLocation === "" ||
                cardLocation === selectedLocation;

            const isVisible = matchesKeyword && matchesLocation;

            card.hidden = !isVisible;

            if (isVisible) {
                visibleCount++;
            }
        });

        if (resultCount) {
            resultCount.textContent =
                visibleCount + " makanan tersedia";
        }

        if (noResults) {
            noResults.hidden = visibleCount !== 0;
        }
    }

    if (searchInput) {
        searchInput.addEventListener("input", filterFoods);
    }

    if (locationSelect) {
        locationSelect.addEventListener("change", filterFoods);
    }

    filterFoods();

});