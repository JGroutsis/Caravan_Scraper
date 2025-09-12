from dataclasses import dataclass
from typing import List

OVERPASS_ENDPOINTS: List[str] = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]

# ArcGIS REST endpoints
NSW_CADASTRE_LAYER_URL = "https://maps.six.nsw.gov.au/arcgis/rest/services/public/NSW_Cadastre/MapServer/9"  # Lot
QLD_CADASTRE_LAYER_URL = "https://spatial-gis.information.qld.gov.au/arcgis/rest/services/PlanningCadastre/LandParcelPropertyFramework/MapServer/4"  # Cadastral parcels

# Optional Vicmap placeholders - fill when you have credentials or an open endpoint
VICMAP_LAYER_URL = ""  # TODO: set WFS or REST layer for parcels if available

STATE_NAMES = {
    "NSW": "New South Wales",
    "QLD": "Queensland",
    "VIC": "Victoria"
}

# Query tuning
OVERPASS_TIMEOUT = 180  # seconds
# Regex without inline flags; we pass the case-insensitive flag separately in the query.
OSM_NAME_REGEX = "(caravan|holiday park|tourist park)"
