import json, time, sys, argparse, logging, random
from typing import List, Dict, Any
import pandas as pd
import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from .config import OVERPASS_ENDPOINTS, OVERPASS_TIMEOUT, STATE_NAMES, OSM_NAME_REGEX

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

def STATE_AREA_QUERY(state_name: str, limit: int | None = None) -> str:
    limit_clause = f" {limit}" if isinstance(limit, int) and limit > 0 else ""
    return f"""
[out:json][timeout:{OVERPASS_TIMEOUT}];
 area["name"="{state_name}"]["boundary"="administrative"]["admin_level"="4"]->.searchArea;
(
  node["tourism"~"^(caravan_site|camp_site)$"](area.searchArea);
  way["tourism"~"^(caravan_site|camp_site)$"](area.searchArea);
  relation["tourism"~"^(caravan_site|camp_site)$"](area.searchArea);
  node["name"~"{OSM_NAME_REGEX}",i](area.searchArea);
  way["name"~"{OSM_NAME_REGEX}",i](area.searchArea);
  relation["name"~"{OSM_NAME_REGEX}",i](area.searchArea);
);
out center tags{limit_clause};
"""

class OverpassError(Exception):
    pass

@retry(stop=stop_after_attempt(4), wait=wait_exponential(min=2, max=30),
       retry=retry_if_exception_type((OverpassError, requests.RequestException)))
def _call_overpass(query: str) -> Dict[str, Any]:
    # Try all endpoints in random order for resilience
    endpoints = OVERPASS_ENDPOINTS[:]
    random.shuffle(endpoints)
    last_err: Exception | None = None
    for endpoint in endpoints:
        try:
            resp = requests.post(endpoint, data={"data": query}, timeout=150)
            if resp.status_code != 200:
                snippet = (resp.text or "").strip().replace("\n", " ")
                if len(snippet) > 1000:
                    snippet = snippet[:1000] + "..."
                raise OverpassError(f"{endpoint} HTTP {resp.status_code}: {snippet}")
            try:
                return resp.json()
            except Exception as e:
                raise OverpassError(f"Invalid JSON from {endpoint}") from e
        except Exception as e:
            last_err = e
            continue
    # If all endpoints failed in this attempt, raise the last error to trigger retry
    raise OverpassError(str(last_err) if last_err else "All Overpass endpoints failed")

def _elements_to_rows(elements: List[Dict[str, Any]], state: str) -> List[Dict[str, Any]]:
    rows = []
    for el in elements:
        el_type = el.get("type")
        el_id = el.get("id")
        tags = el.get("tags", {}) or {}
        name = tags.get("name")
        lat = el.get("lat")
        lon = el.get("lon")
        if (lat is None or lon is None) and el.get("center"):
            lat = el["center"].get("lat")
            lon = el["center"].get("lon")
        if lat is None or lon is None:
            continue
        row = {
            "park_id": f"osm:{el_type}:{el_id}",
            "osm_type": el_type,
            "osm_id": el_id,
            "name": name,
            "latitude": lat,
            "longitude": lon,
            "state": state,
            "addr:housenumber": tags.get("addr:housenumber"),
            "addr:street": tags.get("addr:street"),
            "addr:city": tags.get("addr:city") or tags.get("addr:suburb"),
            "addr:postcode": tags.get("addr:postcode"),
            "website": tags.get("website"),
            "phone": tags.get("phone"),
            "email": tags.get("email"),
            "tourism": tags.get("tourism"),
            "source_primary": "osm_overpass",
            # brand/operator hints for later enrichment
            "brand": tags.get("brand"),
            "operator": tags.get("operator"),
        }
        rows.append(row)
    return rows

def fetch_state(state_code: str, max_per_state: int | None = None) -> pd.DataFrame:
    state_name = STATE_NAMES[state_code]
    q = STATE_AREA_QUERY(state_name, max_per_state)
    data = _call_overpass(q)
    rows = _elements_to_rows(data.get("elements", []), state_code)
    df = pd.DataFrame(rows)
    # drop exact dupes if any
    df = df.drop_duplicates(subset=["park_id"]) if not df.empty else df
    return df

def fetch_osm_for_states(states: List[str], max_per_state: int | None = None) -> pd.DataFrame:
    frames = []
    for s in states:
        logging.info(f"Fetching OSM data for {s}")
        frames.append(fetch_state(s, max_per_state=max_per_state))
        time.sleep(1)
    df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    return df

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--states", nargs="+", required=True, help="States like NSW QLD VIC")
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-per-state", type=int, default=None, help="Optional limit per state for debugging")
    args = ap.parse_args()
    df = fetch_osm_for_states(args.states, max_per_state=args.max_per_state)
    if df.empty:
        logging.warning("No features returned from Overpass. Check queries.")
    df.to_csv(args.out, index=False)
    print(f"Wrote {args.out} with {len(df)} rows")


if __name__ == "__main__":
    main()
