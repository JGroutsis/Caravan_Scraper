import argparse, pandas as pd
from .big4 import fetch_big4
from .gday import fetch_gday
from .nrma import fetch_nrma
from .reflections import fetch_reflections
from .discovery import fetch_discovery
from .ingenia import fetch_ingenia

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    frames = []
    cols = [
        "park_id","name","latitude","longitude","state",
        "operator_brand","operator_company","operator_source_url","source_primary"
    ]
    for fn in [fetch_big4, fetch_gday, fetch_nrma, fetch_reflections, fetch_discovery, fetch_ingenia]:
        try:
            df = fn()
            if df is not None and not df.empty:
                # ensure expected columns exist
                for c in cols:
                    if c not in df.columns:
                        df[c] = None
                frames.append(df[cols])
        except Exception as e:
            print(f"Warning: {fn.__name__} failed: {e}")
    out = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=cols)
    out.to_csv(args.out, index=False)
    print(f"Wrote {args.out} with {len(out)} rows")

if __name__ == "__main__":
    main()
