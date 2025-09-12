import argparse, pandas as pd, requests, time
from requests import Session
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from .config import QLD_CADASTRE_LAYER_URL

# Reuse HTTP session for connection pooling
_SESSION: Session | None = None

def _get_session() -> Session:
    global _SESSION
    if _SESSION is None:
        _SESSION = requests.Session()
        _SESSION.headers.update({"User-Agent": "caravan-parks/area-qld/0.1"})
    return _SESSION

@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10),
       retry=retry_if_exception_type((requests.RequestException,)))
def _query_parcels_for_point(lat, lon, buffer_m=120):
    params = {
        "f": "json",
        "geometry": f"{{\"x\":{lon},\"y\":{lat},\"spatialReference\":{{\"wkid\":4326}}}}",
        "geometryType": "esriGeometryPoint",
        "inSR": 4326,
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "lot,plan,lotplan,lot_area",
        "distance": buffer_m,
        "units": "esriSRUnit_Meter",
        "returnGeometry": False,
        "returnDistinctValues": False,
        "where": "1=1",
    }
    url = f"{QLD_CADASTRE_LAYER_URL}/query"
    r = _get_session().get(url, params=params, timeout=45)
    r.raise_for_status()
    js = r.json()
    feats = js.get("features", [])
    return feats

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", dest="out", required=True)
    ap.add_argument("--limit", dest="limit", type=int, default=None, help="Process at most this many QLD rows")
    ap.add_argument("--offset", dest="offset", type=int, default=0, help="Skip this many QLD rows before processing")
    ap.add_argument("--sleep", dest="sleep", type=float, default=0.25, help="Seconds to sleep between requests")
    ap.add_argument("--force", dest="force", action="store_true", help="Force re-query even if already enriched")
    args = ap.parse_args()

    df = pd.read_csv(args.inp)
    df["qld_parcels_count"] = 0
    if "qld_checked" not in df.columns:
        df["qld_checked"] = 0

    processed = 0
    skipped = 0
    for idx, row in df.iterrows():
        if row.get("state") != "QLD":
            continue
        if args.offset and skipped < args.offset:
            skipped += 1
            continue
        if args.limit is not None and processed >= args.limit:
            break
        if not args.force:
            las = row.get("land_area_source")
            qld_cnt = row.get("qld_parcels_count")
            lpis_val = row.get("land_parcel_ids")
            has_ids = (pd.notna(lpis_val) and str(lpis_val).strip() != "")
            # Skip if already has QLD parcel info or land_area_source already set to qld_dcdb
            if (row.get("qld_checked") == 1) or (isinstance(las, str) and las == "qld_dcdb") or (pd.notna(qld_cnt) and int(qld_cnt) > 0) or has_ids:
                continue
        lat, lon = row["latitude"], row["longitude"]
        try:
            feats = _query_parcels_for_point(lat, lon)
            df.at[idx, "qld_parcels_count"] = len(feats)
            if feats:
                ids = []
                area = 0.0
                for f in feats:
                    attrs = f.get("attributes", {})
                    pid = attrs.get("lotplan") or ""
                    ids.append(pid)
                    a = attrs.get("lot_area") or 0.0
                    area += float(a)
                # merge with any NSW results if already present
                prev_area = float(df.at[idx, "land_area_sqm"]) if pd.notna(df.at[idx, "land_area_sqm"]) else 0.0
                prev_ids = df.at[idx, "land_parcel_ids"] if pd.notna(df.at[idx, "land_parcel_ids"]) else ""
                df.at[idx, "land_parcel_ids"] = ";".join([p for p in [prev_ids] + ids if p])
                df.at[idx, "land_area_sqm"] = round(prev_area + area, 2) if area else (prev_area or None)
                df.at[idx, "land_area_source"] = "qld_dcdb" if area else df.at[idx, "land_area_source"]
        except Exception as e:
            df.at[idx, "notes"] = f"qld_area_error:{e}"
        # Mark as checked regardless
        df.at[idx, "qld_checked"] = 1
        time.sleep(args.sleep)
        processed += 1

    df.to_csv(args.out, index=False)
    print(f"Wrote {args.out}")

if __name__ == "__main__":
    main()
