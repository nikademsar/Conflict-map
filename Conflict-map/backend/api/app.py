from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

from elasticsearch import Elasticsearch
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# Optional Redis cache (requires `redis` package in requirements.txt)
try:
    import redis  # type: ignore
except Exception:
    redis = None


# =======================
# Config (env overridable)
# =======================
ES_HOST = os.getenv("ES_HOST", "http://localhost:9200")

REDIS_ENABLED = os.getenv("REDIS_ENABLED", "0") == "1"  # default OFF unless enabled
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))
REDIS_TTL_SECONDS = int(os.getenv("REDIS_TTL_SECONDS", "3600"))

MAX_SIZE = int(os.getenv("API_MAX_SIZE", "50000"))


# =======================
# App
# =======================
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

es = Elasticsearch(ES_HOST)


# =======================
# Redis client (optional)
# =======================
redis_client = None
if REDIS_ENABLED and redis is not None:
    try:
        redis_client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB,
            decode_responses=True,
        )
        redis_client.ping()
    except Exception:
        redis_client = None


def cache_key(prefix: str, year: int, size: int, filters: Dict[str, Any]) -> str:
    f = {k: v for k, v in filters.items() if v is not None and v != ""}
    f_str = json.dumps(f, sort_keys=True, ensure_ascii=False)
    return f"{prefix}:year={year}:size={size}:filters={f_str}"


def cache_get(key: str) -> Optional[dict]:
    if redis_client is None:
        return None
    try:
        val = redis_client.get(key)
        if val is None:
            return None
        return json.loads(val)
    except Exception:
        return None


def cache_set(key: str, value: dict) -> None:
    if redis_client is None:
        return
    try:
        redis_client.setex(key, REDIS_TTL_SECONDS, json.dumps(value, ensure_ascii=False))
    except Exception:
        pass


# =======================
# Helpers
# =======================
def fix_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: fix_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [fix_json(v) for v in value]
    if isinstance(value, float) and str(value).lower() == "nan":
        return None
    if isinstance(value, str) and value.strip().lower() == "nan":
        return None
    return value


def clamp_size(size: int) -> int:
    size = int(size)
    if size < 1:
        size = 1
    if size > MAX_SIZE:
        size = MAX_SIZE
    return size


# =======================
# Health
# =======================
@app.get("/health")
def health() -> Dict[str, Any]:
    out: Dict[str, Any] = {"ok": True, "es_host": ES_HOST}
    try:
        out["es"] = es.info()
    except Exception as e:
        out["ok"] = False
        out["es_error"] = str(e)

    out["redis_enabled"] = REDIS_ENABLED and redis is not None
    out["redis_connected"] = redis_client is not None
    return out


