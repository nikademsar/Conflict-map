@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM ============================================
REM Conflict-map - Windows launcher (BAT)
REM ============================================

cd /d "%~dp0"

echo.
echo [0/6] Preverjam Natural Earth datoteko
if not exist "data\raw\ne_110m_admin_0_countries.geojson" goto :NO_NE

echo.
echo [1/6] Namestitev Python knjiznic (requirements.txt)
python -m pip install -r requirements.txt
if errorlevel 1 goto :FAIL

echo.
echo [2/6] Zagon Elasticsearch + Kibana + Redis (Docker)
where docker-compose >nul 2>nul
if %errorlevel%==0 goto :DOCKER_DC
goto :DOCKER_D

:DOCKER_DC
docker-compose up -d
if errorlevel 1 goto :FAIL
goto :GW

:DOCKER_D
docker compose up -d
if errorlevel 1 goto :FAIL
goto :GW

:GW
echo.
echo [3/6] GWNo seznam drzav
if exist "data\raw_api\gw_states.csv" goto :GW_OK
echo [INFO] Prenasam GWNo (insecure; zaradi TLS na hostu)
python backend\etl\download_gwno_states.py --insecure --quiet-warn
if errorlevel 1 goto :FAIL

:GW_OK
echo [INFO] GWNo OK

echo.
echo [4/6] UCDP API prenos (GED + ACD)
if exist "data\raw_api\gedevents\*.json" goto :GED_OK
echo [INFO] GED raw manjka -> klicem fetch_ucdp_api.py
python backend\etl\fetch_ucdp_api.py --read-timeout 300 --retries 6 --resume

if errorlevel 1 goto :FAIL

:GED_OK
if exist "data\raw_api\ucdpprioconflict\*.json" goto :ACD_OK
echo [INFO] ACD raw manjka -> klicem fetch_ucdp_api.py
python backend\etl\fetch_ucdp_api.py
if errorlevel 1 goto :FAIL

:ACD_OK
echo [INFO] UCDP raw OK

echo.
echo [5/6] ETL: raw_api JSON -> processed GeoJSON
python backend\etl\process_data_api.py
if errorlevel 1 goto :FAIL

echo.
echo [6/6] Nalaganje v Elasticsearch (events + countries)
python backend\elastic\bulk_load.py
if errorlevel 1 goto :FAIL
python backend\elastic\bulk_load_countries.py
if errorlevel 1 goto :FAIL

echo.
echo [INFO] Zagon API-ja (uvicorn + Redis cache)
echo Kibana:   http://localhost:5601
echo API:      http://localhost:8000
echo Redis:    localhost:6379
echo Frontend: odpri frontend\index.html
echo.
echo OPOMBA: API tece v tem oknu. Zapri okno za ustavitev.
echo.

set REDIS_ENABLED=1
set REDIS_HOST=localhost
set REDIS_PORT=6379
set REDIS_DB=0
set REDIS_TTL_SECONDS=3600

python -m uvicorn backend.api.app:app --reload --port 8000
goto :EOF

:NO_NE
echo.
echo [ERROR] Manjka: data\raw\ne_110m_admin_0_countries.geojson
echo Dodaj Natural Earth admin_0 countries GeoJSON v to pot.
pause
exit /b 1

:FAIL
echo.
echo [ERROR] Zagon je spodletel. Preveri izpis zgoraj.
pause
exit /b 1
