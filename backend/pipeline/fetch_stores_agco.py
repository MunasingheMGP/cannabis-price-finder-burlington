import math
import pandas as pd
import requests
from db_config import get_engine, write_df

#  CONFIG 
AGCO_BASE     = (
    "https://services9.arcgis.com"
    "/8LLh665FxwX7bxLB/arcgis/rest/services"
)
AGCO_FALLBACK = "Authorized_to_open_20250620"

CENTER_LAT = 43.3255
CENTER_LON = -79.7990
RADIUS_KM  = 35

HEADERS = {"User-Agent": "Mozilla/5.0"}


#  HAVERSINE 
def haversine(lat1, lon1, lat2, lon2):
    r    = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a    = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return 2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a))


#  AUTO-DETECT LATEST AGCO SERVICE 
def get_latest_service():
    try:
        r = requests.get(f"{AGCO_BASE}?f=json", headers=HEADERS, timeout=20)
        r.raise_for_status()
        services = [
            s["name"]
            for s in r.json().get("services", [])
            if "Authorized_to_open" in s["name"]
        ]
        if services:
            latest = sorted(services)[-1]
            print(f"Auto-detected service: {latest}")
            return latest
    except Exception as e:
        print(f"Service discovery failed ({e}), using fallback.")
    return AGCO_FALLBACK


#  FETCH ALL AGCO STORES 
def fetch_stores(service_name):
    url    = f"{AGCO_BASE}/{service_name}/FeatureServer/0/query"
    params = {
        "where": "1=1", "outFields": "*",
        "returnGeometry": "false", "f": "json",
        "resultOffset": 0, "resultRecordCount": 2000,
    }
    r    = requests.get(url, params=params, headers=HEADERS, timeout=60)
    r.raise_for_status()
    data = r.json()
    if "features" not in data:
        raise ValueError(f"Unexpected response: {data}")
    rows = [x["attributes"] for x in data["features"]]
    return pd.DataFrame(rows)


#  MAIN 
def main():
    engine  = get_engine()
    service = get_latest_service()
    df      = fetch_stores(service)
    print(f"Total AGCO stores downloaded: {len(df)}")

    # distance filter
    df["distance_km"] = df.apply(
        lambda x: haversine(
            CENTER_LAT, CENTER_LON,
            float(x["Latitude"]), float(x["Longitude"]),
        ),
        axis=1,
    )
    df = df[df["distance_km"] <= RADIUS_KM].copy()

    # rename to standard columns
    rename = {
        "PremisesName": "store_name",
        "Address":      "address",
        "City":         "city",
        "PostalCode":   "postal_code",
        "Website":      "website",
    }
    df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})

    # placeholders — enrich_store_contacts will fill these
    df["phone_number"]       = "Pending"
    df["hours_of_operation"] = "Pending"
    df["owner_details"]      = "Not publicly disclosed"

    keep  = [
        "store_name", "address", "city", "postal_code",
        "phone_number", "hours_of_operation",
        "owner_details", "website", "distance_km",
    ]
    final = df[[c for c in keep if c in df.columns]]

    #  Write to PostgreSQL 
    write_df(final, "stores_master", engine, if_exists="replace")
    print(f"Stores within {RADIUS_KM} km: {len(final)}")


if __name__ == "__main__":
    main()
