# Caravan Parks Data Pipeline (NSW, QLD, VIC)

**Status:** Starter kit scaffold created 2025-09-11 02:34 UTC.  
**Audience:** Internal only.  
**Goal:** Build a reproducible pipeline that compiles an *as-complete-as-practical* list of caravan and holiday parks across NSW, QLD and VIC, and enriches each record with operator brand and parcel area.

This kit is designed for **first‑time** spatial projects. Follow steps in order. Every script is small and self‑contained.

---

## Quick start

### 0) Set up Python
```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 1) Pull a base list from OpenStreetMap (OSM)
```bash
python -m src.overpass_fetch --states NSW QLD VIC --out data/osm_seed.csv
```
This queries Overpass for `tourism=caravan_site` and `tourism=camp_site`, plus name filters like 'caravan', 'holiday park', 'tourist park'. It returns coordinates, names and any address tags present.

### 2) Add operator brands (optional first pass)
Edit `src/brands/*.py` to enable network fetchers. When ready:
```bash
python -m src.brands.run_all --out data/brands_seed.csv
```

### 3) Merge and dedupe
```bash
python -m src.merge_dedupe data/osm_seed.csv data/brands_seed.csv --out data/parks_merged.csv
```

### 4) Compute parcel areas
- NSW parcels via ArcGIS REST MapServer Lot layer.  
- QLD DCDB parcels via ArcGIS REST MapServer Cadastral parcels layer.
```bash
python -m src.area_nsw --in data/parks_merged.csv --out data/parks_merged_nsw.csv
python -m src.area_qld --in data/parks_merged_nsw.csv --out data/parks_merged_nsw_qld.csv
```
Victoria requires Vicmap access. See README section **Vicmap notes**.

### 5) Classify and export
```bash
python -m src.classify --in data/parks_merged_nsw_qld.csv --out data/caravan_parks_master.csv
```

---

## Output schema

See `src/export_schema.py` for the canonical schema. Key fields:
- `park_id`, `name`
- `state`, `address_line`, `suburb`, `postcode`, `lga`
- `latitude`, `longitude`
- `website`, `phone`, `email`
- `category`  (holiday, residential, mixed, camp, unknown)
- `operator_brand`, `operator_company`, `operator_source_url`
- `opening_status`  (active, closed, seasonal, unknown)
- `permanent_sites`, `tourist_sites`  (where available)
- `land_parcel_ids`  (semicolon list)
- `land_area_sqm`, `land_area_source`  (nsw_dcdb, qld_dcdb, vicmap, unknown)
- `source_primary`, `source_secondary`
- `confidence`, `needs_review`, `date_collected_utc`, `notes`

---

## What is free and what needs registration

- **Free**  
  - OSM Overpass API for feature discovery. Use moderate request sizes and caching.  
  - NSW cadastre query via ArcGIS REST (Lot layer).  
  - QLD DCDB parcels via ArcGIS REST (Cadastral parcels).

- **Registration**  
  - **Vicmap** Property parcels for Victoria. You may use WMS/WFS or REST via Vicmap as a Service with an account.  
  - **ATDW ATLAS API** for tourism business listings. Useful for operator names. Requires free distributor registration.

See inline links in this README and comments in the code.

---

## Vicmap notes (Victoria parcel areas)

Parcel polygons for Victoria are available via Vicmap Property. You will likely need a free account or licence before accessing WFS or REST services. Once you have an endpoint and credentials, copy them into `src/config.py` and run a Victoria area enrichment pass similar to NSW and QLD. Until then, `land_area_sqm` will remain blank for VIC and `land_area_source` will be `unknown`.

---

## Heuristics and definitions

- **Included:** holiday parks and caravan parks, plus mixed‑use parks that allow longer stays but are not built manufactured home estates.  
- **Excluded:** pure lifestyle villages, retirement villages, built manufactured home communities with no touring or short‑stay caravan sites.

Classification is rule‑based and conservative. Anything ambiguous is marked `needs_review=1`.

---

## Re‑running and provenance

Every script stamps `date_collected_utc` and writes `source_*` URLs. You can re‑run any step and it will update incrementally by `park_id` and name+coordinates blocking. Keep the CSVs in `data/` under version control.

---

## Commands you will use most

```bash
# Base discovery
python -m src.overpass_fetch --states NSW QLD VIC --out data/osm_seed.csv

# Merge brand sources
python -m src.brands.run_all --out data/brands_seed.csv

# Merge and dedupe
python -m src.merge_dedupe data/osm_seed.csv data/brands_seed.csv --out data/parks_merged.csv

# Parcel area
python -m src.area_nsw --in data/parks_merged.csv --out data/parks_merged_nsw.csv
python -m src.area_qld --in data/parks_merged_nsw.csv --out data/parks_merged_nsw_qld.csv

# Classification
python -m src.classify --in data/parks_merged_nsw_qld.csv --out data/caravan_parks_master.csv
```

---

## Disclaimers

- Overpass and public MapServer endpoints have rate limits. Keep batch sizes small and cache responses.  
- Operator is best‑effort from brand directories and park websites. Land **ownership** is out of scope here.  
- Parcel area sums parcels that intersect a buffered park point. Large properties may include non‑operational land, so review any unusually large totals.  

