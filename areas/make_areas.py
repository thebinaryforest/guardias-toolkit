"""Build the GuardIAS starter set of shared filter areas (areas.gpkg).

    uv run --with requests --with geopandas --with 'shapely>=2.1' --with pyproj python make_areas.py

Writes one layer, one feature per area, with `name` and `tag` columns, in
EPSG:4326. upload_areas.py sends it to a GBIF Alert instance. Sources,
licences and processing are described in README.md.
"""
import csv
import io
import json
import zipfile
from functools import cache
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests
import shapely
from shapely.geometry import MultiPolygon, Polygon, box

HERE = Path(__file__).parent
MASK = HERE.parent / "eez_polygons" / "wider_europe_eez_land_hires.geojson"
EUROPE_BOX = box(-45, 20, 60, 90)   # European Russia stops at 60 deg E, as in the mask
MIN_HOLE_KM2 = 100                  # smaller holes (mostly islands) are filled
N2K_MIN_KM2 = 50
MAX_PAYLOAD = 2_500_000             # Django's default DATA_UPLOAD_MAX_MEMORY_SIZE

GISCO = "https://gisco-services.ec.europa.eu/distribution/v2/"
VLIZ_WFS = "https://geo.vliz.be/geoserver/MarineRegions/wfs"
EEA_WATER = "https://water.discomap.eea.europa.eu/arcgis/rest/services/"
N2K_LAYER = "https://bio.discomap.eea.europa.eu/arcgis/rest/services/ProtectedSites/Natura2000Sites/MapServer/2"
# Nextcloud share of the tabular end-2024 release; the token may change with the next release
N2K_CSV = ("https://sdi.eea.europa.eu/datashare/public.php/dav/files/P6rmxbD6eyjCPmk/"
           "Natura2000_end2024_rev1_csv.zip")
EMODNET_WFS = "https://ows.emodnet-seabedhabitats.eu/geoserver/emodnet_open/wfs"


def get(url, method="GET", **kw):
    r = requests.request(method, url, timeout=600, **kw)
    r.raise_for_status()
    return r


def features(geojson):
    return gpd.GeoDataFrame.from_features(geojson["features"], crs=4326)


def wfs(url, layer, **params):
    return get(url, params={"service": "WFS", "version": "1.0.0", "request": "GetFeature",
                            "typeName": layer, "outputFormat": "application/json", **params}).json()


def arcgis(layer_url, **params):
    # maxAllowableOffset (~100 m) is well inside the buffer applied afterwards
    gj = get(layer_url + "/query", "POST", data={
        "where": "1=1", "outFields": "*", "outSR": 4326, "maxAllowableOffset": 0.001,
        "geometryPrecision": 5, "f": "geojson", **params}).json()
    assert not gj.get("properties", {}).get("exceededTransferLimit"), f"{layer_url}: paging needed"
    return features(gj)


@cache
def world():
    return features(get(GISCO + "countries/geojson/CNTR_RG_10M_2024_4326.geojson").json())


def countries():
    return world().assign(name=world().NAME_ENGL)


def nuts2():
    g = features(get(GISCO + "nuts/geojson/NUTS_RG_10M_2024_4326_LEVL_2.geojson").json())
    return g.assign(name=g.NAME_LATN + " (" + g.NUTS_ID + ")")


def eez_iho():
    # One request per feature: the whole layer for Europe is ~200 MB
    bbox = ",".join(map(str, EUROPE_BOX.bounds))
    ids = [f["properties"]["mrgid"] for f in
           wfs(VLIZ_WFS, "MarineRegions:eez_iho", bbox=bbox, propertyName="mrgid")["features"]]
    g = pd.concat([features(wfs(VLIZ_WFS, "MarineRegions:eez_iho", cql_filter=f"mrgid={i}"))
                   for i in ids], ignore_index=True)
    return g.assign(name=g.marregion)


def msfd():
    g = arcgis(EEA_WATER + "Marine/MSFD_regions_and_subregions/MapServer/0")
    return g.assign(name=g.subregionName.fillna(g.regionName))   # Baltic and Black Sea have no subregions


def river_basin_districts():
    g = arcgis(EEA_WATER + "WISE_WFD/WFD2022_RiverBasinDistrict_WM/MapServer/0")
    name = g.nameTextInternational.fillna(g.nameText).str.title()
    return g.assign(name=name + " (" + g.thematicIdIdentifier + ")")


def freshwater_ecoregions():
    bbox = ",".join(map(str, EUROPE_BOX.bounds))
    g = features(wfs(VLIZ_WFS, "MarineRegions:tnc_wwf_feow_hydrosheds", bbox=bbox))
    # Unnamed features are Greenland ice and scattered islands (Azores, Madeira, Canaries, ...)
    g = g[g["name"].notna()]
    return g.assign(name=g["name"].str.strip())


