# Conflict Map

Interaktivna prostorsko-časovna vizualizacija oboroženih konfliktov na svetovni ravni, ki temelji na **uradnih podatkih Uppsala Conflict Data Program (UCDP)**.

Projekt korektno ločuje obdobja **brez prostorskih dogodkov (1946–1988)** in **obdobje z natančno georeferenciranimi dogodki (1989–danes)**.

---

## Opis projekta

Projekt prikazuje oborožene konflikte skozi čas z uporabo zemljevida in letnega drsnika.
Cilj je prikazati:

* **katere države so bile v konfliktu v posameznem letu**,
* **kje so se konflikti dejansko dogajali**, ko so na voljo prostorski dogodki,
* **intenzivnost konfliktov** in osnovne lastnosti (akterji, tip konflikta).

### Metodološka osnova (ključna)

* **1946–1988**

  * na voljo je **le UCDP/PRIO Armed Conflict Dataset (ACD)**
  * **ni koordinat**
  * na zemljevidu se prikazujejo **poligoni držav**, ki so bile v konfliktu

* **1989–danes**

  * ACD + **UCDP Georeferenced Event Dataset (GED)**
  * na voljo so **dogodki z latitude/longitude**
  * na zemljevidu se prikazujejo **točke dogodkov**

To je **uradno priporočena in metodološko pravilna uporaba UCDP podatkov**.

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
  uporablja se za prikaz držav v konfliktu pred letom 1989
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
│   ├── conflicts_events.geojson        # točke (1989+)
│   └── conflict_countries.geojson       # poligoni držav (1946+)
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

* letni drsnik (1946–danes),
* samodejno preklapljanje vizualizacije:

  * **poligoni držav** za leta < 1989,
  * **točke dogodkov** za leta ≥ 1989,
* interaktivni pop-up z osnovnimi podatki konflikta,
* združevanje točk (marker clustering),
* legenda intenzivnosti.

---

## Tehnologije

* **Python** (pandas, geopandas, shapely)
* **Elasticsearch**

  * `geo_shape` za poligone držav
  * `geo_point` / `geo_shape` za točke dogodkov
* **FastAPI**
* **Leaflet**
* **Docker / Docker Compose**

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

---

## Zagon sistema

### 1. Zagon Elasticsearch in Kibane

```bash
docker-compose up -d
```

Kibana:

```
http://localhost:5601
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

---

### 5. Zagon frontenda

Odpri:

```
frontend/index.html
```

---

## TODO

* Redis cache za hitrejše nalaganje let
* filtri (tip konflikta, regija, intenzivnost)
* izboljšano barvanje držav glede na intenzivnost
* animacija skozi čas
* izboljšana legenda
* prikaz konfliktov z več državami
* iskanje konfliktov po državi
* dokumentiranje metodoloških omejitev (1946–1988)

---

## Poročila

[Povezava do uvodnega poročila](https://unilj-my.sharepoint.com/:w:/g/personal/nd3657_student_uni-lj_si/ESj02Kf7p2VKuE42LhPjx_MBQtv_fK4WkLZBLpFIDGQlMA)
