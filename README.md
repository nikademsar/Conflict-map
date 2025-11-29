# Conflict Map

Interaktivna vizualizacija oboroženih konfliktov od leta 1900 do danes.

## Opis projekta

Projekt prikazuje svetovne vojne in oborožene konflikte skozi čas z uporabo prostorsko-časovne vizualizacije. Cilj je jasno predstaviti, kje in kdaj so potekali konflikti, kakšna je bila njihova intenzivnost ter kako se je fronta premikala. Sistem vključuje tudi prikaz kakovosti podatkov in prekrivanja konfliktov, ki so potekali istočasno.

Glavne značilnosti:

* dinamični zemljevid, ki se spreminja glede na izbrano leto (1900–danes),
* obarvana konfliktna območja glede na vrsto konflikta in intenziteto žrtev,
* prikaz premikanja front,
* prikaz sočasnih konfliktov z več plastmi,
* interaktivni prikaz podatkov posameznega dogodka,
* filtri po vrsti konflikta, regiji in številu žrtev.

Informacijsko okno prikazuje:

* države, vključene v konflikt,
* število žrtev v izbranem letu,
* skupno število žrtev,
* kakovost podatkov,
* kratek opis poteka konflikta.

Uporabljeni uradni podatkovni viri:

* **UCDP – Uppsala Conflict Data Program**
* **ACLED – Armed Conflict Location & Event Data**
* **Correlates of War (COW) Project**
* **Human Security Report Project**
* **United Nations Statistical Data**

Tehnologije:
* **Elasticsearch** (geo_point)
* **Python** (pandas, geopandas, shapely)
* **FastAPI**
* **Leaflet**
* **Docker / Docker Compose**

## Namestitev

Zahteve:

* Docker + Docker Compose
* Python 3.10+
* Git

Namestitev Python knjižnic:

```bash
pip install pandas numpy requests beautifulsoup4 lxml python-dateutil geopandas shapely pyproj geojson folium geopy elasticsearch elastic-transport elasticsearch-dsl fastapi uvicorn plotly dash dash-leaflet branca matplotlib seaborn pillow imageio moviepy
```

---

# Zagon sistema

## 1. Zaženi Elasticsearch in Kibano

```bash
docker-compose up -d
```

Ko se container za Kibano zažene, jo odpreš v brskalniku:

```
http://localhost:5601
```

V Kibani lahko:

* preveriš stanje indeksa `conflicts`,
* ustvariš vizualizacije,
* dodaš **Maps Layer → Documents → Index: conflicts**,
* izvedeš iskanja z DevTools (`GET conflicts/_search`).

---

## 2. Ustvari indeks in naloži podatke

```bash
python backend/elastic/bulk_load.py
```

Ta skripta:

* ustvari indeks `conflicts` (če še ne obstaja),
* normalizira datume in odstrani neveljavne vrednosti,
* pretvori geokoordinate v `geo_point`,
* naloži podatke v Elasticsearch.

---

## 3. Zagon API-ja (FastAPI)

```bash
uvicorn backend.api.app:app --reload --port 8000
```

API endpoint:

```
GET /conflicts?year=YYYY
```

Vrne GeoJSON, primer:

```
{
  "type": "FeatureCollection",
  "features": ...
}
```

---

## 4. Zagon frontenda

Odpri datoteko:

```
frontend/index.html
```

Frontend uporablja Leaflet in prikazuje točke konfliktov glede na izbrano leto.

---

# Test_all – avtomatski zagon celotnega sistema

Projekt vključuje skripto **test_all.py**, ki:

1. preveri, ali obstaja `ucdp.csv`,
2. preveri, ali so nameščeni vsi moduli,
3. zažene ETL obdelavo,
4. zažene Docker Compose (Elasticsearch + Kibana),
5. počaka, da se Elasticsearch inicializira,
6. izvede **bulk_load** v indeks,
7. izpiše uspešnost nalaganja.

Zagon:

```bash
python test_all.py
```

Ta ukaz **celoten sistem pripravi v enem koraku**.

---

## Poročila

[Povezava do uvodnega poročila](https://unilj-my.sharepoint.com/:w:/g/personal/nd3657_student_uni-lj_si/ESj02Kf7p2VKuE42LhPjx_MBQtv_fK4WkLZBLpFIDGQlMA?e=msJlOM) 
