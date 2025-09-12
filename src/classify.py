import argparse, pandas as pd, re, datetime

HOLIDAY_BRANDS = {"BIG4","NRMA","Discovery","G'Day","Gday","Reflections","Ingenia Holidays","Tasman","Holiday Haven"}
EXCLUDE_PATTERNS = re.compile(r"\b(lifestyle|over\s*50s|retirement|village|manufactured\s*home|lakeside lifestyle)\b", re.I)

def classify_row(row):
    name_val = row.get("name")
    brand_val = row.get("operator_brand")
    tourism_val = row.get("tourism")
    name = (str(name_val) if pd.notna(name_val) else "")
    brand = (str(brand_val) if pd.notna(brand_val) else "")
    tourism = (str(tourism_val) if pd.notna(tourism_val) else "")
    notes_val = row.get("notes")
    notes = (str(notes_val).lower() if pd.notna(notes_val) else "")
    cat = "unknown"
    # Exclude built communities
    if EXCLUDE_PATTERNS.search(name):
        cat = "built_community"
    elif brand in HOLIDAY_BRANDS or tourism in ("caravan_site","camp_site"):
        # If camp_site without caravan, mark camp
        if tourism == "camp_site" and ("caravan" not in (name.lower())):
            cat = "camp"
        else:
            cat = "holiday"
    # Mixed use heuristics
    if "permanent" in notes or "long-stay" in notes:
        cat = "mixed"
    return cat

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", dest="out", required=True)
    args = ap.parse_args()
    df = pd.read_csv(args.inp)
    df["category"] = df.apply(classify_row, axis=1)
    df["confidence"] = 0.6
    df["needs_review"] = (df["category"].isin(["unknown","mixed"]) | df["name"].isna()).astype(int)
    df["date_collected_utc"] = datetime.datetime.utcnow().isoformat()
    df.to_csv(args.out, index=False)
    print(f"Wrote {args.out}")

if __name__ == "__main__":
    main()
