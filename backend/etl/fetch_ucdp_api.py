# backend/etl/fetch_ucdp_api.py
from __future__ import annotations

import argparse
import json
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, Iterable
from urllib.parse import urlencode

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


UCDP_API_BASE = "https://ucdpapi.pcr.uu.se/api"
MAX_PAGESIZE = 1000  # API limit 1000 rows/page :contentReference[oaicite:2]{index=2}


@dataclass(frozen=True)
class FetchConfig:
    resource: str
    version: str
    pagesize: int = 1000
    sleep_s: float = 0.1
    connect_timeout_s: float = 10.0
    read_timeout_s: float = 300.0  # increase from 60 -> 300
    retries: int = 6
    backoff_factor: float = 0.5


def _safe_makedirs(p: str) -> None:
    os.makedirs(p, exist_ok=True)


def _write_json(path: str, obj: Any) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)
    os.replace(tmp, path)


def _session_with_retries(cfg: FetchConfig) -> requests.Session:
    """
    Retry transient failures (timeouts/5xx/429) with exponential backoff.
    Backoff behavior is documented in urllib3 Retry. :contentReference[oaicite:3]{index=3}
    """
    s = requests.Session()
    retry = Retry(
        total=cfg.retries,
        connect=cfg.retries,
        read=cfg.retries,
        status=cfg.retries,
        backoff_factor=cfg.backoff_factor,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET"]),
        raise_on_status=False,
        respect_retry_after_header=True,
    )
    adapter = HTTPAdapter(max_retries=retry)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    return s


def build_url(resource: str, version: str, page: int, pagesize: int, params: Dict[str, Any]) -> str:
    ps = max(1, min(int(pagesize), MAX_PAGESIZE))
    q = {"pagesize": ps, "page": page}
    for k, v in params.items():
        if v is None:
            continue
        if isinstance(v, str) and v.strip() == "":
            continue
        q[k] = v
    return f"{UCDP_API_BASE}/{resource}/{version}?{urlencode(q, doseq=True)}"


def fetch_page(session: requests.Session, url: str, timeout: tuple[float, float]) -> Dict[str, Any]:
    r = session.get(url, timeout=timeout)  # timeout supports tuple(connect, read) :contentReference[oaicite:4]{index=4}
    r.raise_for_status()
    return r.json()


def iter_all_pages(cfg: FetchConfig, params: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    session = _session_with_retries(cfg)
    timeout = (cfg.connect_timeout_s, cfg.read_timeout_s)

    page = 0
    first_url = build_url(cfg.resource, cfg.version, page=page, pagesize=cfg.pagesize, params=params)
    first = fetch_page(session, first_url, timeout)
    yield first

    total_pages = int(first.get("TotalPages", 0))
    for page in range(1, total_pages):
        url = build_url(cfg.resource, cfg.version, page=page, pagesize=cfg.pagesize, params=params)
        obj = fetch_page(session, url, timeout)
        yield obj
        if cfg.sleep_s > 0:
            time.sleep(cfg.sleep_s)


def fetch_resource_by_year(cfg: FetchConfig, year: int, out_dir: str, params: Dict[str, Any], prefix: str, resume: bool) -> None:
    _safe_makedirs(out_dir)

    # Resume: skip pages already written
    existing = set()
    if resume:
        for fn in os.listdir(out_dir):
            if fn.startswith(prefix) and f"year{year}_" in fn and fn.endswith(".json"):
                existing.add(fn)

    for i, page_obj in enumerate(iter_all_pages(cfg, params=params)):
        fn = f"{prefix}_v{cfg.version}_year{year}_page{i:05d}.json"
        if resume and fn in existing:
            continue
        out = os.path.join(out_dir, fn)
        _write_json(out, page_obj)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ged-version", default="25.1")
    ap.add_argument("--acd-version", default="25.1")
    ap.add_argument("--ged-start", type=int, default=1989)
    ap.add_argument("--ged-end", type=int, default=2024)
    ap.add_argument("--acd-start", type=int, default=1946)
    ap.add_argument("--acd-end", type=int, default=2024)
    ap.add_argument("--pagesize", type=int, default=1000)
    ap.add_argument("--sleep", type=float, default=0.1)
    ap.add_argument("--connect-timeout", type=float, default=10.0)
    ap.add_argument("--read-timeout", type=float, default=300.0)
    ap.add_argument("--retries", type=int, default=6)
    ap.add_argument("--backoff", type=float, default=0.5)
    ap.add_argument("--out", default="data/raw_api")
    ap.add_argument("--resume", action="store_true", help="Skip pages already downloaded")
    args = ap.parse_args()

    out_root = args.out
    _safe_makedirs(out_root)

    # GED events
    ged_cfg = FetchConfig(
        resource="gedevents",
        version=args.ged_version,
        pagesize=args.pagesize,
        sleep_s=args.sleep,
        connect_timeout_s=args.connect_timeout,
        read_timeout_s=args.read_timeout,
        retries=args.retries,
        backoff_factor=args.backoff,
    )
    for y in range(args.ged_start, args.ged_end + 1):
        params = {"StartDate": f"{y}-01-01", "EndDate": f"{y}-12-31"}
        fetch_resource_by_year(
            ged_cfg, y, os.path.join(out_root, "gedevents"),
            params=params, prefix="gedevents", resume=args.resume
        )

    # ACD (UCDP/PRIO conflict-year)
    acd_cfg = FetchConfig(
        resource="ucdpprioconflict",
        version=args.acd_version,
        pagesize=args.pagesize,
        sleep_s=args.sleep,
        connect_timeout_s=args.connect_timeout,
        read_timeout_s=args.read_timeout,
        retries=args.retries,
        backoff_factor=args.backoff,
    )
    for y in range(args.acd_start, args.acd_end + 1):
        params = {"year": str(y)}
        fetch_resource_by_year(
            acd_cfg, y, os.path.join(out_root, "ucdpprioconflict"),
            params=params, prefix="ucdpprioconflict", resume=args.resume
        )


if __name__ == "__main__":
    main()
