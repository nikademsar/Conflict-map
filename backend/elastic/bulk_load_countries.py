import os, json
import geopandas as gpd
from elasticsearch import Elasticsearch, helpers

ES_HOST = "http://localhost:9200"
INDEX = "conflict_countries"
GEOJSON = "data/processed/conflict_countries.geojson"
MAPPING = "backend/elastic/create_index_countries.json"

def create_index(es: Elasticsearch):
    if es.indices.exists(index=INDEX):
        print(f"[INFO] Index {INDEX} exists.")
        return
    with open(MAPPING, "r", encoding="utf-8") as f:
        body = json.load(f)
    es.indices.create(index=INDEX, body=body)
    print(f"[OK] Created {INDEX}")

def main():
    es = Elasticsearch(ES_HOST)
    create_index(es)

    if not os.path.exists(GEOJSON):
        raise FileNotFoundError(f"Missing {GEOJSON} - run ETL first.")

    gdf = gpd.read_file(GEOJSON)

    actions = []
    for _, row in gdf.iterrows():
        props = row.drop(labels=["geometry"]).to_dict()
        geom = row.geometry.__geo_interface__ if row.geometry is not None else None
        props["geometry"] = geom

        doc_id = f'{props.get("conflict_id")}-{props.get("year")}-{props.get("country_name")}'
        actions.append({"_index": INDEX, "_id": doc_id, "_source": props})

    ok, fail = 0, 0
    for success, item in helpers.streaming_bulk(es, actions, raise_on_error=False):
        if success:
            ok += 1
        else:
            fail += 1
            print("[ERROR]", item)
    print(f"[OK] Loaded {ok}, failed {fail}")

if __name__ == "__main__":
    main()
