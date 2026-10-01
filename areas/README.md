# Starter set of shared filter areas

Built 2026-10-01 for the GuardIAS GBIF Alert instance. 1,407 areas covering wider Europe, meant to show what area filters can do for marine and freshwater species: administrative units, national parts of the seas, policy regions, river basins, biogeographic regions, protected sites and one habitat. Each area carries one tag naming its layer, so the area filter can show one layer at a time.

## Contents

| Tag | Areas | Source | Licence |
|---|---|---|---|
| Country | 53 | Eurostat GISCO, Countries 2024, 1:10 million | © EuroGeographics for the administrative boundaries; non-commercial use with attribution |
| NUTS 2 region | 294 | Eurostat GISCO, NUTS 2024 level 2, 1:10 million | as above |
| EEZ x IHO sea | 124 | Flanders Marine Institute (VLIZ), Marine Regions layer `MarineRegions:eez_iho` (intersect of the EEZs and the IHO sea areas) | CC-BY 4.0 |
| MSFD marine region | 10 | EEA, MSFD regions and subregions, version 2, Oct. 2022 | CC-BY 4.0, see disclaimer below |
| River basin district | 166 | EEA, WISE WFD Reference Spatial Datasets reported under the Water Framework Directive 2022, public version 1.9, Sep. 2025 | CC-BY 4.0 |
| Freshwater ecoregion | 34 | Abell et al. (2008), Freshwater Ecoregions of the World, HydroSHEDS-based version served by Marine Regions (`MarineRegions:tnc_wwf_feow_hydrosheds`) | **Non-commercial** (CC BY-NC 3.0 on Data Basin) |
| Natura 2000 marine site | 718 | EEA, Natura 2000 end 2024 (vector doi:10.2909/91357f39-7866-41ce-b447-43905c364ec8, tabular doi:10.2909/d713bff7-0cdf-4f0d-acd1-dc3c63af237e) | CC-BY 4.0 |
| Posidonia beds | 8 | EEA, 2013 Habitats Directive Article 17 reporting (period 2007-2012), gridded distribution of habitat 1120, served by EMODnet Seabed Habitats (`emodnet_open:art17_hab_1120`) | CC-BY 4.0 |

Two layers are not CC-BY: the GISCO boundaries and the freshwater ecoregions only allow non-commercial use. That fits GuardIAS, but not a commercial reuse of this file.

Citation for the freshwater ecoregions: Abell, R. et al. (2008). Freshwater Ecoregions of the World: A New Map of Biogeographic Units for Freshwater Biodiversity Conservation. BioScience 58(5): 403-414. For the Marine Regions layer, cite the exact version listed on https://www.marineregions.org/.

MSFD disclaimer, required by its licence: the MSFD regions and subregions map is a working tool only. It does not represent official marine borders.

## Selection

- **Wider Europe**: areas with more than half of their surface inside `../eez_polygons/wider_europe_eez_land_hires.geojson`, after clipping at 60°E. This drops neighbouring countries, French overseas regions and river basin districts, and Asian ecoregions. It keeps Turkey and Georgia, as the mask does. MSFD regions, Natura 2000 sites and Posidonia beds are EU-defined, so they are not filtered (MSFD Macaronesia is only 44% inside the mask).
- **Freshwater ecoregions**: the 5 unnamed features (Greenland ice, scattered islands, the Azores, Madeira and the Canary Islands) are dropped. The NUTS 2 regions cover the three archipelagos.
- **Natura 2000**: sites of at least 50 km² that are marine. A site counts as marine if its `MARINE_AREA_PERCENTAGE` in the tabular data is at least 50, or if its centre point lies outside the GISCO land polygons. The second test is needed because the percentage is wrong for some sites: Belgian sites SBZ 1-3 (BEMNZ0002-4) are fully marine but recorded as 0%. Areas are named `SITECODE - SITENAME`.
- **Posidonia beds**: the grid cells are dissolved per member state, giving 8 areas named `Posidonia beds - <country>`.
- **River basin districts**: each feature is one country's part of a district. The Danube, for example, comes as AT1000, DE1000, RO1000 and others. Areas are named `<name> (<code>)`.

## Processing

GISCO and Article 17 geometries are used as published: they are already generalized. The other layers are lightened in ETRS89-LAEA:

1. Buffer outwards by 1 km (Natura 2000: 250 m), then simplify with a tolerance of 0.8 times the buffer.
2. Fill holes smaller than 100 km², mostly islands.
3. Take the union with the original geometry. In rare cases simplification still cuts off a sliver (0.13 km² of the Gullmarsfjorden site), and the union adds it back.

Every area therefore contains its original geometry, at the cost of a margin of up to the buffer width. This favours marine records: shore observations are often georeferenced slightly inland. Neighbouring areas of the same layer overlap by up to twice the buffer width.

The EEA layers are fetched with server-side generalization (`maxAllowableOffset` 0.001°, about 100 m). That error stays well inside the buffer. Coordinates are rounded to 1e-5° (about 1 m).

Result: at most 6,303 vertices per area (Barents Sea Drainages), and a 138 kB request body for the largest upload. Django rejects request bodies above 2.5 MB by default. The build checks that limit, that names are unique, and that every geometry is a valid MultiPolygon.

## Files

- `make_areas.py`: fetches the sources and writes `areas.gpkg`. It takes about 6 minutes, most of it the 124 per-feature requests for `eez_iho`.
- `areas.gpkg`: layer `areas`, EPSG:4326, columns `name` and `tag`. This is the frozen reference that was uploaded.
- `upload_areas.py`: creates each area as a shared area through `POST /api/v2/areas/` of GBIF Alert.

```bash
uv run --with requests --with geopandas --with 'shapely>=2.1' --with pyproj python make_areas.py
```

```bash
GBIF_ALERT_URL=https://... GBIF_ALERT_TOKEN=... uv run --with requests --with geopandas python upload_areas.py
```

Upload notes:

- The token must belong to an operator (superuser), because only operators can create shared areas. Create one on the instance's API tokens page.
- Tag names passed as arguments restrict the upload to those layers, e.g. `upload_areas.py "MSFD marine region"`.
- An area whose name already exists among the public areas is skipped and listed, so the upload can be re-run after an interruption. The script never updates or deletes existing areas: after changing an area's geometry, delete the old area on the instance first.
- The Natura 2000 tabular data comes from an EEA Nextcloud share whose token (`N2K_CSV` in `make_areas.py`) may change with the next release. If it does, get the new link from https://sdi.eea.europa.eu/data/d713bff7-0cdf-4f0d-acd1-dc3c63af237e.
