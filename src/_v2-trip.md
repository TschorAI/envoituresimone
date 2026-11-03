# v2: the A -> B trip, with real toll prices

Working note (not built into a PDF). Written 2026-11-03.

## Why it was taken out of v1

V1 had a "Trajet A -> B" tab: fastest route (tolls allowed) against the toll-free route, with
fuel, wear and tolls. Tolls were a flat 0.11 EUR/km on the tolled kilometres that
OpenRouteService reports (`tollways` extra). That is too rough to show to drivers:

- real tariffs depend on the operator, the section and the entry/exit pair, not on distance;
- urban tunnels (Duplex A86: several EUR for about 10 km) and open-system barriers are far
  off any per-km rate;
- the whole point of the comparison (EUR saved per hour lost) hangs on that toll number.

The tab was removed on 2026-11-03. What is kept for v2:

- `cost.route_cost()` and `cost.Leg` (tested in `src/tests/test_cost.py`);
- `connectors/routing.route(a, b, avoid_tolls)`, which already returns the geometry, the
  per-step speeds and the tolled ranges of the route;
- the v1 UI (two cards, map with tolled parts in red) is in git history, file
  `src/envoituresimone/static/app.js`, section "use case B: trip".

V1 test result, for reference (2026-11-03, E10 at 2.123 EUR/L, Concorde -> Bellecour):
fastest 464 km, 4 h 36, 154.49 EUR, of which tolls 397 km x 0.11 = 43.70 EUR; toll-free
484 km, 7 h 19, 111.97 EUR.

## Toll data found

| Data | Source | Format | Licence | Notes |
|---|---|---|---|---|
| Location of every toll gate of the concession network (1266 gates: motorway, side D/G/I, interchange, type, name, Lambert-93 x/y) | Ministère de la Transition écologique, https://www.data.gouv.fr/datasets/gares-de-peage-du-reseau-routier-national-concede | CSV and SHP, yearly (2025 latest) | ODC-BY | No operator column and no price. |
| APRR and AREA tariffs per entry/exit pair, classes 1-5, tariff distance | https://www.data.gouv.fr/datasets/tarifs-autoroutes-aprr (published by an individual, extracted from APRR's PDFs "without change") | CSV, 2026-02 (21 505 pairs for APRR) | Licence Ouverte v2 | Covers Paris -> Lyon (A6). Columns: gare_entree, gare_sortie, distance_tarifaire_km, tarif_classe_1..5. |
| Vinci Autoroutes tariffs (ASF, Cofiroute, Escota, Arcos, Duplex A86) | https://www.vinci-autoroutes.com/fr/tarifs-peage-reseaux-vinci-autoroutes | PDF grids, class 1, 2026 (ASF from 1 June 2026, Cofiroute and Escota from 1 Feb 2026) | to check | To parse into CSV. |
| Sanef and SAPN tariffs | https://www.autoroutes.sanef.com/fr/grilles-tarifs-de-peage | PDF brochures 2026 | to check | To parse into CSV. |
| Free-flow gantries (A79, A13/A14...) | https://www.data.gouv.fr/datasets/autoroutes-et-peages-en-flux-libre | CSV, GeoJSON | other | Free-flow sections have no barrier: need a price per gantry. |
| Smaller operators (ATMB, SFTRF, CEVM Millau, Alicorne, Atlandes, Albea, Adelac, A'liénor, Arcour, ALIS) | each operator's site | PDF / web pages | to check | Mostly fixed price per barrier or few gates. |

Not usable: OSM has no toll prices (`barrier=toll_booth` nodes only; a 2017 `toll_fee` relation
proposal went nowhere). Google Routes API computes tolls only for "select" regions; France
was not confirmed. Commercial APIs (TollGuru, HERE) were not checked.

## Plan

1. `tools/fetch_tolls.py`: download the gate CSV and the APRR/AREA CSVs into `data/tolls/`;
   convert gates from Lambert-93 to WGS84 (pyproj).
2. Match tariff gate names to ministry gate names (normalise accents, case, "NORD/SUD",
   "BARRIERE"; then fuzzy match; keep a hand-checked override table in `data/tolls/`).
3. On a route: find the gates within about 100 m of the ORS geometry, on the right carriageway
   side, in order along the route.
4. Price: closed system = tariff of the (first entry, last exit) pair on one operator; open
   system = fixed price of each barrier passed; crossing operators = one ticket per operator.
5. Any tolled stretch with no matched tariff falls back on 0.11 EUR/km, with a warning naming it.
6. Validate against the operators' online calculators on 10 trips (Paris -> Lyon, Lyon ->
   Grenoble, Dijon -> Besançon...). Goal: within 1 EUR.
7. Then add Vinci and Sanef/SAPN: `tools/parse_toll_pdfs.py` (pdfplumber) -> same CSV format.
8. Bring the tab back.

## Open questions

- The APRR CSV is a third-party extraction: check a sample against the official PDF.
- Licence of the Vinci and Sanef PDFs for reuse.
- Tariffs change every 1 February (and ASF in June 2026): yearly refresh.
- Does ORS sometimes route through a free-flow section without a `tollways` flag?
