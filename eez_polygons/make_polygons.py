"""Rebuild the 'wider Europe' EEZ + land polygons from the Marine Regions WFS.

Requires: requests, shapely>=2.1, pyproj, geopandas (only for the GeoPackage).
    pip install requests shapely pyproj geopandas

Source layer: MarineRegions:eez_land, "Marine and land zones: the union of world
country boundaries and EEZ's" (Flanders Marine Institute, CC-BY 4.0).
"""
import json
import requests
import shapely
from shapely.geometry import MultiPolygon, Polygon, box, mapping, shape
from shapely.ops import transform, unary_union
from pyproj import Transformer

WFS = "https://geo.vliz.be/geoserver/MarineRegions/wfs"

# Territories with an EEZ, by mrgid_eez (see wider_europe_eez_land_territories.csv)
MRGID_EEZ = [
    8361, 5680, 8364, 8363, 5681, 48973, 5688, 48975, 48967, 8435, 48998, 48966,
    49002, 8437, 8365, 64446, 48999, 5696, 49001, 5693, 49000, 21788, 48997,
    21789, 5677, 3293, 5668, 21790, 48976, 5674, 5669, 48977, 5682, 50167, 5686,
    5692, 5685, 5673, 5694, 22491, 33181, 5691, 5687, 5670, 5684, 5679, 5683,
    5675, 5676, 5689, 5672, 5695, 8376, 5697, 64459, 5678, 5690,
]
# Landlocked countries have no mrgid_eez; select them by name
LANDLOCKED = [
    "Andorra", "Grand Duchy of Luxembourg", "Switzerland", "Liechtenstein",
    "Vatican City", "San Marino", "Austria", "Czech Republic", "Hungary",
    "Slovakia", "Serbia", "Macedonia", "Belarus", "Moldova",
]
RUSSIA_CLIP = box(-10, 35, 60, 90)   # European Russia: west of 60 deg E
KEEP_HOLES_KM2 = 1000                # smaller holes are slivers between EEZs
SIMPLIFIED_KM = [5, 10, 20, 40]      # outward buffer per simplified version

to_laea = Transformer.from_crs(4326, 3035, always_xy=True).transform
to_wgs = Transformer.from_crs(3035, 4326, always_xy=True).transform


def area_km2(g):
    return transform(to_laea, g).area / 1e6


def fetch(cql):
    r = requests.get(WFS, params={
        "service": "WFS", "version": "1.0.0", "request": "GetFeature",
        "typeName": "MarineRegions:eez_land", "outputFormat": "application/json",
        "cql_filter": cql,
    }, timeout=120)
    r.raise_for_status()
    return r.json()["features"]


def polygons(g):
    return [p for p in getattr(g, "geoms", [g]) if p.geom_type == "Polygon"]


def drop_small_holes(parts):
    return [Polygon(p.exterior, [r for r in p.interiors if area_km2(Polygon(r)) >= KEEP_HOLES_KM2])
            for p in parts]


def main():
    feats = []
    for i in MRGID_EEZ:
        feats += fetch(f"mrgid_eez={i}")
    for n in LANDLOCKED:
        feats += fetch(f"union='{n}'")
    json.dump({"type": "FeatureCollection", "features": feats},
              open("eez_land_wider_europe_raw.geojson", "w"))

    geoms = []
    for f in feats:
        g = shapely.make_valid(shape(f["geometry"]))
        if f["properties"]["union"] == "Russia":
            g = g.intersection(RUSSIA_CLIP)
        geoms.append(g)

    u = shapely.make_valid(unary_union(geoms))
    u = shapely.make_valid(unary_union(drop_small_holes(polygons(u))))
    hires = MultiPolygon([p for p in polygons(u) if area_km2(p) > 0.1])
    hires = shapely.orient_polygons(hires, exterior_cw=False)   # GBIF: anticlockwise
    write("wider_europe_eez_land_hires", hires, precision=6)

    # Simplified versions: buffer outwards in metres (LAEA), then simplify in
    # lon/lat with a tolerance below the buffer width, so every version still
    # covers the high-resolution polygon when edges are read as straight lines
    # in lon/lat (as GBIF does).
    hires_m = transform(to_laea, shapely.segmentize(hires, 0.05))
    for km in SIMPLIFIED_KM:
        buf = transform(to_wgs, hires_m.buffer(km * 1000, quad_segs=4))
        g = shapely.make_valid(buf.simplify(0.8 * km / 111.32, preserve_topology=True))
        prec = 3 if km < 30 else 2
        g = shapely.set_precision(MultiPolygon(drop_small_holes(polygons(g))), 10 ** -prec)
        g = shapely.orient_polygons(shapely.make_valid(g), exterior_cw=False)
        if g.geom_type == "Polygon":
            g = MultiPolygon([g])
        assert area_km2(hires.difference(g)) < 0.01, "simplified version misses part of the original"
        write(f"wider_europe_eez_land_gbif_{km}km", g, precision=prec, compact=True)


def write(name, g, precision, compact=False):
    wkt = shapely.to_wkt(g, rounding_precision=precision, trim=True)
    if compact:
        wkt = wkt.replace(", ", ",")
    open(name + ".wkt", "w").write(wkt)
    json.dump({"type": "Feature", "properties": {"name": name}, "geometry": mapping(g)},
              open(name + ".geojson", "w"), separators=(",", ":"))
    print(f"{name}: {shapely.get_num_coordinates(g)} vertices, {len(wkt)} WKT chars")


if __name__ == "__main__":
    main()
