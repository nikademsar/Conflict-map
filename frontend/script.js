// Inicializacija zemljevida
const map = L.map('map', { zoomControl: false}).setView([20, 0], 2); // svetovni pogled

L.control.zoom({
    position: 'topright'
}).addTo(map)

// Osnovni tile layer (OpenStreetMap)
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 18,
    attribution: '&copy; OpenStreetMap contributors'
}).addTo(map);

// Layer za konflikte + cluster group
let conflictsLayer = null;

const conflictClusters = L.markerClusterGroup({
    disableClusteringAtZoom: 5,   // pri večjem zoomu se razbijejo
    maxClusterRadius: 40          // kako blizu morejo bit točke
});
map.addLayer(conflictClusters);

// Slider element
const yearSlider = document.getElementById('year');
const yearText = document.getElementById('year-value');

function colorForBest(best) {
    if (best == null || isNaN(best)) return '#888888'; // brez podatkov
    if (best < 25)  return '#4da6ff';  // malo žrtev - modra
    if (best < 100) return '#ffa500';  // srednje - oranzna
    return '#ff0000';                  // veliko - rdeca
} 

async function loadConflicts(year, doFit = false) {
    const url = `http://localhost:8000/conflicts?year=${year}`;

    try {
        const response = await fetch(url);
        if (!response.ok) {
            console.error('Napaka pri klicu API:', response.status, response.statusText);
            return;
        }

        const geojson = await response.json();
        console.log(`Leto ${year}:`, geojson);

        // očisti staro stanje
        conflictClusters.clearLayers();

        // nov GeoJSON sloj
        conflictsLayer = L.geoJSON(geojson, {
            pointToLayer: (feature, latlng) => {
                const p = feature.properties || {};
                const best = p.best;
                const color = colorForBest(best);

                return L.circleMarker(latlng, {
                    radius: 5,
                    weight: 1,
                    color: color,
                    fillColor: color,
                    opacity: 1,
                    fillOpacity: 0.7
                });
            },
            onEachFeature: (feature, layer) => {
                const p = feature.properties || {};
                const conflictName = p.conflict_name || 'Neznan konflikt';
                const country = p.country || 'Neznana država';
                const yearStr = p.year || year;

                let popupHtml = `<strong>${conflictName}</strong><br/>`;
                popupHtml += `Država: ${country}<br/>`;
                popupHtml += `Leto: ${yearStr}<br/>`;

                if (p.best != null) {
                    popupHtml += `Ocena žrtev: ${p.best}<br/>`;
                }
                if (p.type_of_violence != null) {
                    popupHtml += `Tip vojne: ${p.type_of_violence}<br/>`;
                }

                layer.bindPopup(popupHtml);
            }
        });

        // dodaj vse v cluster group
        conflictClusters.addLayer(conflictsLayer);

        //fit samo pri prvem loadu, ne ob vsakem premiku sliderja
        if (doFit && geojson.features && geojson.features.length > 0) {
            const bounds = conflictClusters.getBounds();
            if (bounds.isValid()) {
                map.fitBounds(bounds, { maxZoom: 5 });
            }
        }

    } catch (err) {
        console.error('Napaka pri nalaganju konfliktov:', err);
    }
}

let debounceTimer = null;
let firstLoad = true;

// event za slider
yearSlider.addEventListener('input', () => {
    const year = yearSlider.value;
    yearText.textContent = year;
    loadConflicts(year);

    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
        loadConflicts(year, firstLoad);
        firstLoad = false;
    }, 200);
});

const legend = L.control({ position: 'bottomleft' });

legend.onAdd = function (map) {
    const div = L.DomUtil.create('div', 'legend');
    div.innerHTML = `
      <div><span class="legend-box" style="background:#4da6ff"></span> 0–24 žrtev</div>
      <div><span class="legend-box" style="background:#ffa500"></span> 25–99 žrtev</div>
      <div><span class="legend-box" style="background:#ff0000"></span> 100+ žrtev</div>
    `;
    return div;
};

legend.addTo(map);


// inicialni load - fit bounds
loadConflicts(yearSlider.value, true);
