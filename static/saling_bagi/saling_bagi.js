
document.addEventListener("DOMContentLoaded", function () {

    // CUSTOM LOCATION INPUT
    const lokasiSelect = document.getElementById("id_lokasi_pengambilan");
    const lokasiContainer = document.getElementById("lokasi-lainnya-container");
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

    // FOOD SEARCH, LOCATION FILTER, AND SORTING
    const searchInput = document.getElementById("bagiSearch");
    const locationSelect = document.getElementById("bagiLocation");
    const sortSelect = document.getElementById("bagiSort");
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
            const description = (card.dataset.description || "").toLowerCase();
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
            resultCount.textContent = visibleCount;
        }

        if (noResults) {
            noResults.hidden = !(cards.length > 0 && visibleCount === 0);
        }
    }

    function sortFoods() {
        if (!sortSelect) return;

        const sortType = sortSelect.value;
        const sortedCards = [...cards];

        sortedCards.sort(function (a, b) {
            if (sortType === "oldest") {
                return Number(a.dataset.date) - Number(b.dataset.date);
            }

            if (sortType === "name") {
                return (a.dataset.name || "").localeCompare(
                    b.dataset.name || ""
                );
            }

            return Number(b.dataset.date) - Number(a.dataset.date);
        });

        sortedCards.forEach(function (card) {
            foodGrid.insertBefore(card, noResults);
        });

        filterFoods();
    }

    if (searchInput) {
        searchInput.addEventListener("input", filterFoods);
    }

    if (locationSelect) {
        locationSelect.addEventListener("change", filterFoods);
    }

    if (sortSelect) {
        sortSelect.addEventListener("change", sortFoods);
    }

    filterFoods();
});
