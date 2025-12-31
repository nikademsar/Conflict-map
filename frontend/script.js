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

let countriesLayer = null; // polygons layer (all years from API)

// =======================
// Slider + year bubble + play
// =======================
const yearSlider = document.getElementById("year");
const yearText = document.getElementById("year-value");
const yearBubble = document.getElementById("year-bubble");
const playBtn = document.getElementById("play-btn");

let isPlaying = false;
let playTimer = null;

// hitrost animacije (ms na leto)
const PLAY_INTERVAL_MS = 2000;

// prepreči prekrivanje fetch klicev, ko interval teče
let isLoadingYear = false;

function positionYearBubble() {
  if (!yearBubble || !yearSlider) return;

  const min = Number(yearSlider.min);
  const max = Number(yearSlider.max);
  const val = Number(yearSlider.value);

  const percent = (val - min) / (max - min); // 0..1
  const sliderWidth = yearSlider.offsetWidth;

  const bubbleWidth = yearBubble.offsetWidth || 44;
  const x = percent * sliderWidth - bubbleWidth / 2;

  yearBubble.style.left = `${x}px`;
  yearBubble.textContent = String(val);
}

function setYearUI(y) {
  if (!yearSlider) return;
  yearSlider.value = String(y);
  if (yearText) yearText.textContent = String(y);
  positionYearBubble();
}

function setPlayButtonLabel() {
  if (!playBtn) return;
  playBtn.textContent = isPlaying ? "Pause" : "Play";
}

function stopPlayback() {
  isPlaying = false;
  if (playTimer) {
    clearInterval(playTimer);
    playTimer = null;
  }
  setPlayButtonLabel();
}

async function safeLoadYear(y, doFit = false) {
  if (isLoadingYear) return;
  isLoadingYear = true;
  try {
    await loadByYear(y, doFit);
  } finally {
    isLoadingYear = false;
  }
}

async function stepForwardOneYear() {
  if (!yearSlider) return;

  const max = Number(yearSlider.max);
  let y = Number(yearSlider.value);

  if (y >= max) {
    stopPlayback();
    return;
  }

  y = y + 1;
  setYearUI(y);

  // nalaganje podatkov za novo leto
  await safeLoadYear(y, false);

  // če je uporabnik med nalaganjem pritisnil pause
  if (!isPlaying) return;

  // če smo prišli do konca
  if (y >= max) stopPlayback();
}

function startPlayback() {
  if (!yearSlider) return;

  const max = Number(yearSlider.max);
  const y = Number(yearSlider.value);
  if (y >= max) return;

  isPlaying = true;
  setPlayButtonLabel();

  playTimer = setInterval(() => {
    // interval callback ne more biti await
    stepForwardOneYear();
  }, PLAY_INTERVAL_MS);
}

function togglePlayback() {
  if (isPlaying) stopPlayback();
  else startPlayback();
}

// Slider events
if (yearSlider) {
  yearSlider.addEventListener("input", () => {
    if (yearText) yearText.textContent = yearSlider.value;
    positionYearBubble();

    // če uporabnik ročno premika, ustavi animacijo
    if (isPlaying) stopPlayback();
  });

  yearSlider.addEventListener("change", () => {
    const y = Number(yearSlider.value);

    // če uporabnik ročno spremeni leto, ustavi animacijo
    if (isPlaying) stopPlayback();

    safeLoadYear(y, false);
  });

  window.addEventListener("resize", () => positionYearBubble());
}

// Play button event
if (playBtn) {
  playBtn.addEventListener("click", () => togglePlayback());
  setPlayButtonLabel();
}

// =======================
// Utils
// =======================
function safe(v) {
  if (v == null) return "";
  return String(v)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function decode(dict, code) {
  if (code == null) return "";
  const k = Number(code);
  if (!Number.isFinite(k)) return safe(code);
  return dict[k] ?? safe(code);
}

function fmtDateISO(v) {
  if (!v) return "";
  return safe(v);
}

function popupRow(label, value) {
  if (value == null || value === "") return "";
  return `<div class="row"><div class="k">${safe(label)}</div><div class="v">${safe(
    value
  )}</div></div>`;
}

function popupSection(title, rowsHtml) {
  if (!rowsHtml) return "";
  return `<div class="section"><div class="t">${safe(title)}</div>${rowsHtml}</div>`;
}

// =======================
// Dictionaries (UCDP codes)
// =======================

// GED (Event) codes
const GED_TYPE_OF_VIOLENCE = {
  1: "State-based conflict",
  2: "Non-state conflict",
  3: "One-sided violence",
};

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
  3: "Territory and government",
};

// =======================
// Popups
// =======================
function buildCountryPopup(p) {
  const header = `<div class="popup-header">
    <div class="h1">${safe(p.country_name ?? "Country")}</div>
    <div class="h2">Year: ${safe(p.year ?? "")}</div>
  </div>`;

  const base =
    popupRow("Country", p.country_name) +
    popupRow("ISO3", p.iso3) +
    popupRow("Year", p.year);

  const maxI = Number(p.intensity_level_max ?? p.intensity_level ?? 0);

  const acd =
    popupRow("Intensity (max)", decode(ACD_INTENSITY_LEVEL, maxI)) +
    popupRow("Type of conflict", decode(ACD_TYPE_OF_CONFLICT, p.type_of_conflict)) +
    popupRow("Incompatibility", decode(ACD_INCOMPATIBILITY, p.incompatibility)) +
    popupRow("Conflicts count (in year)", p.conflicts_count) +
    popupRow(
      "Conflict IDs",
      Array.isArray(p.conflict_ids) ? p.conflict_ids.join(", ") : p.conflict_id
    );

  return `
    ${header}
    ${popupSection("Base", base)}
    ${popupSection("ACD (annual conflict)", acd)}
  `;
}

