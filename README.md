# Conflict Map

Interaktivna prostorsko-časovna vizualizacija oboroženih konfliktov na svetovni ravni, ki temelji na **uradnih podatkih Uppsala Conflict Data Program (UCDP)**.

Projekt korektno ločuje obdobja **brez georeferenciranih dogodkov (1946–1988)** in **obdobje z georeferenciranimi dogodki (1989–danes)**, pri čemer za leta **1989+** prikazuje **oboje**:

* **točke dogodkov (GED)** in
* **obarvane poligone držav v konfliktu (ACD + Natural Earth)**, kjer je **moč/barva odvisna od intenzitete konflikta**.

---

## Opis projekta

Projekt prikazuje oborožene konflikte skozi čas z uporabo zemljevida in letnega drsnika.
Cilj je prikazati:

* **katere države so bile v konfliktu v posameznem letu** (poligoni držav),
* **kje so se konflikti dejansko dogajali**, ko so na voljo prostorski dogodki (točke GED),
* **intenzivnost konfliktov** in osnovne lastnosti (akterji, tip konflikta).

### Metodološka osnova (ključna)

* **1946–1988**

  * na voljo je **le UCDP/PRIO Armed Conflict Dataset (ACD)**
  * **ni koordinat GED dogodkov**
  * na zemljevidu se prikazujejo **poligoni držav**, ki so bile v konfliktu (ACD + Natural Earth)

* **1989–danes**

  * ACD + **UCDP Georeferenced Event Dataset (GED)**
  * na voljo so **dogodki z latitude/longitude**
  * na zemljevidu se prikazujejo:

    * **poligoni držav v konfliktu** (obarvani po intenziteti ACD), in
    * **točke dogodkov** (GED), združene z marker clustering

---

## Podatkovni viri (uradni)

### Glavna vira (dejansko uporabljena)

* **UCDP/PRIO Armed Conflict Dataset (Annual, 1946–present)**
  `ucdp_prio_acd.csv`
  [https://ucdp.uu.se/downloads/index.html#armedconflict](https://ucdp.uu.se/downloads/index.html#armedconflict)

* **UCDP Georeferenced Event Dataset – Global (1989–present)**
  `ucdp_ged.csv`
  [https://ucdp.uu.se/downloads/index.html#ged_global](https://ucdp.uu.se/downloads/index.html#ged_global)

### Dodatni prostorski vir

* **Natural Earth – Admin 0 Countries (poligoni držav)**
  `ne_110m_admin_0_countries.geojson`
  [https://github.com/nvkelso/natural-earth-vector/blob/master/geojson/ne_110m_admin_0_countries.geojson](https://github.com/nvkelso/natural-earth-vector/blob/master/geojson/ne_110m_admin_0_countries.geojson)

### Dokumentacija

* UCDP/PRIO ACD Codebook
  [https://ucdp.uu.se/downloads/replication_data/2023_ucdp-prio-acd-231.pdf](https://ucdp.uu.se/downloads/replication_data/2023_ucdp-prio-acd-231.pdf)

* UCDP GED Codebook
  [https://ucdp.uu.se/downloads/replication_data/2023_ucdp_ged_codebook.pdf](https://ucdp.uu.se/downloads/replication_data/2023_ucdp_ged_codebook.pdf)

---

## Arhitektura sistema

```
data/
├── raw/
│   ├── ucdp_prio_acd.csv
│   ├── ucdp_ged.csv
│   └── ne_110m_admin_0_countries.geojson
├── processed/
│   ├── conflicts_events.geojson         # točke (GED, 1989+)
│   └── conflict_countries.geojson       # poligoni držav (ACD+NE, 1946+)
backend/
├── etl/
│   └── process_data.py
├── elastic/
│   ├── bulk_load.py
│   ├── bulk_load_countries.py
│   ├── create_index.json
│   └── create_index_countries.json
├── api/
│   └── app.py
frontend/
├── index.html
├── script.js
└── style.css
```

---

## Funkcionalnosti

* letni drsnik (1946–2024),
* **Play/Pause animacija** skozi leta (premika slider od trenutnega leta do konca),
* samodejno preklapljanje vizualizacije:

  * **< 1989:** samo **poligoni držav v konfliktu**
  * **≥ 1989:** **poligoni držav v konfliktu + točke GED dogodkov**
* barvanje držav glede na **intenziteto konflikta (ACD intensity_level)**,
* agregacija držav po letu:

  * za državo v letu se izračuna **maksimalna intenziteta** (npr. `intensity_level_max`)
  * shrani se tudi `conflicts_count` in seznam `conflict_ids` (odvisno od implementacije v API),
* interaktivni pop-up za države in dogodke,
* združevanje točk (marker clustering),
* legenda:

  * razreditev točk po fatalities (best),
  * razreditev držav po ACD intenziteti.

---

## Tehnologije

* **Python** (pandas, geopandas, shapely)
* **Elasticsearch**

  * `geo_shape` za poligone držav
  * `geo_shape` / `geo_point` za dogodke (odvisno od mappinga)
* **FastAPI**
* **Leaflet**
* **Docker / Docker Compose**
* (opcijsko) **Redis** za cache API odgovorov po letu

---

## Namestitev

### Zahteve

* Python 3.10+
* Docker + Docker Compose
* Git

### Namestitev Python knjižnic

```bash
pip install -r requirements.txt
```

Če uporabljaš Redis cache v API:

* dodaj `redis` knjižnico v `requirements.txt` (npr. `redis>=5.0.0`).

---

## Zagon sistema

### 1. Zagon Elasticsearch in Kibane (in opcijsko Redis)

```bash
docker-compose up -d
```

Kibana:

```
http://localhost:5601
```

Opcijsko (če dodaš Redis v compose), Redis port:

```
localhost:6379
```

---

### 2. ETL – priprava podatkov

```bash
python backend/etl/process_data.py
```

Rezultat:

* `conflicts_events.geojson` (GED, 1989+)
* `conflict_countries.geojson` (ACD + države, 1946+)

---

### 3. Nalaganje v Elasticsearch

**Dogodki (točke):**

```bash
python backend/elastic/bulk_load.py
```

**Države (poligoni):**

```bash
python backend/elastic/bulk_load_countries.py
```

---

### 4. Zagon API-ja

```bash
uvicorn backend.api.app:app --reload --port 8000
```

API endpointi:

* dogodki:

```
GET /conflicts?year=YYYY
```

* države:

```
GET /conflict-countries?year=YYYY
```

Dodatno (če je vključeno v `app.py`):

* health:

```
GET /health
```

* (opcijsko) brisanje cache:

```
POST /cache/clear
```

---

### 5. Zagon frontenda

Odpri:

```
frontend/index.html
```

---

## Redis cache

Za hitrejše nalaganje let, lahko API kešira odgovore po letu v Redis:

* ključ (primer): `conflicts:year=YYYY:size=...` in `conflict_countries:year=YYYY:size=...`
* TTL nastavljiv (npr. `REDIS_TTL_SECONDS`)

Priporočeno: po ponovnem nalaganju podatkov v Elasticsearch počisti cache (npr. `POST /cache/clear`), če je endpoint implementiran.

---

## Poročila

Povezava do uvodnega poročila:
[https://unilj-my.sharepoint.com/:w:/g/personal/nd3657_student_uni-lj_si/ESj02Kf7p2VKuE42LhPjx_MBQtv_fK4WkLZBLpFIDGQlMA](https://unilj-my.sharepoint.com/:w:/g/personal/nd3657_student_uni-lj_si/ESj02Kf7p2VKuE42LhPjx_MBQtv_fK4WkLZBLpFIDGQlMA)
