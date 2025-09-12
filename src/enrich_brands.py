import argparse
import re
from urllib.parse import urlparse
import pandas as pd


BRAND_HOST_MAP = {
    "big4.com.au": ("BIG4", "BIG4 Holiday Parks"),
    "nrmaparksandresorts.com.au": ("NRMA", "NRMA Parks and Resorts"),
    "discoveryholidayparks.com.au": ("Discovery", "Discovery Parks"),
    "gdayparks.com.au": ("G'Day", "G'Day Parks"),
    "ingeniaholidays.com.au": ("Ingenia Holidays", "Ingenia Communities"),
    "reflectionsnsw.com.au": ("Reflections", "Reflections Holiday Parks"),
    "tasmanholidayparks.com": ("Tasman", "Tasman Holiday Parks"),
    "holidayhaven.com.au": ("Holiday Haven", "Shoalhaven City Council"),
}


BRAND_NAME_PATTERNS = [
    (re.compile(r"\b(big\s*4|big4)\b", re.I), ("BIG4", "BIG4 Holiday Parks")),
    (re.compile(r"\bnrma\b", re.I), ("NRMA", "NRMA Parks and Resorts")),
    (re.compile(r"\bdiscovery\b", re.I), ("Discovery", "Discovery Parks")),
    (re.compile(r"g['’`-]?day", re.I), ("G'Day", "G'Day Parks")),
    (re.compile(r"\bingenia\b", re.I), ("Ingenia Holidays", "Ingenia Communities")),
    (re.compile(r"\breflections?\b", re.I), ("Reflections", "Reflections Holiday Parks")),
    (re.compile(r"\btasman\b", re.I), ("Tasman", "Tasman Holiday Parks")),
    (re.compile(r"holiday\s*haven", re.I), ("Holiday Haven", "Shoalhaven City Council")),
]


def host_from_url(url: str) -> str | None:
    try:
        u = urlparse(url)
        host = u.netloc.lower()
        # strip leading www.
        if host.startswith("www."):
            host = host[4:]
        return host
    except Exception:
        return None


def match_brand_from_host(host: str) -> tuple[str, str] | None:
    if not host:
        return None
    # exact match or suffix match
    for k, v in BRAND_HOST_MAP.items():
        if host == k or host.endswith("." + k) or k in host:
            return v
    return None


def match_brand_from_text(text: str) -> tuple[str, str] | None:
    if not text:
        return None
    for pat, value in BRAND_NAME_PATTERNS:
        if pat.search(text):
            return value
    return None


def enrich_row(row, force=False):
    ob_val = row.get("operator_brand")
    oc_val = row.get("operator_company")
    current = (str(ob_val).strip() if pd.notna(ob_val) else "")
    company = (str(oc_val).strip() if pd.notna(oc_val) else "")
    if current and not force:
        return current, company, row.get("operator_source_url")

    # 1) website host mapping
    website = row.get("website")
    host = host_from_url(str(website)) if pd.notna(website) else None
    m = match_brand_from_host(host) if host else None
    if m:
        brand, comp = m
        return brand, comp, website

    # 2) OSM tags if present
    for col in ("brand", "operator"):
        val = row.get(col)
        if pd.notna(val) and str(val).strip():
            mm = match_brand_from_text(str(val))
            if mm:
                brand, comp = mm
                return brand, comp, website

    # 3) Name heuristic
    name = row.get("name")
    if pd.notna(name) and str(name).strip():
        mm = match_brand_from_text(str(name))
        if mm:
            brand, comp = mm
            return brand, comp, website

    return current or None, company or None, row.get("operator_source_url")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", dest="out", required=True)
    ap.add_argument("--force-overwrite", action="store_true")
    args = ap.parse_args()

    df = pd.read_csv(args.inp)
    # Ensure object dtype for textual fields
    for col in ["operator_brand", "operator_company", "operator_source_url"]:
        if col not in df.columns:
            df[col] = None
        df[col] = df[col].astype("object")

    updated = 0
    for idx, row in df.iterrows():
        brand, comp, url = enrich_row(row, force=args.force_overwrite)
        if brand and (args.force_overwrite or pd.isna(row.get("operator_brand")) or not str(row.get("operator_brand") or "").strip()):
            df.at[idx, "operator_brand"] = brand
            updated += 1
        if comp and (args.force_overwrite or pd.isna(row.get("operator_company")) or not str(row.get("operator_company") or "").strip()):
            df.at[idx, "operator_company"] = comp
        if url and (args.force_overwrite or pd.isna(row.get("operator_source_url")) or not str(row.get("operator_source_url") or "").strip()):
            df.at[idx, "operator_source_url"] = url

    df.to_csv(args.out, index=False)
    print(f"Wrote {args.out} (updated {updated} rows)")


if __name__ == "__main__":
    main()
