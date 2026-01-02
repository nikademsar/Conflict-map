@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM ============================================
REM Conflict-map - Windows launcher (BAT)
REM ============================================
REM Predpogoji:
REM - Docker Desktop (docker + docker-compose ali docker compose)
REM - Python v PATH (python, pip)
REM - requirements.txt v rootu repozitorija
REM - Redis definiran v docker-compose.yml
REM ============================================

cd /d "%~dp0"

echo.
echo [1/5] Namestitev Python knjiznic (requirements.txt)
python -m pip install -r requirements.txt
if errorlevel 1 goto :FAIL

echo.
echo [2/5] Zagon Elasticsearch + Kibana (+ Redis)
REM Podpira tako "docker-compose" kot "docker compose"
where docker-compose >nul 2>nul
if %errorlevel%==0 (
  docker-compose up -d
) else (
  docker compose up -d
)
if errorlevel 1 goto :FAIL

echo.
echo [3/5] ETL priprava podatkov
python backend\etl\process_data.py
if errorlevel 1 goto :FAIL

echo.
echo [4/5] Nalaganje v Elasticsearch (events + countries)
python backend\elastic\bulk_load.py
if errorlevel 1 goto :FAIL
python backend\elastic\bulk_load_countries.py
if errorlevel 1 goto :FAIL

echo.
echo [5/5] Zagon API-ja (uvicorn + Redis cache)
echo Kibana: http://localhost:5601
echo API:    http://localhost:8000
echo Redis:  localhost:6379
echo Frontend: odpri frontend\index.html
echo.
echo OPOMBA: API se bo zaganjal v tem oknu. Zapri okno za ustavitev.
echo.

REM ==========================
REM Vklop Redis cache
REM ==========================
set REDIS_ENABLED=1
set REDIS_HOST=localhost
set REDIS_PORT=6379
set REDIS_DB=0
set REDIS_TTL_SECONDS=3600

python -m uvicorn backend.api.app:app --reload --port 8000
goto :EOF

:FAIL
echo.
echo [ERROR] Zagon je spodletel. Preveri izpis zgoraj.
pause
exit /b 1
