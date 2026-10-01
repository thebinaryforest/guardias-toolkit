# guardias-toolkit
Various tools used for the deployment of the GBIF Alert instance for the GuardIAS project

## Tools

### eez_polygons

Builds one polygon covering the land and Exclusive Economic Zones of wider
Europe, in a high-resolution version and in simplified versions small enough
to be used as a GBIF `within` predicate.

GuardIAS needs it as the geographic filter for GBIF occurrences. Filtering on
`continent=EUROPE` excludes offshore records, and a bounding box wide enough
for the Azores, the Canary Islands, Svalbard and Cyprus also takes in North
Africa, the Levant and part of Greenland. See
[eez_polygons/README.md](eez_polygons/README.md) for scope, processing and
the list of files.

### areas

Builds the starter set of shared filter areas for the GuardIAS instance
(countries, NUTS 2 regions, national parts of the seas, MSFD marine regions,
river basin districts, freshwater ecoregions, marine Natura 2000 sites and
Posidonia beds), lightened for the web map, and uploads them through the GBIF
Alert API. See [areas/README.md](areas/README.md) for sources, licences and
processing.
