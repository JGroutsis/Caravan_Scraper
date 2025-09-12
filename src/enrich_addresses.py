import argparse
import csv
import time
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import pandas as pd
import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type


NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"


@dataclass
class Addr:
    address_line: Optional[str] = None
    suburb: Optional[str] = None
    postcode: Optional[str] = None
    lga: Optional[str] = None


def _mk_address_line(addr: Dict[str, str]) -> Optional[str]:
    hn = addr.get("house_number")
    road = addr.get("road") or addr.get("pedestrian") or addr.get("footway") or addr.get("path") or addr.get("place")
    if hn and road:
        return f"{hn} {road}"
    return road or None


def _pick_suburb(addr: Dict[str, str]) -> Optional[str]:
    for k in ("suburb", "town", "village", "locality", "hamlet", "neighbourhood", "city_district"):
        if addr.get(k):
            return addr.get(k)
    # Fall back to city if small places don't exist
    return addr.get("city") or None


def _pick_lga(addr: Dict[str, str]) -> Optional[str]:
    # Preferred keys in AU OSM data
    for k in ("local_government_area", "municipality"):
        if addr.get(k):
            return addr.get(k)
    # Fallbacks that often contain LGA-like values (e.g., "Shire of X", "City of Y")
    for k in ("city", "county"):
        if addr.get(k):
            val = addr.get(k)
            # Sanity: prefer values that look like councils/shires
            if any(word in val.lower() for word in ("shire", "city", "council", "regional")):
                return val
    return None


class Geocoder:
    def __init__(self, contact: Optional[str] = None, pause_s: float = 1.1):
        self.session = requests.Session()
        ua = "caravan-parks-starter-kit/0.1"
        if contact:
            ua += f" ({contact})"
        self.session.headers.update({"User-Agent": ua})
        self.pause_s = pause_s

    @retry(stop=stop_after_attempt(4), wait=wait_exponential(min=2, max=30),
           retry=retry_if_exception_type((requests.RequestException,)))
    def reverse(self, lat: float, lon: float) -> Addr:
        params = {
            "format": "jsonv2",
            "lat": f"{lat}",
            "lon": f"{lon}",
            "zoom": 18,
            "addressdetails": 1,
        }
        r = self.session.get(NOMINATIM_URL, params=params, timeout=30)
        if r.status_code == 429:
            # Rate limited; raise to trigger retry/backoff
            raise requests.RequestException("HTTP 429 from Nominatim")
        r.raise_for_status()
        js = r.json()
        addr = js.get("address", {}) or {}
        out = Addr(
            address_line=_mk_address_line(addr),
            suburb=_pick_suburb(addr),
            postcode=addr.get("postcode"),
            lga=_pick_lga(addr),
        )
        # Gentle rate limiting — Nominatim usage policy
        time.sleep(self.pause_s)
        return out


def _load_cache(path: Optional[str]) -> Dict[Tuple[int, int], Addr]:
    cache: Dict[Tuple[int, int], Addr] = {}
    if not path:
        return cache
    try:
        with open(path, "r", newline="") as f:
            rdr = csv.DictReader(f)
            for row in rdr:
                key = (int(row["lat_e6"]), int(row["lon_e6"]))
                cache[key] = Addr(
                    address_line=row.get("address_line") or None,
                    suburb=row.get("suburb") or None,
                    postcode=row.get("postcode") or None,
                    lga=row.get("lga") or None,
                )
    except FileNotFoundError:
        pass
    return cache


def _save_cache(path: Optional[str], cache: Dict[Tuple[int, int], Addr]):
    if not path:
        return
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["lat_e6", "lon_e6", "address_line", "suburb", "postcode", "lga"])
        w.writeheader()
        for (la, lo), a in cache.items():
            w.writerow({
                "lat_e6": la, "lon_e6": lo,
                "address_line": a.address_line or "",
                "suburb": a.suburb or "",
                "postcode": a.postcode or "",
                "lga": a.lga or "",
            })


