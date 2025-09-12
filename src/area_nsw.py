import argparse, pandas as pd, requests, math, time
from requests import Session
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from urllib.parse import urlencode
from .config import NSW_CADASTRE_LAYER_URL

# Reuse HTTP session for connection pooling
_SESSION: Session | None = None

def _get_session() -> Session:
    global _SESSION
    if _SESSION is None:
        _SESSION = requests.Session()
        _SESSION.headers.update({"User-Agent": "caravan-parks/area-nsw/0.1"})
    return _SESSION

@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10),
       retry=retry_if_exception_type((requests.RequestException,)))
def _query_parcels_for_point(lat, lon, buffer_m=120):
    # ArcGIS expects geometry as point in WGS84 or Web Mercator. Use a distance buffer.
    params = {
        "f": "json",
        "geometry": f"{{\"x\":{lon},\"y\":{lat},\"spatialReference\":{{\"wkid\":4326}}}}",
        "geometryType": "esriGeometryPoint",
        "inSR": 4326,
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "planlabel,lotnumber,shape_Area",
        "distance": buffer_m,
        "units": "esriSRUnit_Meter",
        "returnGeometry": False,
        "returnDistinctValues": False,
        "where": "1=1",
    }
    url = f"{NSW_CADASTRE_LAYER_URL}/query"
    r = _get_session().get(url, params=params, timeout=45)
    r.raise_for_status()
    js = r.json()
    feats = js.get("features", [])
    return feats

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", dest="out", required=True)
    ap.add_argument("--limit", dest="limit", type=int, default=None, help="Process at most this many NSW rows")
    ap.add_argument("--offset", dest="offset", type=int, default=0, help="Skip this many NSW rows before processing")
    ap.add_argument("--sleep", dest="sleep", type=float, default=0.25, help="Seconds to sleep between requests")
    ap.add_argument("--force", dest="force", action="store_true", help="Force re-query even if already enriched")
    args = ap.parse_args()

    df = pd.read_csv(args.inp)
    df["nsw_parcels_count"] = 0
    df["nsw_parcel_ids"] = ""
    df["nsw_area_sum_sqm"] = None
    if "nsw_checked" not in df.columns:
        df["nsw_checked"] = 0

    processed = 0
    skipped = 0
    for idx, row in df.iterrows():
        if row.get("state") != "NSW":
            continue
        if args.offset and skipped < args.offset:
            skipped += 1
            continue
        if args.limit is not None and processed >= args.limit:
            break
        # Skip rows already enriched unless forcing
        if not args.force:
            las = row.get("land_area_source")
            nsw_cnt = row.get("nsw_parcels_count")
            lpis_val = row.get("land_parcel_ids")
            has_ids = (pd.notna(lpis_val) and str(lpis_val).strip() != "")
            already = (row.get("nsw_checked") == 1) or (isinstance(las, str) and las == "nsw_dcdb") or (pd.notna(nsw_cnt) and int(nsw_cnt) > 0) or has_ids
            if already:
                continue
        lat, lon = row["latitude"], row["longitude"]
        try:
            feats = _query_parcels_for_point(lat, lon)
            df.at[idx, "nsw_parcels_count"] = len(feats)
            if feats:
                ids = []
                area = 0.0
                for f in feats:
                    attrs = f.get("attributes", {})
                    pid = attrs.get("planlabel") or ""
                    if attrs.get("lotnumber"):
                        pid = f"{attrs.get('lotnumber')}/{pid}" if pid else str(attrs.get("lotnumber"))
                    ids.append(pid)
                    a = attrs.get("shape_Area") or 0.0
                    area += float(a)
                df.at[idx, "land_parcel_ids"] = ";".join([p for p in ids if p])
                df.at[idx, "land_area_sqm"] = round(area, 2)
                df.at[idx, "land_area_source"] = "nsw_dcdb"
        except Exception as e:
            df.at[idx, "notes"] = f"nsw_area_error:{e}"
        # Mark as checked regardless of hits to avoid re-querying endlessly
        df.at[idx, "nsw_checked"] = 1
        time.sleep(args.sleep)  # be kind to the server
        processed += 1

    df.to_csv(args.out, index=False)
    print(f"Wrote {args.out}")

if __name__ == "__main__":
    main()
