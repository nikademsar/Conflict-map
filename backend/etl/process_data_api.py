# process_data_api.py
from __future__ import annotations

import argparse
import glob
import json
import os
from typing import Any, Dict, Iterable, List, Optional

import pandas as pd
import geopandas as gpd
from shapely.geometry import mapping


RAW_GED_DIR = "data/raw_api/gedevents"
RAW_ACD_DIR = "data/raw_api/ucdpprioconflict"
GW_STATES_CSV = "data/raw_api/gw_states.csv"
NE_COUNTRIES_GEOJSON = "data/raw/ne_110m_admin_0_countries.geojson"

OUT_EVENTS = "data/processed/conflicts_events.geojson"
OUT_COUNTRIES = "data/processed/conflict_countries.geojson"


def _safe_makedirs(p: str) -> None:
    os.makedirs(p, exist_ok=True)


def _norm_name(s: Any) -> str:
    if s is None:
        return ""
    return (
        str(s).strip().lower()
        .replace("&", "and")
        .replace(".", "")
        .replace(",", "")
    )


# shapely validity helper (same approach as your existing ETL) :contentReference[oaicite:17]{index=17}
try:
    from shapely.validation import make_valid as _make_valid
except Exception:
    _make_valid = None


def fix_geometry(geom):
    if geom is None:
        return None
    if _make_valid is not None:
        try:
            g = _make_valid(geom)
        except Exception:
            g = None
    else:
        g = None
    if g is None:
        try:
            g = geom.buffer(0)
        except Exception:
            return None
    if g is None or g.is_empty:
        return None
    return g


def atomic_write_geojson(gdf: gpd.GeoDataFrame, path: str) -> None:
    tmp = path + ".tmp.geojson"
    gdf.to_file(tmp, driver="GeoJSON")
    os.replace(tmp, path)


def _iter_result_rows_from_pages(files: Iterable[str]) -> Iterable[Dict[str, Any]]:
    for fp in files:
        with open(fp, "r", encoding="utf-8") as f:
            obj = json.load(f)
        res = obj.get("Result", [])
        if isinstance(res, list):
            for row in res:
                if isinstance(row, dict):
                    yield row


def load_ged_events_df(raw_dir: str) -> pd.DataFrame:
    files = sorted(glob.glob(os.path.join(raw_dir, "*.json")))
    if not files:
        raise FileNotFoundError(f"No GED raw pages found in {raw_dir}. Run fetch_ucdp_api.py first.")
    rows = list(_iter_result_rows_from_pages(files))
    return pd.DataFrame(rows)


def load_acd_df(raw_dir: str) -> pd.DataFrame:
    files = sorted(glob.glob(os.path.join(raw_dir, "*.json")))
    if not files:
        raise FileNotFoundError(f"No ACD raw pages found in {raw_dir}. Run fetch_ucdp_api.py first.")
    rows = list(_iter_result_rows_from_pages(files))
    return pd.DataFrame(rows)


def build_event_points_from_ged(ged: pd.DataFrame) -> gpd.GeoDataFrame:
    # Match what your ES mapping expects for conflicts events index. :contentReference[oaicite:18]{index=18}
    required = ["id", "year", "latitude", "longitude"]
    missing = [c for c in required if c not in ged.columns]
    if missing:
        raise ValueError(f"GED missing columns: {missing}")

    ged = ged.dropna(subset=["latitude", "longitude"]).copy()

    gdf = gpd.GeoDataFrame(
        ged,
        geometry=gpd.points_from_xy(ged["longitude"], ged["latitude"]),
        crs="EPSG:4326",
    )
    return gdf


