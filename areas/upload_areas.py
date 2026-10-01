"""Upload areas.gpkg to a GBIF Alert instance as shared (public) areas.

    GBIF_ALERT_URL=https://... GBIF_ALERT_TOKEN=... \\
        uv run --with requests --with geopandas python upload_areas.py ["MSFD marine region" ...]

Optional arguments restrict the upload to areas with these tags.
The token must belong to an operator (superuser): only operators can create
shared areas. An area whose name is already taken among the public areas is
skipped and listed, so the script can be re-run after an interruption.
"""
import os
import sys
import time
from pathlib import Path

import geopandas as gpd
import requests


def main():
    url = os.environ["GBIF_ALERT_URL"].rstrip("/") + "/api/v2/areas/"
    session = requests.Session()
    session.headers["Authorization"] = "Bearer " + os.environ["GBIF_ALERT_TOKEN"]
    areas = gpd.read_file(Path(__file__).parent / "areas.gpkg", layer="areas")
    if sys.argv[1:]:
        areas = areas[areas.tag.isin(sys.argv[1:])]
    created, skipped = 0, []
    for i, a in enumerate(areas.itertuples(), 1):
        payload = {"name": a.name, "geojson": a.geometry.__geo_interface__,
                   "shared": True, "tags": [a.tag]}
        while (r := session.post(url, json=payload, timeout=300)).status_code == 429:
            time.sleep(float(r.headers.get("Retry-After", 60)))
        if r.status_code == 201:
            created += 1
        elif r.status_code == 409:
            skipped.append(a.name)
        else:
            raise SystemExit(f"{a.name}: HTTP {r.status_code} {r.text[:500]}")
        if i % 100 == 0:
            print(f"{i}/{len(areas)}")
    print(f"{created} created, {len(skipped)} skipped (name already taken): {skipped}")


if __name__ == "__main__":
    main()
