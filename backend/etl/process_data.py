import os
import pandas as pd
import geopandas as gpd

RAW_CSV = "data/raw/ucdp.csv"
PROCESSED_GEOJSON = "data/processed/conflicts.geojson"

# Ustvari mapo processed, če ne obstaja
os.makedirs(os.path.dirname(PROCESSED_GEOJSON), exist_ok=True)

# Naloži CSV
try:
    df = pd.read_csv(RAW_CSV, low_memory=False)
    print(f"[OK] CSV naložen: {RAW_CSV}")
except FileNotFoundError:
    print(f"[ERROR] CSV datoteka ne obstaja: {RAW_CSV}")
    exit(1)

# Preveri stolpce za geolokacijo
if not {"latitude", "longitude"}.issubset(df.columns):
    print("[ERROR] CSV datoteka ne vsebuje stolpcev 'latitude' in 'longitude'.")
    exit(1)

# Pretvori v GeoDataFrame
gdf = gpd.GeoDataFrame(
    df,
    geometry=gpd.points_from_xy(df.longitude, df.latitude),
    crs="EPSG:4326"
)

# Shrani geojson
try:
    gdf.to_file(PROCESSED_GEOJSON, driver="GeoJSON")
    print(f"[OK] GeoJSON ustvarjen: {PROCESSED_GEOJSON}")
except Exception as e:
    print(f"[ERROR] Napaka pri shranjevanju GeoJSON: {e}")
    exit(1)
