import os
import pandas as pd
import geopandas as gpd

ACD_CSV = "data/raw/ucdp_prio_acd.csv"
GED_CSV = "data/raw/ucdp_ged.csv"
NE_COUNTRIES_GEOJSON = "data/raw/ne_110m_admin_0_countries.geojson"

OUT_EVENTS = "data/processed/conflicts_events.geojson"
OUT_COUNTRIES = "data/processed/conflict_countries.geojson"

os.makedirs("data/processed", exist_ok=True)


def _require_cols(df: pd.DataFrame, cols: list[str], name: str):
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise ValueError(f"{name} manjka stolpce: {missing}")


def _norm_name(s: str) -> str:
    if s is None:
        return ""
    return (
        str(s).strip().lower()
        .replace("&", "and")
        .replace(".", "")
        .replace(",", "")
    )


# varno: shapely 2 ima make_valid, shapely 1 pogosto ne
try:
    from shapely.validation import make_valid as _make_valid
except Exception:
    _make_valid = None


def fix_geometry(geom):
    if geom is None:
        return None

    # 1) poskusi make_valid (če obstaja)
    if _make_valid is not None:
        try:
            g = _make_valid(geom)
        except Exception:
            g = None
    else:
        g = None

    # 2) fallback: buffer(0)
    if g is None:
        try:
            g = geom.buffer(0)
        except Exception:
            return None

    if g is None or g.is_empty:
        return None
    return g


def atomic_write_geojson(gdf: gpd.GeoDataFrame, path: str):
    # tmp naj bo vedno .geojson (da driver dela enako na vseh OS)
    tmp = path + ".tmp.geojson"
    gdf.to_file(tmp, driver="GeoJSON")
    os.replace(tmp, path)


def build_country_conflicts(acd: pd.DataFrame, countries: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    _require_cols(acd, ["conflict_id", "year", "location"], "ACD")
    acd = acd.copy()
    acd["location"] = acd["location"].astype(str)

    rows = []
    for _, r in acd.iterrows():
        parts = [p.strip() for p in r["location"].replace(";", ",").split(",") if p.strip()]
        for p in parts:
            rows.append(
                {
                    "conflict_id": int(r["conflict_id"]),
                    "year": int(r["year"]),
                    "country_name": p,
                    "type_of_conflict": r.get("type_of_conflict"),
                    "intensity_level": r.get("intensity_level"),
                    "incompatibility": r.get("incompatibility"),
                    "side_a": r.get("side_a"),
                    "side_b": r.get("side_b"),
                    "region": r.get("region"),
                    "version": r.get("version"),
                }
            )

    cdf = pd.DataFrame(rows)
    cdf["country_key"] = cdf["country_name"].map(_norm_name)

    admin_col = "ADMIN" if "ADMIN" in countries.columns else None
    name_long_col = "NAME_LONG" if "NAME_LONG" in countries.columns else None
    if admin_col is None and name_long_col is None:
        raise ValueError("Natural Earth GeoJSON nima pričakovanih polj ADMIN/NAME_LONG.")

    countries = countries.copy()
    if admin_col:
        countries["admin_key"] = countries[admin_col].map(_norm_name)
    if name_long_col:
        countries["name_long_key"] = countries[name_long_col].map(_norm_name)

    # primary match: ADMIN
    if admin_col:
        m = cdf.merge(
            countries[["admin_key", "geometry"]].rename(columns={"admin_key": "country_key"}),
            on="country_key",
            how="left",
        )
    else:
        m = cdf.copy()
        m["geometry"] = None

    # fallback match: NAME_LONG
    if name_long_col:
        no_geom = m["geometry"].isna()
        if no_geom.any():
            fb = cdf[no_geom].merge(
                countries[["name_long_key", "geometry"]].rename(columns={"name_long_key": "country_key"}),
                on="country_key",
                how="left",
            )
            m.loc[no_geom, "geometry"] = fb["geometry"].values

    m = m.dropna(subset=["geometry"]).drop_duplicates(subset=["conflict_id", "year", "country_name"])
    gdf = gpd.GeoDataFrame(m, geometry="geometry", crs=countries.crs or "EPSG:4326")
    return gdf


def build_event_points(ged: pd.DataFrame) -> gpd.GeoDataFrame:
    ged = ged.copy()
    ged.columns = [str(c).strip() for c in ged.columns]

    # GED: conflict_new_id -> conflict_id (za nadaljnjo uporabo v projektu)
    if "conflict_id" not in ged.columns and "conflict_new_id" in ged.columns:
        ged["conflict_id"] = ged["conflict_new_id"]

    _require_cols(ged, ["conflict_id", "year", "latitude", "longitude"], "GED")
    ged = ged.dropna(subset=["latitude", "longitude"]).copy()

    gdf = gpd.GeoDataFrame(
        ged,
        geometry=gpd.points_from_xy(ged["longitude"], ged["latitude"]),
        crs="EPSG:4326",
    )
    return gdf


def main():
    acd = pd.read_csv(ACD_CSV, low_memory=False)
    countries = gpd.read_file(NE_COUNTRIES_GEOJSON)

    countries_gdf = build_country_conflicts(acd, countries)
    countries_gdf["geometry"] = countries_gdf["geometry"].apply(fix_geometry)
    countries_gdf = countries_gdf.dropna(subset=["geometry"])

    atomic_write_geojson(countries_gdf, OUT_COUNTRIES)
    print(f"[OK] {OUT_COUNTRIES} features={len(countries_gdf)}")

    ged = pd.read_csv(GED_CSV, low_memory=False)
    events_gdf = build_event_points(ged)
    atomic_write_geojson(events_gdf, OUT_EVENTS)
    print(f"[OK] {OUT_EVENTS} features={len(events_gdf)}")


if __name__ == "__main__":
    main()
