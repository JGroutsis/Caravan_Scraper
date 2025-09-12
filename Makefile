SHELL := /bin/bash
.ONESHELL:
.DEFAULT_GOAL := help

# Configurable variables (override like: make all STATES="NSW QLD" LIMIT=500)
VENV ?= .venv
PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

DATA_DIR ?= data
STATES ?= NSW QLD VIC
MAX_PER_STATE ?=

# Batch controls for parcel/address enrichment
LIMIT ?= 500
SLEEP ?=
FORCE ?=
OFFSETS_NSW ?=
OFFSETS_QLD ?=
NSW_START ?= 0
NSW_END ?= 3000
NSW_STEP ?= 500
QLD_START ?= 0
QLD_END ?= 2000
QLD_STEP ?= 500
CONTACT ?=

# Common file paths (under DATA_DIR)
OSM_SEED := $(DATA_DIR)/osm_seed.csv
BRANDS_SEED := $(DATA_DIR)/brands_seed.csv
MERGED := $(DATA_DIR)/parks_merged.csv
NSW := $(DATA_DIR)/parks_merged_nsw.csv
QLD := $(DATA_DIR)/parks_merged_nsw_qld.csv
BRANDS_ENRICHED := $(DATA_DIR)/parks_merged_nsw_qld_brands.csv
MASTER := $(DATA_DIR)/caravan_parks_master.csv
ADDR := $(DATA_DIR)/caravan_parks_master_addr.csv
EXPORT := $(DATA_DIR)/caravan_parks_master_export.csv

.PHONY: help venv fetch brands merge area_nsw_init area_nsw_batch area_nsw_all area_qld_init area_qld_batch area_qld_all enrich_brands classify enrich_addresses_batch export export_from_master export_from_addr all all_quick

help:
	@echo "Make targets (override variables as needed):"
	@echo "  venv                      Create venv and install requirements"
	@echo "  fetch                     Run Overpass fetch → $(OSM_SEED) (STATES='$(STATES)' MAX_PER_STATE=$(MAX_PER_STATE))"
	@echo "  brands                    Build brand seed CSV → $(BRANDS_SEED)"
	@echo "  merge                     Merge/dedupe → $(MERGED)"
	@echo "  area_nsw_init             Initialize NSW file (copy $(MERGED) → $(NSW))"
	@echo "  area_nsw_batch            One NSW batch (LIMIT=$(LIMIT) OFFSET=<required>)"
	@echo "  area_nsw_all              NSW batches for OFFSETS_NSW='$(OFFSETS_NSW)' (LIMIT=$(LIMIT))"
	@echo "  area_qld_init             Initialize QLD file (copy $(NSW) → $(QLD))"
	@echo "  area_qld_batch            One QLD batch (LIMIT=$(LIMIT) OFFSET=<required>)"
	@echo "  area_qld_all              QLD batches for OFFSETS_QLD='$(OFFSETS_QLD)' (LIMIT=$(LIMIT))"
	@echo "  enrich_brands             Infer operator brand/company → $(BRANDS_ENRICHED)"
	@echo "  classify                  Classify → $(MASTER) (input: $(BRANDS_ENRICHED))"
	@echo "  enrich_addresses_batch    One address batch (LIMIT=$(LIMIT) OFFSET=<required> CONTACT='$(CONTACT)')"
	@echo "  export                    Export to schema → $(EXPORT) (auto-picks master or addr)"
	@echo "  all                       Full pipeline with batches (uses OFFSETS_* and LIMIT)"
	@echo "  all_quick                 Quick smoke: small fetch + minimal batches"

venv:
	@if [ ! -x "$(PY)" ]; then python3 -m venv $(VENV); fi
	. $(VENV)/bin/activate; python -V; pip install -r requirements.txt

fetch: venv
	$(PY) -m src.overpass_fetch --states $(STATES) $(if $(MAX_PER_STATE),--max-per-state $(MAX_PER_STATE),) --out $(OSM_SEED)

brands: venv
	$(PY) -m src.brands.run_all --out $(BRANDS_SEED)

merge: venv
	$(PY) -m src.merge_dedupe $(OSM_SEED) $(BRANDS_SEED) --out $(MERGED)

