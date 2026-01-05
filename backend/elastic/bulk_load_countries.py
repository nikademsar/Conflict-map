import os
import json

import geopandas as gpd
from shapely.geometry import mapping
from elasticsearch import Elasticsearch, helpers, ApiError


ES_HOST = "http://localhost:9200"
INDEX = "conflict_countries"
GEOJSON = "data/processed/conflict_countries.geojson"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MAPPING = os.path.join(BASE_DIR, "create_index_countries.json")


def create_index(es: Elasticsearch) -> None:
    # NE uporabljaj es.indices.exists() (pri tebi vrača 400 na HEAD)
    with open(MAPPING, "r", encoding="utf-8") as f:
        body = json.load(f)

    try:
        es.indices.create(index=INDEX, body=body)
        print(f"[OK] Created {INDEX}")
    except ApiError as e:
        # indeks že obstaja -> OK
        if (
            getattr(e, "error", None) == "resource_already_exists_exception"
            or "resource_already_exists_exception" in str(e)
        ):
            print(f"[INFO] Index {INDEX} exists.")
            return
        raise


def main() -> None:
    es = Elasticsearch(ES_HOST)
    create_index(es)

    if not os.path.exists(GEOJSON):
        raise FileNotFoundError(f"Missing {GEOJSON} - run ETL first.")

    gdf = gpd.read_file(GEOJSON)

    actions = []
    for _, row in gdf.iterrows():
        props = row.drop(labels=["geometry"]).to_dict()

        geom = row.geometry
        props["geometry"] = mapping(geom) if geom is not None else None

        # stabilen _id (če conflict_id manjka, vseeno dobimo unikaten ključ)
        conflict_id = props.get("conflict_id")
        year = props.get("year")
        country_name = props.get("country_name")
        iso3 = props.get("iso3")

        if conflict_id is None:
            doc_id = f"{year}-{country_name}-{iso3}"
        else:
            doc_id = f"{conflict_id}-{year}-{country_name}"

        actions.append({"_index": INDEX, "_id": doc_id, "_source": props})

    ok, fail = 0, 0
    for success, item in helpers.streaming_bulk(es, actions, raise_on_error=False):
        if success:
            ok += 1
        else:
            fail += 1
            err = item.get("index", {}).get("error")
            doc_id = item.get("index", {}).get("_id")
            print(f"[ERROR] Document {doc_id} failed: {err}")

    print(f"[OK] Loaded {ok}, failed {fail}")


if __name__ == "__main__":
    main()