def _e6(lat: float, lon: float) -> Tuple[int, int]:
    return int(round(lat * 1e6)), int(round(lon * 1e6))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", dest="out", required=True)
    ap.add_argument("--contact", dest="contact", default=None, help="Contact info for Nominatim User-Agent")
    ap.add_argument("--limit", type=int, default=None, help="Max rows to process")
    ap.add_argument("--offset", type=int, default=0, help="Rows to skip before processing")
    ap.add_argument("--force-overwrite", action="store_true", help="Overwrite existing address fields")
    ap.add_argument("--cache", default=None, help="Path for persistent geocode cache (defaults next to --in file)")
    args = ap.parse_args()

    df = pd.read_csv(args.inp)

    # Prepare output columns according to export schema naming
    if "address_line" not in df.columns:
        df["address_line"] = None
    if "suburb" not in df.columns:
        df["suburb"] = None
    if "postcode" not in df.columns:
        df["postcode"] = None
    if "lga" not in df.columns:
        df["lga"] = None

    # First map any OSM addr:* tags into our columns when available
    if "addr:street" in df.columns:
        # Combine house number + street
        def mk_line(row):
            if pd.notna(row.get("addr:housenumber")) and pd.notna(row.get("addr:street")):
                return f"{str(row['addr:housenumber']).strip()} {str(row['addr:street']).strip()}".strip()
            if pd.notna(row.get("addr:street")):
                return str(row.get("addr:street")).strip()
            return None
        if args.force_overwrite:
            df["address_line"] = df.apply(mk_line, axis=1)
        else:
            df["address_line"] = df["address_line"].where(df["address_line"].notna(), df.apply(mk_line, axis=1))
    if "addr:city" in df.columns:
        if args.force_overwrite:
            df["suburb"] = df["addr:city"]
        else:
            df["suburb"] = df["suburb"].where(df["suburb"].notna(), df["addr:city"])
    if "addr:postcode" in df.columns:
        if args.force_overwrite:
            df["postcode"] = df["addr:postcode"]
        else:
            df["postcode"] = df["postcode"].where(df["postcode"].notna(), df["addr:postcode"])

    # Reverse geocode only when something is missing (or force_overwrite)
    geocoder = Geocoder(contact=args.contact)
    # Default cache path lives alongside the input file to avoid CWD issues
    cache_path = args.cache
    if cache_path is None:
        import os
        cache_path = os.path.join(os.path.dirname(os.path.abspath(args.inp)), "geocode_cache.csv")
    cache = _load_cache(cache_path)

    processed = 0
    skipped = 0
    for idx, row in df.iterrows():
        if args.limit is not None and processed >= args.limit:
            break
        if args.offset and skipped < args.offset:
            skipped += 1
            continue
        lat = row.get("latitude")
        lon = row.get("longitude")
        try:
            if pd.isna(lat) or pd.isna(lon):
                continue
            need = (
                args.force_overwrite or
                pd.isna(row.get("address_line")) or pd.isna(row.get("suburb")) or pd.isna(row.get("postcode")) or pd.isna(row.get("lga")) or
                (not str(row.get("address_line") or "").strip()) or (not str(row.get("suburb") or "").strip()) or (not str(row.get("postcode") or "").strip()) or (not str(row.get("lga") or "").strip())
            )
            if not need:
                continue
            key = _e6(float(lat), float(lon))
            if key in cache:
                a = cache[key]
            else:
                a = geocoder.reverse(float(lat), float(lon))
                cache[key] = a
            # Write back
            if args.force_overwrite or not str(df.at[idx, "address_line"] or "").strip():
                df.at[idx, "address_line"] = a.address_line
            if args.force_overwrite or not str(df.at[idx, "suburb"] or "").strip():
                df.at[idx, "suburb"] = a.suburb
            if args.force_overwrite or not str(df.at[idx, "postcode"] or "").strip():
                df.at[idx, "postcode"] = a.postcode
            if args.force_overwrite or not str(df.at[idx, "lga"] or "").strip():
                df.at[idx, "lga"] = a.lga
            processed += 1
        except Exception as e:
            # Non-fatal; continue
            continue

    # Save cache and output
    _save_cache(cache_path, cache)
    df.to_csv(args.out, index=False)
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
