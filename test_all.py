import os
import sys
import subprocess
import time

# --- Nastavitve ---
GEOCSV_PATH = "data/raw/ucdp.csv"
ETL_SCRIPT = "backend/etl/process_data.py"
BULK_SCRIPT = "backend/elastic/bulk_load.py"
DOCKER_COMPOSE_FILE = "docker-compose.yml"

def check_file(path):
    if os.path.isfile(path) and os.path.getsize(path) > 0:
        print(f"[OK] Datoteka najdena: {path}")
        return True
    else:
        print(f"[ERROR] Datoteka ne obstaja ali je prazna: {path}")
        return False

def check_modules(modules):
    for mod in modules:
        try:
            __import__(mod)
            print(f"[OK] Modul najden: {mod}")
        except ImportError:
            print(f"[ERROR] Modul ni nameščen: {mod}")

def run_etl():
    print("[INFO] Zagon ETL skripta...")
    subprocess.run([sys.executable, ETL_SCRIPT], check=True)

def run_docker_compose():
    print("[INFO] Zagon Elasticsearch in Kibana preko Docker Compose...")
    subprocess.run(["docker-compose", "-f", DOCKER_COMPOSE_FILE, "up", "-d"], check=True)
    print("[INFO] Počakaj 15 sekund, da se Elasticsearch zažene...")
    time.sleep(15)

def load_elasticsearch():
    print("[INFO] Nalaganje podatkov v Elasticsearch...")
    subprocess.run([sys.executable, BULK_SCRIPT], check=True)

if __name__ == "__main__":
    # Preveri CSV
    if not check_file(GEOCSV_PATH):
        sys.exit(1)

    # Preveri module
    required_modules = [
        "pandas", "numpy", "geopandas", "shapely",
        "folium", "flask", "elasticsearch", "requests", "uvicorn"
    ]
    check_modules(required_modules)

    # Zagon ETL skripta
    run_etl()

    # Zagon Docker Compose (Elasticsearch/Kibana)
    if os.path.isfile(DOCKER_COMPOSE_FILE):
        run_docker_compose()
    else:
        print(f"[WARNING] Docker Compose datoteka ne obstaja: {DOCKER_COMPOSE_FILE}")

    # Bulk load podatkov v Elasticsearch
    try:
        load_elasticsearch()
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Bulk load je končal z napako: {e}")
        sys.exit(1)

    print("[OK] Test & Run dokončan.")