def build_country_conflicts_from_acd(
    acd: pd.DataFrame,
    countries: gpd.GeoDataFrame,
    gw_states: pd.DataFrame,
) -> gpd.GeoDataFrame:
    """
    ACD rows contain gwno_loc (location of incompatibility) per API docs. :contentReference[oaicite:19]{index=19}
    We map gwno_loc -> country_name using GW states list (gw_states.csv).
    Then we match by name to Natural Earth polygons (ADMIN/NAME_LONG), as in your existing ETL. :contentReference[oaicite:20]{index=20}
    """
    if "gwno_loc" not in acd.columns:
        raise ValueError("ACD API data missing 'gwno_loc' column.")
    if "year" not in acd.columns:
        raise ValueError("ACD API data missing 'year' column.")

    gw_states = gw_states.copy()
    if "gwno" not in gw_states.columns or "country_name" not in gw_states.columns:
        raise ValueError("gw_states.csv must contain columns: gwno,country_name")

    # join gwno_loc -> country_name
    acd2 = acd.copy()
    acd2["gwno_loc"] = pd.to_numeric(acd2["gwno_loc"], errors="coerce")
    gw_states["gwno"] = pd.to_numeric(gw_states["gwno"], errors="coerce")
    acd2 = acd2.merge(gw_states[["gwno", "country_name"]], left_on="gwno_loc", right_on="gwno", how="left")

    # Normalize keys
    acd2["country_key"] = acd2["country_name"].map(_norm_name)

    admin_col = "ADMIN" if "ADMIN" in countries.columns else None
    name_long_col = "NAME_LONG" if "NAME_LONG" in countries.columns else None
    if admin_col is None and name_long_col is None:
        raise ValueError("Natural Earth GeoJSON missing ADMIN/NAME_LONG columns.")

    ctry = countries.copy()
    if admin_col:
        ctry["admin_key"] = ctry[admin_col].map(_norm_name)
    if name_long_col:
        ctry["name_long_key"] = ctry[name_long_col].map(_norm_name)

    # pick ISO3 field from Natural Earth if available
    iso_col = None
    for cand in ["ISO_A3", "ADM0_A3", "ISO3", "iso_a3"]:
        if cand in ctry.columns:
            iso_col = cand
            break

    # primary match: ADMIN
    if admin_col:
        m = acd2.merge(
            ctry[["admin_key", "geometry"] + ([iso_col] if iso_col else [])].rename(columns={"admin_key": "country_key"}),
            on="country_key",
            how="left",
        )
    else:
        m = acd2.copy()
        m["geometry"] = None
        if iso_col:
            m[iso_col] = None

    # fallback match: NAME_LONG
    if name_long_col:
        no_geom = m["geometry"].isna()
        if no_geom.any():
            fb = acd2[no_geom].merge(
                ctry[["name_long_key", "geometry"] + ([iso_col] if iso_col else [])].rename(columns={"name_long_key": "country_key"}),
                on="country_key",
                how="left",
            )
            m.loc[no_geom, "geometry"] = fb["geometry"].values
            if iso_col:
                m.loc[no_geom, iso_col] = fb[iso_col].values

    # Build output schema similar to your current conflict_countries.geojson properties :contentReference[oaicite:21]{index=21}
    out_cols = {
        "conflict_id": "conflict_id",
        "year": "year",
        "country_name": "country_name",
        "type_of_conflict": "type_of_conflict",
        "intensity_level": "intensity_level",
        "incompatibility": "incompatibility",
        "side_a": "side_a",
        "side_b": "side_b",
        "region": "region",
        "version": "version",
    }

    out = pd.DataFrame()
    for k, src in out_cols.items():
        if src in m.columns:
            out[k] = m[src]
        else:
            out[k] = None

    # Optional ISO3 for popup (frontend already tries to display it) :contentReference[oaicite:22]{index=22}
    if iso_col:
        out["iso3"] = m[iso_col]
    else:
        out["iso3"] = None

    out["geometry"] = m["geometry"]

    # clean + unique
    out = out.dropna(subset=["geometry"])
    # ACD is already conflict-year; allow multiple conflicts per country-year as separate rows
    gdf = gpd.GeoDataFrame(out, geometry="geometry", crs=ctry.crs or "EPSG:4326")

    # fix invalid polygons
    gdf["geometry"] = gdf["geometry"].apply(fix_geometry)
    gdf = gdf.dropna(subset=["geometry"])

    return gdf


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-ged", default=RAW_GED_DIR)
    ap.add_argument("--raw-acd", default=RAW_ACD_DIR)
    ap.add_argument("--gw-states", default=GW_STATES_CSV)
    ap.add_argument("--ne", default=NE_COUNTRIES_GEOJSON)
    ap.add_argument("--out-events", default=OUT_EVENTS)
    ap.add_argument("--out-countries", default=OUT_COUNTRIES)
    args = ap.parse_args()

    _safe_makedirs(os.path.dirname(args.out_events))
    _safe_makedirs(os.path.dirname(args.out_countries))

    # Natural Earth polygons stay local (API does not provide country geometries). :contentReference[oaicite:23]{index=23}
    countries = gpd.read_file(args.ne)

    # --- Countries layer (ACD -> country polygons) ---
    gw_states = pd.read_csv(args.gw_states)
    acd = load_acd_df(args.raw_acd)
    countries_gdf = build_country_conflicts_from_acd(acd, countries=countries, gw_states=gw_states)
    atomic_write_geojson(countries_gdf, args.out_countries)
    print(f"[OK] {args.out_countries} features={len(countries_gdf)}")

    # --- Events layer (GED -> points) ---
    ged = load_ged_events_df(args.raw_ged)
    events_gdf = build_event_points_from_ged(ged)
    atomic_write_geojson(events_gdf, args.out_events)
    print(f"[OK] {args.out_events} features={len(events_gdf)}")


if __name__ == "__main__":
    main()
