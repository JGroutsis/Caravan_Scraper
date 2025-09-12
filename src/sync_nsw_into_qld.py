import argparse
import pandas as pd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nsw", required=True, help="Path to parks_merged_nsw.csv")
    ap.add_argument("--qld", required=True, help="Path to parks_merged_nsw_qld.csv")
    ap.add_argument("--out", required=True, help="Output path (usually same as --qld)")
    args = ap.parse_args()

    nsw_df = pd.read_csv(args.nsw)
    qld_df = pd.read_csv(args.qld)

    # Columns to propagate from NSW file into the combined file for NSW rows only
    cols = [
        "nsw_parcels_count", "nsw_parcel_ids", "nsw_area_sum_sqm",
        "land_parcel_ids", "land_area_sqm", "land_area_source",
    ]

    # Align by osm park_id; fallback to name+coords if needed
    key = "park_id" if "park_id" in nsw_df.columns and "park_id" in qld_df.columns else None
    if key:
        nsw_map = nsw_df.set_index(key)
        qld_df.set_index(key, inplace=True)
        idx = qld_df[qld_df["state"] == "NSW"].index
        for c in cols:
            if c in nsw_map.columns:
                qld_df.loc[idx, c] = nsw_map.loc[idx, c]
        qld_df.reset_index(inplace=True)
    else:
        # Fallback: merge on name+lat+lon
        on = ["name", "latitude", "longitude"]
        merged = qld_df.merge(
            nsw_df[on + cols], how="left", on=on, suffixes=("", "_nsw")
        )
        for c in cols:
            if c + "_nsw" in merged.columns:
                merged.loc[merged["state"] == "NSW", c] = merged.loc[merged["state"] == "NSW", c + "_nsw"]
                merged.drop(columns=[c + "_nsw"], inplace=True)
        qld_df = merged

    qld_df.to_csv(args.out, index=False)
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()

