import argparse, pandas as pd, numpy as np
from rapidfuzz import fuzz
from shapely.geometry import Point
from shapely.ops import nearest_points
import geopandas as gpd

def _norm_name(s):
    if not isinstance(s, str):
        return ""
    return ''.join(ch.lower() for ch in s if ch.isalnum() or ch.isspace()).strip()

def _fuzzy(a,b):
    return fuzz.token_set_ratio(_norm_name(a), _norm_name(b))

def _geo_dedup(df: pd.DataFrame, radius_m=200) -> pd.DataFrame:
    # cluster by proximity then within each cluster pick best name
    gdf = gpd.GeoDataFrame(df.copy(), geometry=gpd.points_from_xy(df.longitude, df.latitude), crs="EPSG:4326")
    gdf = gdf.to_crs(3857)
    gdf["cluster"] = (gdf.geometry.x.round(-1).astype(int).astype(str) + ":" + gdf.geometry.y.round(-1).astype(int).astype(str))
    # simple groupby, then within group merge duplicates by fuzzy name
    out_rows = []
    for _, grp in gdf.groupby("cluster"):
        cand = grp.copy()
        used = set()
        for i, row in cand.iterrows():
            if i in used:
                continue
            block = [i]
            for j, row2 in cand.iterrows():
                if j==i or j in used:
                    continue
                # distance filter ~ radius_m
                if row.geometry.distance(row2.geometry) <= radius_m:
                    if _fuzzy(row.get("name"), row2.get("name")) >= 80 or (row.get("name") and row2.get("name") and _norm_name(row["name"])==_norm_name(row2["name"])):
                        block.append(j)
            used.update(block)
            merged = cand.loc[block].sort_values(by=["source_primary"], na_position="last").iloc[0].copy()
            # Merge in helpful fields from other rows in the block if missing on the chosen base
            prefer_cols = [
                "operator_brand", "operator_company", "operator_source_url",
                "website", "phone", "email",
            ]
            for col in prefer_cols:
                if col in cand.columns and (pd.isna(merged.get(col)) or str(merged.get(col) or "").strip() == ""):
                    for k in block:
                        val = cand.loc[k].get(col)
                        if pd.notna(val) and str(val).strip():
                            merged[col] = val
                            break
            merged["source_secondary"] = ";".join(str(cand.loc[k].get("source_primary")) for k in block if k!=merged.name)
            out_rows.append(merged)
    out = pd.DataFrame(out_rows).drop(columns=["geometry","cluster"]).reset_index(drop=True)
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("inputs", nargs="+", help="CSV inputs to merge")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    frames = [pd.read_csv(p) for p in args.inputs if p]
    df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if df.empty:
        print("No input rows.")
        pd.DataFrame().to_csv(args.out, index=False)
        return
    # Basic normalisation
    df["name"] = df["name"].fillna("")
    df = df.dropna(subset=["latitude","longitude"], how="any")
    merged = _geo_dedup(df)
    merged.to_csv(args.out, index=False)
    print(f"Wrote {args.out} with {len(merged)} rows")


if __name__ == "__main__":
    main()
