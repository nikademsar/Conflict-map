import os
import json
import math

import pandas as pd
import geopandas as gpd
from shapely import wkt
from shapely.geometry import mapping
from elasticsearch import Elasticsearch, helpers

# Poti in konfiguracija
CSV_FILE = "data/raw/ucdp.csv"
GEOJSON_FILE = "data/processed/conflicts.geojson"
INDEX_NAME = "conflicts"
ES_HOST = "http://localhost:9200"

# create_index.json v isti mapi kot bulk_load.py
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INDEX_DEFINITION_FILE = os.path.join(BASE_DIR, "create_index.json")


def sanitize_value(val):
    """Na nivoju DataFrame zamenja klasične NaN/string 'NaN' z None."""
    if pd.isna(val):
        return None
    if isinstance(val, str) and val.strip() == "NaN":
        return None
    return val


def sanitize_geometry(geom):
    """
    Pretvori WKT ali shapely geometrijo v GeoJSON dict ali None.
    To je oblika, ki jo Elasticsearch pričakuje za geo_shape.
    """
    if geom is None:
        return None
    if isinstance(geom, str):
        try:
            geom = wkt.loads(geom)
        except Exception:
            return None
    try:
        # mapping() -> npr. {'type': 'Point', 'coordinates': (lon, lat)}
        return mapping(geom)
    except Exception:
        return None


def create_geojson_from_csv():
    """Prebere CSV, pripravi GeoDataFrame in shrani GeoJSON."""
    print(f"[INFO] Naložimo CSV: {CSV_FILE}")
    df = pd.read_csv(CSV_FILE, low_memory=False)

    # Saniraj NaN in 'NaN' na nivoju stolpcev (posebej za string stolpce)
    for col in df.columns:
        df[col] = df[col].apply(sanitize_value)

    # Pretvori WKT -> shapely geometry
    if "geom_wkt" not in df.columns:
        raise ValueError("CSV ne vsebuje stolpca 'geom_wkt'")

    df["geometry"] = df["geom_wkt"].apply(
        lambda x: wkt.loads(x) if isinstance(x, str) and x.strip() != "" else None
    )

    gdf = gpd.GeoDataFrame(df, geometry="geometry")
    gdf.set_crs(epsg=4326, inplace=True)

    print(f"[INFO] Ustvarjam GeoJSON: {GEOJSON_FILE}")
    gdf.to_file(GEOJSON_FILE, driver="GeoJSON")

    return gdf


def create_index_if_needed(es: Elasticsearch):
    """Če indeks ne obstaja, ga ustvari iz create_index.json."""
    if es.indices.exists(index=INDEX_NAME):
        print(f"[INFO] Indeks {INDEX_NAME} že obstaja.")
        return

    print(f"[INFO] Ustvarjam indeks {INDEX_NAME} iz {INDEX_DEFINITION_FILE}...")
    with open(INDEX_DEFINITION_FILE, "r", encoding="utf-8") as f:
        body = json.load(f)

    es.indices.create(index=INDEX_NAME, body=body)
    print(f"[INFO] Indeks {INDEX_NAME} ustvarjen.")


def clean_doc_for_es(doc: dict) -> dict:
    """
    Na nivoju posameznega dokumenta zamenja vse pandas/float NaN vrednosti z None,
    da se v JSON ne pojavi literal NaN (ki ga ES ne sprejme).
    """
    cleaned = {}
    for k, v in doc.items():
        # že None je OK
        if v is None:
            cleaned[k] = None
            continue

        # pandas NA / numpy NaN / podobno
        try:
            if pd.isna(v):
                cleaned[k] = None
                continue
        except Exception:
            pass

        # dodatna zaščita za gole float NaN
        if isinstance(v, float) and math.isnan(v):
            cleaned[k] = None
            continue

        cleaned[k] = v

    return cleaned


def main():
    es = Elasticsearch(ES_HOST)

    # 1) Indeks (mapping) iz create_index.json
    create_index_if_needed(es)

    # 2) Priprava podatkov iz CSV -> GeoDataFrame
    gdf = create_geojson_from_csv()

    # 3) Priprava bulk akcij
    actions = []
    for _, row in gdf.iterrows():
        doc = row.to_dict()

        # shapely geometry -> GeoJSON dict (za geo_shape)
        doc["geometry"] = sanitize_geometry(doc.get("geometry"))

        # WKT stolpca ne pošiljamo v ES
        doc.pop("geom_wkt", None)

        # Čiščenje NaN vrednosti za ES
        doc = clean_doc_for_es(doc)

        actions.append(
            {
                "_index": INDEX_NAME,
                "_id": doc.get("id"),
                "_source": doc,
            }
        )

    print("[INFO] Začenjam bulk upload...")
    success_count = 0
    fail_count = 0

    # raise_on_error=False: napake logiramo, ne vržemo exception takoj
    for ok, item in helpers.streaming_bulk(es, actions, raise_on_error=False):
        if ok:
            success_count += 1
        else:
            fail_count += 1
            err = item.get("index", {}).get("error")
            doc_id = item.get("index", {}).get("_id")
            print(f"[ERROR] Dokument {doc_id} neuspešen: {err}")

    print(
        f"[INFO] Bulk upload končan. Uspešno: {success_count}, Neuspešno: {fail_count}"
    )

    # Če želiš, da proces pade, če ni bilo uspešnih dokumentov, odkomentiraj:
    # if success_count == 0:
    #     raise RuntimeError("Bulk upload failed for all documents")


if __name__ == "__main__":
    main()
