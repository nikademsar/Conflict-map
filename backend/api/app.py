from fastapi import FastAPI
from elasticsearch import Elasticsearch
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

es = Elasticsearch("http://localhost:9200")


def fix_json(value):
    if isinstance(value, dict):
        return {k: fix_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [fix_json(v) for v in value]
    if isinstance(value, float) and str(value).lower() == "nan":
        return None
    if isinstance(value, str) and value.strip().lower() == "nan":
        return None
    return value


@app.get("/conflicts")
def get_conflicts(year: int, size: int = 10000):
    size = min(max(size, 1), 50000)
    result = es.search(
        index="conflicts",
        query={"term": {"year": year}},
        size=size,
        track_total_hits=False,
    )

    features = []
    for hit in result["hits"]["hits"]:
        src = fix_json(hit["_source"])
        geom = src.get("geometry")

        # če geometry ni prisoten, poskusi iz longitude/latitude (tvoj obstoječi fallback)
        if geom is None and "longitude" in src and "latitude" in src:
            geom = {"type": "Point", "coordinates": [src["longitude"], src["latitude"]]}

        props = dict(src)
        props.pop("geometry", None)
        features.append({"type": "Feature", "geometry": geom, "properties": props})

    return {"type": "FeatureCollection", "features": features}


@app.get("/conflict-countries")
def get_conflict_countries(year: int, size: int = 10000):
    size = min(max(size, 1), 50000)
    result = es.search(
        index="conflict_countries",
        query={"term": {"year": year}},
        size=size,
        track_total_hits=False,
    )

    features = []
    for hit in result["hits"]["hits"]:
        src = fix_json(hit["_source"])
        geom = src.get("geometry")  # geo_shape kot GeoJSON dict
        props = dict(src)
        props.pop("geometry", None)
        features.append({"type": "Feature", "geometry": geom, "properties": props})

    return {"type": "FeatureCollection", "features": features}
