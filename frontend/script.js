// =======================
// Map init
// =======================
const map = L.map("map", { zoomControl: false }).setView([20, 0], 2);

L.control.zoom({ position: "topright" }).addTo(map);

L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 18,
  attribution: "&copy; OpenStreetMap contributors",
}).addTo(map);

// =======================
// Layers
// =======================
const conflictClusters = L.markerClusterGroup({
  disableClusteringAtZoom: 5,
  maxClusterRadius: 40,
});
map.addLayer(conflictClusters);

let countriesLayer = null; // polygons layer (<1989)

// =======================
// Slider + year bubble
// =======================
const yearSlider = document.getElementById("year");
const yearText = document.getElementById("year-value");
const yearBubble = document.getElementById("year-bubble");

function positionYearBubble() {
  if (!yearBubble || !yearSlider) return;

  const min = Number(yearSlider.min);
  const max = Number(yearSlider.max);
  const val = Number(yearSlider.value);

  const percent = (val - min) / (max - min); // 0..1
  const sliderWidth = yearSlider.offsetWidth;

  // must match CSS thumb width (#year::-webkit-slider-thumb width)
  const thumbWidth = 16;

  const x = percent * (sliderWidth - thumbWidth) + thumbWidth / 2;
  yearBubble.style.left = `${x}px`;
}

window.addEventListener("resize", positionYearBubble);

// =======================
// Codebook decoders (UCDP)
// =======================
// ACD (Annual) codes
const ACD_TYPE_OF_CONFLICT = {
  1: "Extrasystemic",
  2: "Interstate",
  3: "Intrastate",
  4: "Internationalized intrastate",
};

const ACD_INTENSITY_LEVEL = {
  1: "Minor (25–999 battle-related deaths in year)",
  2: "War (≥1,000 battle-related deaths in year)",
};

const ACD_INCOMPATIBILITY = {
  1: "Territory",
  2: "Government",
  3: "Government and territory",
};

// GED (Event) codes
const GED_TYPE_OF_VIOLENCE = {
  1: "State-based conflict",
  2: "Non-state conflict",
  3: "One-sided violence",
};

const GED_EVENT_CLARITY = {
  1: "High (individual incident identifiable)",
  2: "Lower (aggregated totals; not separable into single incidents)",
};

const GED_DATE_PREC = {
  1: "Exact date known",
  2: "Known within 2–6 day range",
  3: "Only week known",
  4: "Only month / 8–30 day range known",
  5: "Range >1 month and ≤1 calendar year",
};

// =======================
// Popup helpers (UI)
// =======================
function safe(v) {
  return v === null || v === undefined || v === "" ? "—" : String(v);
}

function decode(map, v) {
  if (v === null || v === undefined || v === "") return "—";
  const k = Number(v);
  return map[k] ? `${k} — ${map[k]}` : String(v);
}

function fmtDateISO(d) {
  if (!d) return "—";
  return String(d).slice(0, 10);
}

function popupRow(label, value) {
  return `<div class="row"><span class="k">${label}</span><span class="v">${value}</span></div>`;
}

function popupSection(title, innerHtml) {
  return `<div class="section"><div class="title">${title}</div>${innerHtml}</div>`;
}

function buildCountryPopup(p) {
  const header = `<div class="popup-header">
    <div class="h1">${safe(p.country_name ?? p.location ?? "Country")}</div>
    <div class="h2">Conflict ID: ${safe(p.conflict_id)} · Year: ${safe(p.year)}</div>
  </div>`;

  const parties =
    popupRow("Side A", safe(p.side_a)) +
    popupRow("Side B", safe(p.side_b));

  const classification =
    popupRow("Type of conflict", decode(ACD_TYPE_OF_CONFLICT, p.type_of_conflict)) +
    popupRow("Intensity level", decode(ACD_INTENSITY_LEVEL, p.intensity_level)) +
    popupRow("Incompatibility", decode(ACD_INCOMPATIBILITY, p.incompatibility)) +
    popupRow("Territory name", safe(p.territory_name));

  const meta =
    popupRow("Region", safe(p.region)) +
    popupRow("Dataset version", safe(p.version));

  return (
    `<div class="popup">` +
    header +
    popupSection("Parties", parties) +
    popupSection("Classification (UCDP/PRIO ACD)", classification) +
    popupSection("Metadata", meta) +
    `</div>`
  );
}

