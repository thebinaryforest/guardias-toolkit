# Decision log

## 2026-09-30 - Add eez_polygons as first tool
**What:** Added `eez_polygons/` with the script and its generated polygons; source data is linked (Marine Regions WFS), not committed.
**Why:** The generated polygons are the frozen reference GuardIAS uses as GBIF filter; the 7.2 MB raw download adds nothing to that.
**Rejected:** Committing the raw WFS snapshot; extending the script to regenerate the GeoPackage, preview and CSV.

## 2026-10-01 - Add areas tool with a starter set of shared areas
**What:** Added `areas/` (build + API upload) and uploaded 1,407 tagged public areas from 8 open sources to guardias.gbif-alert.org.
**Why:** Show what area filters can do for marine and freshwater IAS; buffer-then-simplify keeps every area covering its source so coastal records are never dropped.
**Rejected:** IHO seas (CC-BY-NC-SA, eez_iho is CC-BY and more useful); EMODnet Posidonia meadow polygons (CC BY-NC, ~650 MB); coverage_simplify (cuts coastal records).
