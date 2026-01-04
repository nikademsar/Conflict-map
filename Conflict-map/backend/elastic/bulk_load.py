import os
import json
import math
import pandas as pd
import geopandas as gpd
from shapely.geometry import mapping
from elasticsearch import Elasticsearch, helpers

GEOJSON_FILE = "data/processed/conflicts_events.geojson"
INDEX_NAME = "conflicts"
ES_HOST = "http://localhost:9200"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INDEX_DEFINITION_FILE = os.path.join(BASE_DIR, "create_index.json")


def create_index_if_needed(es: Elasticsearch):
    if es.indices.exists(index=INDEX_NAME):
        print(f"[INFO] Indeks {INDEX_NAME} ze obstaja.")
        return
    print(f"[INFO] Ustvarjam indeks {INDEX_NAME} iz {INDEX_DEFINITION_FILE}...")
    with open(INDEX_DEFINITION_FILE, "r", encoding="utf-8") as f:
        body = json.load(f)
    es.indices.create(index=INDEX_NAME, body=body)
    print(f"[INFO] Indeks {INDEX_NAME} ustvarjen.")


def clean_doc_for_es(doc: dict) -> dict:
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


def main():
    es = Elasticsearch(ES_HOST)

    # 1) Indeks (mapping) iz create_index.json
    create_index_if_needed(es)

    print(f"[INFO] Berem GeoJSON: {GEOJSON_FILE}")
    gdf = gpd.read_file(GEOJSON_FILE)

    actions = []
    for _, row in gdf.iterrows():
        # odstrani shapely geometry iz dict-a, da pošljemo samo geojson dict
        doc = row.drop(labels=["geometry"]).to_dict()

        geom = row.geometry
        doc["geometry"] = mapping(geom) if geom is not None else None

        # če obstaja geom_wkt v GED, ga ne rabimo pošiljati
        doc.pop("geom_wkt", None)

        doc = clean_doc_for_es(doc)

        doc_id = doc.get("id")
        if doc_id is None:
            # če bi se kdaj zgodilo, da id manjka, dokument preskočimo (ali zamenjaj z generiranjem)
            continue

        actions.append({"_index": INDEX_NAME, "_id": doc_id, "_source": doc})

    print("[INFO] Zacenjam bulk upload...")
    success_count, fail_count = 0, 0

    for ok, item in helpers.streaming_bulk(es, actions, raise_on_error=False):
        if ok:
            success_count += 1
        else:
            fail_count += 1
            err = item.get("index", {}).get("error")
            doc_id = item.get("index", {}).get("_id")
            print(f"[ERROR] Dokument {doc_id} neuspešen: {err}")

    print(f"[INFO] Bulk upload koncan. Uspesno: {success_count}, Neuspesno: {fail_count}")


if __name__ == "__main__":
    main()