# =======================
# Endpoints
# =======================
@app.get("/conflicts")
def get_conflicts(
    year: int,
    size: int = 10000,
    region: Optional[str] = None,
    country: Optional[str] = None,
    type_of_violence: Optional[int] = None,
    min_best: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Points (GED, 1989+): index "conflicts"
    Returns GeoJSON FeatureCollection.
    Filters are applied via ES bool.filter (term/range).
    """
    size = clamp_size(size)

    filters: Dict[str, Any] = {
        "region": region,
        "country": country,
        "type_of_violence": type_of_violence,
        "min_best": min_best,
    }
    ck = cache_key("conflicts", year, size, filters)
    cached = cache_get(ck)
    if cached is not None:
        return cached

    must_filters = [{"term": {"year": year}}]

    if region:
        must_filters.append({"term": {"region": region}})
    if country:
        must_filters.append({"term": {"country": country}})
    if type_of_violence is not None:
        must_filters.append({"term": {"type_of_violence": int(type_of_violence)}})
    if min_best is not None:
        must_filters.append({"range": {"best": {"gte": int(min_best)}}})

    try:
        result = es.search(
            index="conflicts",
            query={"bool": {"filter": must_filters}},
            size=size,
            track_total_hits=False,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Elasticsearch error: {e}")

    features = []
    for hit in result.get("hits", {}).get("hits", []):
        src = fix_json(hit.get("_source", {}))
        geom = src.get("geometry")

        # fallback: create Point from longitude/latitude if geometry missing
        if geom is None and "longitude" in src and "latitude" in src:
            try:
                geom = {"type": "Point", "coordinates": [src["longitude"], src["latitude"]]}
            except Exception:
                geom = None

        props = dict(src)
        props.pop("geometry", None)
        features.append({"type": "Feature", "geometry": geom, "properties": props})

    response = {"type": "FeatureCollection", "features": features}
    cache_set(ck, response)
    return response


@app.get("/conflict-countries")
def get_conflict_countries(
    year: int,
    size: int = 10000,
    region: Optional[str] = None,
    country_name: Optional[str] = None,
    type_of_conflict: Optional[int] = None,
    intensity_level: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Polygons (ACD + country polygons, 1946+): index "conflict_countries"
    Returns GeoJSON FeatureCollection.
    Aggregates multiple rows per country-year into a single feature per country.
    """
    size = clamp_size(size)

    filters: Dict[str, Any] = {
        "region": region,
        "country_name": country_name,
        "type_of_conflict": type_of_conflict,
        "intensity_level": intensity_level,
    }
    ck = cache_key("conflict_countries", year, size, filters)
    cached = cache_get(ck)
    if cached is not None:
        return cached

    must_filters = [{"term": {"year": year}}]

    if region:
        must_filters.append({"term": {"region": region}})
    if country_name:
        must_filters.append({"term": {"country_name": country_name}})
    if type_of_conflict is not None:
        must_filters.append({"term": {"type_of_conflict": int(type_of_conflict)}})
    if intensity_level is not None:
        must_filters.append({"term": {"intensity_level": int(intensity_level)}})

    try:
        result = es.search(
            index="conflict_countries",
            query={"bool": {"filter": must_filters}},
            size=size,
            track_total_hits=False,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Elasticsearch error: {e}")

    by_country: Dict[str, Dict[str, Any]] = {}

    hits = result.get("hits", {}).get("hits", [])
    for hit in hits:
        src = fix_json(hit.get("_source", {}))
        geom = src.get("geometry")
        if geom is None:
            continue

        cname = src.get("country_name")
        if not cname:
            continue

        intensity = src.get("intensity_level")
        try:
            intensity_i = int(intensity) if intensity is not None else 0
        except Exception:
            intensity_i = 0

        conflict_id = src.get("conflict_id")

        if cname not in by_country:
            props = dict(src)
            props.pop("geometry", None)

            props["intensity_level_max"] = intensity_i
            props["conflicts_count"] = 1
            props["conflict_ids"] = [conflict_id] if conflict_id is not None else []

            by_country[cname] = {"geometry": geom, "properties": props}
        else:
            p = by_country[cname]["properties"]

            # count
            try:
                p["conflicts_count"] = int(p.get("conflicts_count", 0)) + 1
            except Exception:
                p["conflicts_count"] = 1

            # max intensity
            try:
                old_max = int(p.get("intensity_level_max", 0) or 0)
            except Exception:
                old_max = 0
            if intensity_i > old_max:
                p["intensity_level_max"] = intensity_i

            # collect conflict_ids
            if conflict_id is not None:
                p.setdefault("conflict_ids", [])
                p["conflict_ids"].append(conflict_id)

    features = []
    for _, obj in by_country.items():
        features.append(
            {
                "type": "Feature",
                "geometry": obj["geometry"],
                "properties": obj["properties"],
            }
        )

    response = {"type": "FeatureCollection", "features": features}
    cache_set(ck, response)
    return response


@app.post("/cache/clear")
def cache_clear() -> Dict[str, Any]:
    if redis_client is None:
        return {"ok": False, "redis_connected": False}
    try:
        redis_client.flushdb()
        return {"ok": True, "redis_connected": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Redis error: {e}")
