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

    # agregacija po country_name (eno geojson feature na državo)
    by_country = {}

    for hit in result["hits"]["hits"]:
        src = fix_json(hit["_source"])
        geom = src.get("geometry")
        if geom is None:
            continue

        country = src.get("country_name")
        if not country:
            continue

        intensity = src.get("intensity_level")
        try:
            intensity = int(intensity) if intensity is not None else None
        except Exception:
            intensity = None

        conflict_id = src.get("conflict_id")

        if country not in by_country:
            # osnova: vzemi prvo geometrijo in osnovne props
            props = dict(src)
            props.pop("geometry", None)

            props["intensity_level_max"] = intensity if intensity is not None else 0
            props["conflicts_count"] = 1
            props["conflict_ids"] = [conflict_id] if conflict_id is not None else []
            by_country[country] = {"geometry": geom, "properties": props}
        else:
            p = by_country[country]["properties"]
            p["conflicts_count"] = int(p.get("conflicts_count", 0)) + 1

            old_max = int(p.get("intensity_level_max", 0) or 0)
            new_max = intensity if intensity is not None else 0
            if new_max > old_max:
                p["intensity_level_max"] = new_max

            if conflict_id is not None:
                p.setdefault("conflict_ids", [])
                p["conflict_ids"].append(conflict_id)

    features = []
    for country, obj in by_country.items():
        features.append(
            {
                "type": "Feature",
                "geometry": obj["geometry"],
                "properties": obj["properties"],
            }
        )

    return {"type": "FeatureCollection", "features": features}
