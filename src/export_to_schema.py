import argparse
import pandas as pd
from .export_schema import SCHEMA


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", dest="out", required=True)
    args = ap.parse_args()

    df = pd.read_csv(args.inp)

    # Ensure all schema columns exist
    for col in SCHEMA:
        if col not in df.columns:
            df[col] = None

    # Reorder and drop extras
    out = df[SCHEMA].copy()
    out.to_csv(args.out, index=False)
    print(f"Wrote {args.out} with {len(out)} rows")


if __name__ == "__main__":
    main()

