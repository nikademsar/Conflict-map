import os
import json
import math

import pandas as pd
import geopandas as gpd
from shapely.geometry import mapping
from elasticsearch import Elasticsearch, helpers, ApiError


# =======================
# Config
# =======================
GEOJSON_FILE = "data/processed/conflicts_events.geojson"
INDEX_NAME = "conflicts"
ES_HOST = "http://localhost:9200"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INDEX_DEFINITION_FILE = os.path.join(BASE_DIR, "create_index.json")


# =======================
# Index creation (SAFE)
# =======================
def create_index_if_needed(es: Elasticsearch):
    print(f"[INFO] Preverjam/ustvarjam indeks '{INDEX_NAME}'")

    with open(INDEX_DEFINITION_FILE, "r", encoding="utf-8") as f:
        body = json.load(f)

    try:
        es.indices.create(index=INDEX_NAME, body=body)
        print(f"[INFO] Indeks '{INDEX_NAME}' ustvarjen.")
    except ApiError as e:
        # če indeks že obstaja, to NI napaka
        if (
            getattr(e, "error", None) == "resource_already_exists_exception"
            or "resource_already_exists_exception" in str(e)
        ):
            print(f"[INFO] Indeks '{INDEX_NAME}' ze obstaja.")
            return
        # vse ostalo je prava napaka
        raise


# =======================
# Utils
# =======================
def clean_doc_for_es(doc: dict) -> dict:
    """Odstrani NaN / None vrednosti, ki jih ES ne mara."""
    cleaned = {}
    for k, v in doc.items():
        if v is None:
            cleaned[k] = None
            continue
        try:
            if pd.isna(v):
                cleaned[k] = None
                continue
        except Exception:
            pass
        if isinstance(v, float) and math.isnan(v):
            cleaned[k] = None
            continue
        cleaned[k] = v
    return cleaned


# =======================
# Main
# =======================
def main():
    es = Elasticsearch(ES_HOST)

    # 1) indeks + mapping
    create_index_if_needed(es)

    # 2) beri GeoJSON
    print(f"[INFO] Berem GeoJSON: {GEOJSON_FILE}")
    gdf = gpd.read_file(GEOJSON_FILE)

    actions = []

    for _, row in gdf.iterrows():
        # properties brez geometry
        doc = row.drop(labels=["geometry"]).to_dict()

        # geometry → GeoJSON
        geom = row.geometry
        doc["geometry"] = mapping(geom) if geom is not None else None

        # odstrani nepotrebno polje (če obstaja)
        doc.pop("geom_wkt", None)

        doc = clean_doc_for_es(doc)

        doc_id = doc.get("id")
        if doc_id is None:
            # varnostno preskoči (ne bi se smelo zgoditi)
            continue

        actions.append(
            {
                "_index": INDEX_NAME,
                "_id": doc_id,
                "_source": doc,
            }
        )

    # 3) bulk upload
    print("[INFO] Zacenjam bulk upload...")
    success_count = 0
    fail_count = 0

    for ok, item in helpers.streaming_bulk(
        es, actions, raise_on_error=False
    ):
        if ok:
            success_count += 1
        else:
            fail_count += 1
            err = item.get("index", {}).get("error")
            doc_id = item.get("index", {}).get("_id")
            print(f"[ERROR] Dokument {doc_id} neuspesen: {err}")

    print(
        f"[INFO] Bulk upload koncan. "
        f"Uspesno: {success_count}, Neuspesno: {fail_count}"
    )


if __name__ == "__main__":
    main()