area_nsw_init: venv
	cp -f $(MERGED) $(NSW)
	@echo "Initialized $(NSW) from $(MERGED)"

area_nsw_batch: venv
	@if [ -z "$(OFFSET)" ]; then echo "ERROR: Provide OFFSET, e.g. make area_nsw_batch OFFSET=1000 LIMIT=$(LIMIT)"; exit 2; fi
	$(PY) -m src.area_nsw --in $(NSW) --out $(NSW) --limit $(LIMIT) --offset $(OFFSET) $(if $(SLEEP),--sleep $(SLEEP),) $(if $(FORCE),--force,)

area_nsw_all: venv
	seqs="$(strip $(OFFSETS_NSW))"; \
	if [ -z "$$seqs" ]; then seqs="$$(seq $(NSW_START) $(NSW_STEP) $(NSW_END) | tr '\n' ' ')"; fi; \
	for off in $$seqs; do \
	  echo "NSW batch OFFSET=$$off LIMIT=$(LIMIT)"; \
	  $(PY) -m src.area_nsw --in $(NSW) --out $(NSW) --limit $(LIMIT) --offset $$off $(if $(SLEEP),--sleep $(SLEEP),) $(if $(FORCE),--force,); \
	done

area_qld_init: venv
	cp -f $(NSW) $(QLD)
	@echo "Initialized $(QLD) from $(NSW)"

area_qld_batch: venv
	@if [ -z "$(OFFSET)" ]; then echo "ERROR: Provide OFFSET, e.g. make area_qld_batch OFFSET=1000 LIMIT=$(LIMIT)"; exit 2; fi
	$(PY) -m src.area_qld --in $(QLD) --out $(QLD) --limit $(LIMIT) --offset $(OFFSET) $(if $(SLEEP),--sleep $(SLEEP),) $(if $(FORCE),--force,)

area_qld_all: venv
	seqs="$(strip $(OFFSETS_QLD))"; \
	if [ -z "$$seqs" ]; then seqs="$$(seq $(QLD_START) $(QLD_STEP) $(QLD_END) | tr '\n' ' ')"; fi; \
	for off in $$seqs; do \
	  echo "QLD batch OFFSET=$$off LIMIT=$(LIMIT)"; \
	  $(PY) -m src.area_qld --in $(QLD) --out $(QLD) --limit $(LIMIT) --offset $$off $(if $(SLEEP),--sleep $(SLEEP),) $(if $(FORCE),--force,); \
	done

enrich_brands: venv
	$(PY) -m src.enrich_brands --in $(QLD) --out $(BRANDS_ENRICHED)

classify: venv
	$(PY) -m src.classify --in $(BRANDS_ENRICHED) --out $(MASTER)

enrich_addresses_batch: venv
	@if [ -z "$(OFFSET)" ]; then echo "ERROR: Provide OFFSET, e.g. make enrich_addresses_batch OFFSET=0 LIMIT=$(LIMIT) CONTACT=you@example.com"; exit 2; fi
	@if [ -z "$(CONTACT)" ]; then echo "WARN: CONTACT not set; consider CONTACT=email for Nominatim UA"; fi
	@if [ ! -f "$(ADDR)" ]; then cp -f $(MASTER) $(ADDR); fi
	$(PY) -m src.enrich_addresses --in $(ADDR) --out $(ADDR) --limit $(LIMIT) --offset $(OFFSET) $(if $(CONTACT),--contact "$(CONTACT)",)

export: venv
	@if [ -f "$(ADDR)" ]; then IN="$(ADDR)"; else IN="$(MASTER)"; fi; \
	$(PY) -m src.export_to_schema --in $$IN --out $(EXPORT)

all: fetch brands merge area_nsw_init area_nsw_all area_qld_init area_qld_all enrich_brands classify export
	@echo "Pipeline complete → $(EXPORT)"

all_quick: MAX_PER_STATE=10
all_quick: LIMIT=200
all_quick: OFFSETS_NSW=0
all_quick: OFFSETS_QLD=0
all_quick: fetch brands merge area_nsw_init area_nsw_all area_qld_init area_qld_all enrich_brands classify export
	@echo "Quick pipeline complete → $(EXPORT)"
