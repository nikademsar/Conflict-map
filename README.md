# Conflict Map

Interaktivna **prostorsko-časovna vizualizacija oboroženih konfliktov na svetovni ravni**, ki temelji na **uradnih podatkih Uppsala Conflict Data Program (UCDP)** in uporablja **hibridni pristop (API + lokalni prostorski viri)**.

Projekt korektno ločuje obdobja:

* **1946–1988** – brez georeferenciranih dogodkov
* **1989–danes** – z georeferenciranimi dogodki

in za leta **1989+** prikazuje **oboje**:

* **točke dogodkov (GED)** in
* **obarvane poligone držav v konfliktu (ACD + Natural Earth)**, kjer je **barva odvisna od intenzitete konflikta**.

![Izgled aplikacije](https://github.com/nikademsar/Conflict-map/blob/master/images/izgled1.png?raw=true)
![Izgled aplikacije](https://github.com/nikademsar/Conflict-map/blob/master/images/izgled5.png?raw=true)
---

## Opis projekta

Projekt prikazuje oborožene konflikte skozi čas z uporabo interaktivnega zemljevida in letnega drsnika. Cilji vizualizacije so:

* prikazati **katere države so bile v konfliktu v posameznem letu** (poligoni držav),
* prikazati **kje so se konflikti dejansko dogajali**, ko so na voljo georeferencirani dogodki (točke GED),
* prikazati **intenzivnost konfliktov** in osnovne lastnosti (akterji, tip konflikta, nezdružljivost).

---

## Metodološka osnova (ključna)

### 1946–1988

* na voljo je samo **UCDP/PRIO Armed Conflict Dataset (ACD)**,
* **ni GED dogodkov in koordinat**,
* zemljevid prikazuje **poligone držav v konfliktu**
  (ACD + Natural Earth).

### 1989–danes

* na voljo sta **ACD + UCDP Georeferenced Event Dataset (GED)**,
* GED vsebuje dogodke z **latitude/longitude**,
* zemljevid prikazuje:

  * **poligone držav v konfliktu** (obarvane po ACD intenziteti),
  * **točke dogodkov** (GED), združene z *marker clustering*.

---

## Podatkovni viri (uradni)

### Glavna vira (dejansko uporabljena)

* **UCDP/PRIO Armed Conflict Dataset (Annual, 1946–present)**
  dostop prek **UCDP API (`ucdpprioconflict`)**
  [https://ucdp.uu.se/apidocs/](https://ucdp.uu.se/apidocs/)

* **UCDP Georeferenced Event Dataset – Global (1989–present)**
  dostop prek **UCDP API (`gedevents`)**
  [https://ucdp.uu.se/apidocs/](https://ucdp.uu.se/apidocs/)

> Opomba: Projekt **ne uporablja več lokalnih CSV datotek UCDP**, temveč podatke pridobiva **programsko prek API**, z verzioniranimi in ponovljivimi poizvedbami.

### Prostorski vir

* **Natural Earth – Admin 0 Countries (poligoni držav)**
  `ne_110m_admin_0_countries.geojson`
  [https://www.naturalearthdata.com/](https://www.naturalearthdata.com/)

### Dodatni pomožni vir

* **Gleditsch & Ward country codes (GWNo)**
  uporabljeno za preslikavo `gwno_loc` → država
  (preneseno in shranjeno lokalno kot `gw_states.csv`)

---

## Arhitektura sistema

```
data/
├── raw/
│   └── ne_110m_admin_0_countries.geojson   # Natural Earth poligoni držav
├── raw_api/
│   ├── gw_states.csv                       # GWNo → ime države
│   ├── gedevents/                          # UCDP GED (API dump, paginiran)
│   └── ucdpprioconflict/                   # UCDP ACD (API dump, paginiran)
├── processed/
│   ├── conflicts_events.geojson            # GED točke (1989+)
│   └── conflict_countries.geojson          # ACD + države (1946+)
backend/
├── etl/
│   ├── download_gwno_states.py              # GWNo helper (enkratni prenos)
│   ├── fetch_ucdp_api.py                    # UCDP API → raw_api
│   └── process_data_api.py                  # raw_api → processed GeoJSON
├── elastic/
│   ├── bulk_load.py                         # nalaganje GED v ES
│   ├── bulk_load_countries.py               # nalaganje držav v ES
│   ├── create_index.json
│   └── create_index_countries.json
├── api/
│   └── app.py                               # FastAPI (ES + opcijski Redis)
frontend/
├── index.html
├── script.js
└── style.css
run.bat                                      # celoten pipeline (Windows)
```

---

## Funkcionalnosti

* letni drsnik (1946–2024),
* **Play / Pause animacija** skozi leta,
* samodejno preklapljanje vizualizacije:

  * **< 1989:** samo **poligoni držav**
  * **≥ 1989:** **poligoni + točke GED**
* barvanje držav glede na **ACD intensity_level**,
* agregacija konfliktov po državi in letu:

  * maksimalna intenziteta,
  * število konfliktov,
* interaktivni pop-up za države in dogodke,
* marker clustering za GED dogodke,
* legenda za:

  * intenziteto konfliktov (države),
  * fatalitete dogodkov (GED).

---

## Tehnologije

* **Python** (pandas, geopandas, shapely, requests)
* **Elasticsearch 8.x**

  * `geo_shape` za poligone držav
  * `geo_shape` / `geo_point` za dogodke
* **FastAPI**
* **Leaflet**
* **Docker / Docker Compose**
* (opcijsko) **Redis** za cache odgovorov API po letu

---

## Namestitev

### Zahteve

* Python **3.10+**
* Docker + Docker Compose
* Git

### Python knjižnice

```bash
pip install -r requirements.txt
```

> Priporočilo: `elasticsearch==8.x` (client mora ustrezati verziji ES v Dockerju).

---

## Zagon sistema (priporočeno)

### Windows – celoten pipeline

```bat
run.bat
```

Skript avtomatsko:

1. zažene Docker (Elasticsearch, Kibana, Redis),
2. pridobi GWNo seznam (če manjka),
3. prenese UCDP podatke prek API (z resume podporo),
4. izvede ETL,
5. naloži podatke v Elasticsearch,
6. zažene FastAPI backend.

---

## Ročni zagon (po korakih)

### 1. Docker

```bash
docker-compose up -d
```

* Kibana: [http://localhost:5601](http://localhost:5601)
* Elasticsearch: [http://localhost:9200](http://localhost:9200)

---

### 2. ETL – prenos in obdelava

```bash
python backend/etl/fetch_ucdp_api.py --resume
python backend/etl/process_data_api.py
```

Rezultat:

* `conflicts_events.geojson`
* `conflict_countries.geojson`

---

### 3. Elasticsearch ingest

```bash
python backend/elastic/bulk_load.py
python backend/elastic/bulk_load_countries.py
```

---

### 4. API

```bash
uvicorn backend.api.app:app --reload --port 8000
```

Endpointi:

* `GET /conflicts?year=YYYY`
* `GET /conflict-countries?year=YYYY`
* `GET /health`

---

### 5. Frontend

Odpri:

```
frontend/index.html
```

---

## Redis cache (opcijsko)

* cache po letu (`conflicts:year=YYYY`, `conflict_countries:year=YYYY`)
* nastavljiv TTL (`REDIS_TTL_SECONDS`)
* priporočeno: po ponovnem ETL-ju počisti cache

---

## Opomba o metodologiji

Projekt je zasnovan skladno z metodologijo UCDP:

* **ACD** se uporablja za letni obstoj in intenziteto konfliktov,
* **GED** se uporablja izključno tam, kjer so dogodki prostorsko definirani,
* za države se uporablja **Natural Earth**, saj UCDP ne ponuja poligonov.