function buildEventPopup(p) {
  const header = `<div class="popup-header">
    <div class="h1">${safe(p.dyad_name ?? p.conflict_name ?? "Event")}</div>
    <div class="h2">Event ID: ${safe(p.id ?? "")} · Year: ${safe(p.year ?? "")}</div>
  </div>`;

  const ids =
    popupRow("Conflict ID (conflict_new_id)", p.conflict_new_id ?? p.conflict_id) +
    popupRow("Dyad ID (dyad_new_id)", p.dyad_new_id) +
    popupRow("Type of violence", decode(GED_TYPE_OF_VIOLENCE, p.type_of_violence));

  const loc =
    popupRow("Country", p.country) +
    popupRow("ADM-1", p.adm_1) +
    popupRow("ADM-2", p.adm_2) +
    popupRow("Where (standardized)", p.where_coordinates) +
    popupRow("Latitude", p.latitude) +
    popupRow("Longitude", p.longitude);

  const time = popupRow("Date start", fmtDateISO(p.date_start)) + popupRow("Date end", fmtDateISO(p.date_end));

  const fat =
    popupRow("Best estimate fatalities", p.best) +
    popupRow("Low estimate", p.low) +
    popupRow("High estimate", p.high);

  return `
    ${header}
    ${popupSection("IDs", ids)}
    ${popupSection("Location", loc)}
    ${popupSection("Time", time)}
    ${popupSection("Fatalities", fat)}
  `;
}

// =======================
// Styling helpers
// =======================
function colorForBest(best) {
  if (best == null || isNaN(best)) return "#888888";
  if (best < 25) return "#4da6ff";
  if (best < 100) return "#ffa500";
  return "#ff0000";
}

function radiusForBest(best) {
  if (best == null || isNaN(best)) return 6;
  if (best < 25) return 6;
  if (best < 100) return 8;
  return 10;
}

function countryFillForIntensity(maxIntensity) {
  if (maxIntensity >= 2) return { fillColor: "#ff0000", fillOpacity: 0.45 };
  if (maxIntensity >= 1) return { fillColor: "#ffa500", fillOpacity: 0.30 };
  return { fillColor: "#888888", fillOpacity: 0.0 };
}

// =======================
// Clear helpers
// =======================
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

    // osveži samo točke
    clearPoints();

    const layer = L.geoJSON(geojson, {
      pointToLayer: (feature, latlng) => {
        const p = feature.properties || {};
        const best = Number(p.best);
        return L.circleMarker(latlng, {
          radius: radiusForBest(best),
          color: "#222222",
          weight: 1,
          fillColor: colorForBest(best),
          fillOpacity: 0.85,
        });
      },
      onEachFeature: (feature, layer) => {
        const p = feature.properties || {};
        layer.bindPopup(buildEventPopup(p), { maxWidth: 420 });
      },
    });

    conflictClusters.addLayer(layer);

    if (doFit) {
      const b = layer.getBounds();
      if (b.isValid()) map.fitBounds(b, { maxZoom: 4 });
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

    // osveži samo poligone
    clearCountriesLayer();

    countriesLayer = L.geoJSON(geojson, {
      style: (feature) => {
        const p = feature.properties || {};
        const maxI = Number(p.intensity_level_max ?? p.intensity_level ?? 0);
        const s = countryFillForIntensity(maxI);

        return {
          weight: 1,
          color: "#222222",
          fillColor: s.fillColor,
          fillOpacity: s.fillOpacity,
        };
      },
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
// Year switch logic
// =======================
async function loadByYear(year, doFit = false) {
  if (year < 1989) {
    clearPoints();
    await loadConflictCountries(year, doFit);
    return;
  }

  await loadConflictCountries(year, false);
  await loadConflictEvents(year, doFit);
}

// =======================
// Legend
// =======================
const legend = L.control({ position: "bottomright" });
legend.onAdd = function () {
  const div = L.DomUtil.create("div", "legend");
  div.innerHTML = `
    <div style="margin-bottom:6px;font-weight:700;">Events (fatalities)</div>
    <div><span class="legend-box" style="background:#4da6ff"></span> 0–24</div>
    <div><span class="legend-box" style="background:#ffa500"></span> 25–99</div>
    <div><span class="legend-box" style="background:#ff0000"></span> 100+</div>
    <div style="margin:10px 0 6px;font-weight:700;">Countries (ACD intensity)</div>
    <div><span class="legend-box" style="background:#ffa500"></span> Intensity 1</div>
    <div><span class="legend-box" style="background:#ff0000"></span> Intensity 2</div>
  `;
  return div;
};
legend.addTo(map);

// =======================
// Initial load
// =======================
if (yearText && yearSlider) {
  yearText.textContent = yearSlider.value;
}
positionYearBubble();

if (yearSlider) {
  safeLoadYear(Number(yearSlider.value), true);
}
