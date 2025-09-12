import pandas as pd

# These are stubs. Implement with requests+BeautifulSoup or the site's documented API if available.
# Each function should return a DataFrame with at least:
# park_id, name, latitude, longitude, state, operator_brand, operator_company, operator_source_url, source_primary

def fetch_nrma() -> pd.DataFrame:
    cols = ["park_id","name","latitude","longitude","state","operator_brand","operator_company","operator_source_url","source_primary"]
    return pd.DataFrame(columns=cols)