function buildEventPopup(p) {
  const header = `<div class="popup-header">
    <div class="h1">${safe(p.dyad_name ?? p.conflict_name ?? "Event")}</div>
    <div class="h2">Event ID: ${safe(p.id)} · Year: ${safe(p.year)}</div>
  </div>`;

  const ids =
    popupRow("Conflict ID (conflict_new_id)", safe(p.conflict_new_id ?? p.conflict_id)) +
    popupRow("Dyad ID (dyad_new_id)", safe(p.dyad_new_id)) +
    popupRow("Type of violence", decode(GED_TYPE_OF_VIOLENCE, p.type_of_violence));

  const loc =
    popupRow("Country", safe(p.country)) +
    popupRow("ADM-1", safe(p.adm_1)) +
    popupRow("ADM-2", safe(p.adm_2)) +
    popupRow("Where (standardized)", safe(p.where_coordinates)) +
    popupRow("Latitude", safe(p.latitude)) +
    popupRow("Longitude", safe(p.longitude));

  const time =
    popupRow("Date start", fmtDateISO(p.date_start)) +
    popupRow("Date end", fmtDateISO(p.date_end)) +
    popupRow("Date precision", decode(GED_DATE_PREC, p.date_prec));

  const deaths =
    popupRow("Total fatalities", safe(p.best)) +
    popupRow("Deaths A", safe(p.deaths_a)) +
    popupRow("Deaths B", safe(p.deaths_b)) +
    popupRow("Deaths civilians", safe(p.deaths_civilians)) +
    popupRow("Deaths unknown", safe(p.deaths_unknown));

  return (
    `<div class="popup">` +
    header +
    popupSection("Identifiers (UCDP GED)", ids) +
    popupSection("Location", loc) +
    popupSection("Time", time) +
    popupSection("Fatalities", deaths) +
    `</div>`
  );
}

// =======================
// Helpers
// =======================
function colorForBest(best) {
  if (best == null || isNaN(best)) return "#888888";
  if (best < 25) return "#4da6ff";
  if (best < 100) return "#ffa500";
  return "#ff0000";
}

function clearCountriesLayer() {
  if (countriesLayer) {
    map.removeLayer(countriesLayer);
    countriesLayer = null;
  }
}

function clearPoints() {
  conflictClusters.clearLayers();
}

// =======================
// Loaders
// =======================
async function loadConflictEvents(year, doFit = false) {
  const url = `http://localhost:8000/conflicts?year=${year}`;

  try {
    const response = await fetch(url);
    if (!response.ok) {
      console.error("API error:", response.status, response.statusText);
      return;
    }

    const geojson = await response.json();

    // show points: clear polygons + old points
    clearCountriesLayer();
    clearPoints();

    const eventsLayer = L.geoJSON(geojson, {
      pointToLayer: (feature, latlng) => {
        const p = feature.properties || {};
        const best = p.best ?? p.best_sum ?? null;
        const color = colorForBest(best);

        return L.circleMarker(latlng, {
          radius: 5,
          weight: 1,
          color: color,
          fillColor: color,
          opacity: 1,
          fillOpacity: 0.7,
        });
      },
      onEachFeature: (feature, layer) => {
        const p = feature.properties || {};
        layer.bindPopup(buildEventPopup(p), { maxWidth: 520 });
      },
    });

    conflictClusters.addLayer(eventsLayer);

    if (doFit && geojson.features && geojson.features.length > 0) {
      const bounds = conflictClusters.getBounds();
      if (bounds.isValid()) map.fitBounds(bounds, { maxZoom: 5 });
    }
  } catch (err) {
    console.error("Load events error:", err);
  }
}

async function loadConflictCountries(year, doFit = false) {
  const url = `http://localhost:8000/conflict-countries?year=${year}`;

  try {
    const response = await fetch(url);
    if (!response.ok) {
      console.error("API error:", response.status, response.statusText);
      return;
    }

    const geojson = await response.json();

    // show polygons: clear points + old polygons
    clearPoints();
    clearCountriesLayer();

    countriesLayer = L.geoJSON(geojson, {
      style: () => ({
        weight: 1,
        fillOpacity: 0.25,
      }),
      onEachFeature: (feature, layer) => {
        const p = feature.properties || {};
        layer.bindPopup(buildCountryPopup(p), { maxWidth: 420 });
      },
    }).addTo(map);

    if (doFit) {
      const b = countriesLayer.getBounds();
      if (b.isValid()) map.fitBounds(b, { maxZoom: 4 });
    }
  } catch (err) {
    console.error("Load countries error:", err);
  }
}

// =======================
// Debounce + switching logic
// =======================
let debounceTimer = null;
let firstLoad = true;

function loadByYear(year, doFit = false) {
  if (year < 1989) return loadConflictCountries(year, doFit);
  return loadConflictEvents(year, doFit);
}

yearSlider.addEventListener("input", () => {
  const year = Number(yearSlider.value);

  yearText.textContent = year;
  positionYearBubble();

  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(() => {
    loadByYear(year, firstLoad);
    firstLoad = false;
  }, 200);
});

// =======================
// Legend (optional)
// =======================
const legend = L.control({ position: "bottomleft" });
legend.onAdd = function () {
  const div = L.DomUtil.create("div", "legend");
  div.innerHTML = `
    <div><span class="legend-box" style="background:#4da6ff"></span> 0–24</div>
    <div><span class="legend-box" style="background:#ffa500"></span> 25–99</div>
    <div><span class="legend-box" style="background:#ff0000"></span> 100+</div>
  `;
  return div;
};
legend.addTo(map);

// =======================
// Initial load
// =======================
yearText.textContent = yearSlider.value;
positionYearBubble();
loadByYear(Number(yearSlider.value), true);
