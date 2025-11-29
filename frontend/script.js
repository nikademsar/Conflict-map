// Inicializacija zemljevida
const map = L.map('map').setView([20, 0], 2); // svetovni pogled

// Osnovni tile layer (OpenStreetMap)
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 18,
    attribution: '&copy; OpenStreetMap contributors'
}).addTo(map);

// Layer za konflikte
let conflictsLayer = null;

// Slider element
const yearSlider = document.getElementById('year');
const yearText = document.getElementById('year-value');

async function loadConflicts(year) {
    const url = `http://localhost:8000/conflicts?year=${year}`;

    try {
        const response = await fetch(url);
        if (!response.ok) {
            console.error('Napaka pri klicu API:', response.status, response.statusText);
            return;
        }

        const geojson = await response.json();

        // preveri v konzoli, koliko feature-jev pride
        console.log(`Leto ${year}:`, geojson);

        // odstrani prejšnji sloj
        if (conflictsLayer) {
            map.removeLayer(conflictsLayer);
        }

        // dodaj nov GeoJSON sloj
        conflictsLayer = L.geoJSON(geojson, {
            pointToLayer: (feature, latlng) => {
                return L.circleMarker(latlng, {
                    radius: 5,
                    weight: 1,
                    opacity: 1,
                    fillOpacity: 0.7
                });
            },
            onEachFeature: (feature, layer) => {
                const p = feature.properties || {};
                const conflictName = p.conflict_name || 'Neznan konflikt';
                const country = p.country || 'Neznana drzava';
                const yearStr = p.year || year;

                let popupHtml = `<strong>${conflictName}</strong><br/>`;
                popupHtml += `Drzava: ${country}<br/>`;
                popupHtml += `Leto: ${yearStr}<br/>`;

                if (p.best != null) {
                    popupHtml += `Ocena zrtev: ${p.best}<br/>`;
                }
                if (p.type_of_violence != null) {
                    popupHtml += `Tip vojne: ${p.type_of_violence}<br/>`;
                }

                layer.bindPopup(popupHtml);
            }
        }).addTo(map);

        // fit na layer, če je kaj podatkov
        if (geojson.features && geojson.features.length > 0) {
            const bounds = conflictsLayer.getBounds();
            if (bounds.isValid()) {
                map.fitBounds(bounds, { maxZoom: 5 });
            }
        }

    } catch (err) {
        console.error('Napaka pri nalaganju konfliktov:', err);
    }
}

// event za slider
yearSlider.addEventListener('input', () => {
    const year = yearSlider.value;
    yearText.textContent = year;
    loadConflicts(year);
});


// inicialni load
loadConflicts(yearSlider.value);