def natura2000():
    # The marine percentage in the tabular data is wrong for some sites (Belgian
    # SBZ 1-3: 0%), so a site also counts as marine when its centre is at sea.
    z = zipfile.ZipFile(io.BytesIO(get(N2K_CSV).content))
    table = next(n for n in z.namelist() if n.endswith("NATURA2000SITES.csv"))
    # newline="": some fields contain line breaks
    sites = pd.DataFrame(csv.DictReader(io.StringIO(z.read(table).decode("utf-8-sig"), newline="")))
    num = lambda col: pd.to_numeric(sites[col], errors="coerce")
    x, y = num("LONGITUDE"), num("LATITUDE")
    at_sea = x.notna() & ~shapely.contains_xy(world().union_all(), x.fillna(0), y.fillna(0))
    marine = (num("MARINE_AREA_PERCENTAGE") >= 50) | at_sea
    codes = sites.SITECODE[marine & (num("AREAHA") >= N2K_MIN_KM2 * 100)]
    g = arcgis(N2K_LAYER, where="SITECODE IN (%s)" % ",".join(f"'{c}'" for c in codes),
               outFields="SITECODE,SITENAME")
    return g.assign(name=g.SITECODE + " - " + g.SITENAME)


def posidonia():
    g = features(wfs(EMODNET_WFS, "emodnet_open:art17_hab_1120", srsName="EPSG:4326"))
    g = g.dissolve("country_code").reset_index()
    return g.assign(name="Posidonia beds - " + g.country_code)


# (tag, fetch, outward buffer in km (0 = geometry as published), minimum share of
# the area inside wider Europe). EU-defined sources are not filtered: MSFD
# Macaronesia, for one, is only 44% inside the EEZ mask.
SOURCES = [
    ("Country", countries, 0, 0.5),
    ("NUTS 2 region", nuts2, 0, 0.5),
    ("EEZ x IHO sea", eez_iho, 1, 0.5),
    ("MSFD marine region", msfd, 1, 0),
    ("River basin district", river_basin_districts, 1, 0.5),
    ("Freshwater ecoregion", freshwater_ecoregions, 1, 0.5),
    ("Natura 2000 marine site", natura2000, 0.25, 0),
    ("Posidonia beds", posidonia, 0, 0),
]


def polygons(g):
    if g.geom_type == "Polygon":
        return [g]
    return [p for part in getattr(g, "geoms", []) for p in polygons(part)]


def lighten(g, km):
    """Buffer outwards, simplify by less than the buffer, fill small holes.

    The union with g adds back the rare bits simplification still cuts off
    (0.13 km2 of the Gullmarsfjorden site), so the result always covers g.
    """
    b = g.buffer(km * 1000, quad_segs=4).simplify(0.8 * km * 1000)
    b = MultiPolygon([Polygon(p.exterior, [r for r in p.interiors
                                           if Polygon(r).area >= MIN_HOLE_KM2 * 1e6])
                      for p in polygons(b)])
    return b.union(g)


def build(tag, fetch, km, min_share, mask):
    g = fetch()
    geom = g.geometry.make_valid().clip_by_rect(*EUROPE_BOX.bounds).make_valid()
    laea = geom.to_crs(3035).make_valid()
    keep = ~laea.is_empty & (laea.intersection(mask).area / laea.area > min_share)
    laea = laea[keep]
    if km:
        laea = laea.apply(lighten, km=km)
    geom = laea.to_crs(4326).set_precision(1e-5).make_valid().apply(lambda x: MultiPolygon(polygons(x)))
    return gpd.GeoDataFrame({"name": g.name[keep].values, "tag": tag}, geometry=geom.values, crs=4326)


def main():
    mask = gpd.read_file(MASK).to_crs(3035).union_all()
    shapely.prepare(mask)
    parts = []
    for source in SOURCES:
        a = build(*source, mask)
        tag = source[0]
        n = shapely.get_num_coordinates(a.geometry.values)
        print(f"{tag}: {len(a)} areas, {n.sum():,} vertices, largest {n.max():,} ({a.name.iloc[n.argmax()]})")
        parts.append(a)
    areas = pd.concat(parts, ignore_index=True)

    assert areas.name.is_unique, areas.name[areas.name.duplicated()].tolist()
    assert areas.is_valid.all() and (areas.geom_type == "MultiPolygon").all()
    payload = areas.geometry.apply(lambda g: len(json.dumps({"geojson": g.__geo_interface__})))
    assert payload.max() < MAX_PAYLOAD, areas.name[payload.idxmax()]
    print(f"{len(areas)} areas, largest payload {payload.max() / 1e3:.0f} kB ({areas.name[payload.idxmax()]})")
    areas.to_file(HERE / "areas.gpkg", layer="areas", driver="GPKG")


if __name__ == "__main__":
    main()
