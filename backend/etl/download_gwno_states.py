# etl/download_gwno_states.py
from __future__ import annotations

import argparse
import os
import re
import zipfile
from io import BytesIO
from typing import List, Tuple, Optional
from urllib.parse import urljoin, urlparse

import requests
import urllib3


DATA4_URL = "https://ksgleditsch.com/data-4.html"


def _safe_makedirs(p: str) -> None:
    if p:
        os.makedirs(p, exist_ok=True)


def _get(url: str, verify: bool, timeout: int = 60) -> requests.Response:
    r = requests.get(url, timeout=timeout, verify=verify)
    r.raise_for_status()
    return r


def _extract_all_hrefs(html: str, base_url: str) -> List[str]:
    # Grab all href="..."
    hrefs = re.findall(r'href="([^"]+)"', html, flags=re.IGNORECASE)
    out: List[str] = []
    for h in hrefs:
        h = h.strip()
        if not h:
            continue
        if h.lower().startswith(("mailto:", "javascript:", "#")):
            continue
        out.append(urljoin(base_url, h))
    # de-dup, keep order
    seen = set()
    uniq = []
    for u in out:
        if u in seen:
            continue
        seen.add(u)
        uniq.append(u)
    return uniq


def _looks_like_gw_states_text(txt: str) -> bool:
    """
    Heuristic: GW list typically has many lines starting with an integer code.
    Require at least 50 matches to avoid false positives.
    """
    hits = 0
    for line in txt.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if re.match(r"^\d{1,4}\s+\S+", line):
            hits += 1
            if hits >= 50:
                return True
    return False


def _parse_gw_states_text(txt: str) -> List[Tuple[int, str]]:
    rows: List[Tuple[int, str]] = []
    for line in txt.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"^(\d{1,4})\s+(.*)$", line)
        if not m:
            continue
        gwno = int(m.group(1))
        name = m.group(2).strip()
        rows.append((gwno, name))
    if not rows:
        raise RuntimeError("Parsed 0 rows from GW text; format may have changed.")
    return rows


def _write_csv(path: str, rows: List[Tuple[int, str]]) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("gwno,country_name\n")
        for gwno, name in rows:
            name2 = str(name).replace('"', '""')
            f.write(f'{gwno},"{name2}"\n')
    os.replace(tmp, path)


def _try_parse_response_as_gw(resp: requests.Response, url: str) -> Optional[List[Tuple[int, str]]]:
    ctype = (resp.headers.get("Content-Type") or "").lower()

    # ZIP
    if url.lower().endswith(".zip") or "zip" in ctype:
        z = zipfile.ZipFile(BytesIO(resp.content))
        names = z.namelist()
        # try txt/csv first
        for ext in (".txt", ".csv", ".dat", ".asc"):
            for n in names:
                if n.lower().endswith(ext):
                    data = z.read(n).decode("utf-8", errors="replace")
                    if _looks_like_gw_states_text(data):
                        return _parse_gw_states_text(data)
        # fallback: try any file
        for n in names:
            data = z.read(n).decode("utf-8", errors="replace")
            if _looks_like_gw_states_text(data):
                return _parse_gw_states_text(data)
        return None

    # Plain text
    text = resp.text
    if _looks_like_gw_states_text(text):
        return _parse_gw_states_text(text)

    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/raw_api/gw_states.csv")
    ap.add_argument("--insecure", action="store_true", help="Disable TLS verification (verify=False)")
    ap.add_argument("--quiet-warn", action="store_true", help="Suppress InsecureRequestWarning")
    ap.add_argument("--debug-links", action="store_true", help="Print candidate links being tried")
    args = ap.parse_args()

    verify = not args.insecure
    if args.quiet_warn and not verify:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    out_path = args.out
    _safe_makedirs(os.path.dirname(out_path))

    html = _get(DATA4_URL, verify=verify).text
    hrefs = _extract_all_hrefs(html, DATA4_URL)

    # Only try links from the same host (avoid external unrelated links)
    base_host = urlparse(DATA4_URL).netloc.lower()
    candidates = [u for u in hrefs if urlparse(u).netloc.lower() == base_host]

    if args.debug_links:
        print(f"[DEBUG] Found {len(candidates)} same-host links on {DATA4_URL}")
        for u in candidates[:200]:
            print("  ", u)

    # Try all same-host links until something looks like GW list
    for u in candidates:
        try:
            resp = _get(u, verify=verify)
        except Exception:
            continue

        rows = _try_parse_response_as_gw(resp, url=u)
        if rows:
            _write_csv(out_path, rows)
            print(f"[OK] Wrote {out_path} rows={len(rows)} from {u}")
            return

    raise RuntimeError("Could not locate a downloadable GW states list from links on data-4.html")


if __name__ == "__main__":
    main()
