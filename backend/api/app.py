from fastapi import FastAPI
from elasticsearch import Elasticsearch
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI()
app = FastAPI()
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # za lokalni razvoj
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

es = Elasticsearch("http://localhost:9200")


def fix_json(value):
    """
    Rekurzivno zamenja vse NaN / 'NaN' z None, da je izhod veljaven JSON.
    """
    if isinstance(value, dict):
        return {k: fix_json(v) for k, v in value.items()}

    if isinstance(value, list):
        return [fix_json(v) for v in value]

    if isinstance(value, float):
        if str(value).lower() == "nan":
            return None
        return value

    if isinstance(value, str):
        if value.strip().lower() == "nan":
            return None
        return value

    return value


@app.get("/conflicts")
def get_conflicts(year: int):
    query = {
        "term": {
            "year": year
        }
    }

    result = es.search(
        index="conflicts",
        query=query,
        size=10000
    )

    features = []
    for hit in result["hits"]["hits"]:
        src = hit["_source"]
        src = fix_json(src)

        geom = src.get("geometry")

        if geom is None and "longitude" in src and "latitude" in src:
            geom = {
                "type": "Point",
                "coordinates": [src["longitude"], src["latitude"]]
            }

        props = dict(src)
        props.pop("geometry", None)

        features.append({
            "type": "Feature",
            "geometry": geom,
            "properties": props
        })

    return {
        "type": "FeatureCollection",
        "features": features
    }
