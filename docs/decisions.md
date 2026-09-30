# Decision log

## 2026-09-30 - Add eez_polygons as first tool
**What:** Added `eez_polygons/` with the script and its generated polygons; source data is linked (Marine Regions WFS), not committed.
**Why:** The generated polygons are the frozen reference GuardIAS uses as GBIF filter; the 7.2 MB raw download adds nothing to that.
**Rejected:** Committing the raw WFS snapshot; extending the script to regenerate the GeoPackage, preview and CSV.
