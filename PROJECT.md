# envoituresimone — project description for agents and developers

`README.md` is the short version for people, kept non-technical. This file is the detailed map and
the file index: what each piece does, what it reads and writes, what it costs to run, and where the
boundaries are. `CLAUDE.md` holds the folder rules shared by every GENAU project. Keep this file
true when the code changes.

## 1. The question

A web app for French drivers that gives the real cost of a refill or a trip. Use case A: the cheapest station near home, counting fuel bought plus fuel, wear and tear spent to drive there. Use case B: the cost of an A -> B route, fastest (with tolls) against toll-free, counting fuel, wear and tolls. Data: prix-carburants.gouv.fr (live station prices), Géoplateforme geocoding, OpenRouteService routing (OSM, avoid tollways). V1 (use case A only): E10 and Diesel, editable consumption-by-speed curve per fuel, wear 0.10 EUR/km (optional, on by default). Use case B moves to v2, with real toll tariffs. Out of scope: price forecasting, car models.

A plain web app (FastAPI + Leaflet), with an hourly price snapshot. It was first meant as a
Dataiku + n8n demo; that was dropped on 2026-11-03 (neither fits the app). The tool tests moved
to other projects: see `src/_tool-tests.md`.

## 2. Data flow

    sources/  (as received)
       |
       v
    tools/    fetch, convert, clean                         -> data/
       |
       v
    src/      analysis, models, figures, documents          -> out/

External inputs, all read-only:

| Input | Through | Cost |
|---|---|---|
| Fuel prices (prix-carburants.gouv.fr instant flow, `data.economie.gouv.fr`) | the app's hourly snapshot (`snapshot.py`, bulk parquet export, ~600 KB, 1 call at HH:07) -> `data/prices/`; `connectors/prices.py` reads it, and calls the live API only if the snapshot is missing or older than 3 h | Free, no key. |
| Géoplateforme IGN address search, completion, reverse (`data.geopf.fr/geocodage`) | `connectors/geocode.py` | Free, no key. Cached 24 h in memory. |
| OpenRouteService directions and matrix (`api.openrouteservice.org`, OSM) | `connectors/routing.py` | Free key, 2000 directions and 500 matrix calls a day. Use case A: 1 matrix call per search + 1 directions call per station clicked. |
| OpenStreetMap tiles, Leaflet 1.9.4 (unpkg CDN) | the browser | Free, fair use. |
| GoatCounter visitor counting (`gc.zgo.at/count.js`, no cookies) | the page, only if `GOATCOUNTER_CODE` is set | Free for non-commercial use. |

Note the cost of each: a web download (cached or not), a database read, a remote job, anything
that touches production. Mark what must never run by default.

**Environment variables** (`.env` at the project root, never committed, never synced). Only the
ones the project needs; `tools/setup.sh` checks exactly these (its `ENV_VARS` line):

| Variable | For |
|---|---|
| `ORS_API_KEY` | OpenRouteService routing. Without it, distances are crow-fly x 1.3 at 40 km/h. |

## 3. The code

Run from the project root, in the project's env: `uv run python src/<script>.py`,
`uv run python tools/<script>.py`.

| Script or module | Does | Reads | Writes | Run time |
|---|---|---|---|---|
| `src/app.py` | Starts the web app on http://127.0.0.1:8000 (`--port N`, `--reload`) | the package below, `.env` | nothing | stays up |
| `src/envoituresimone/cost.py` | The cost model, pure functions (no I/O): consumption curve, refill cost, route cost (route cost kept for v2) | nothing | nothing | instant |
| `src/envoituresimone/api.py` | FastAPI app: `/api/refill` (A), `/api/price-map` (C), `/api/leg`, `/api/complete`, `/api/geocode`, `/api/reverse`, `/api/config`, and the page | connectors | nothing | 1-5 s a request |
| `src/envoituresimone/connectors/` | One client per service (prices from the snapshot or live, geocode, routing) | the services of section 2, `data/prices/latest.parquet` | nothing | network-bound |
| `src/envoituresimone/snapshot.py` | Price snapshot of all stations plus a history of every price change; the app runs it at start (if the snapshot is over 1 h old) and at HH:07 every hour (`PRICE_REFRESH=0` turns it off) | `data.economie.gouv.fr` | `<DATA_DIR>/prices/latest.parquet`, `<DATA_DIR>/prices/history/YYYY-MM.parquet` | ~3 s |
| `tools/fetch_prices.py` | Takes one snapshot by hand | as above | as above | ~3 s |
| `src/envoituresimone/static/` | The page, two tabs: "Faire le plein" (A: address autocomplete, map picking, curve editor, ranking, detail, comparison) and "Carte des prix" (C: every station coloured by price, cheapest 10 in view) | `/api/*` | browser localStorage (curve, points, fuel) | - |
| `src/tests/test_cost.py` | Checks the cost model on hand-computed cases (`uv run pytest`) | nothing | nothing | < 1 s |

`cost.py` has no I/O, so the cost model is tested and changed apart from the data services.

## 4. Conventions

- Units: km, hours, km/h, L/100 km, EUR/L, EUR. Points are (lat, lon) in the code, [lon, lat] only at the ORS boundary.
- Fuel keys follow the price dataset prefixes: `e10`, `gazole`. E10 uses the former SP95 curve (E10 burns a little more, about 1-2 %; adjust in the app).
- Consumption: linear interpolation on the speed curve, flat beyond its ends. Each route step of ORS is one leg at its own average speed.
- Price timestamps (`updated`) are French local time: the source labels them UTC but they are local. Prices not updated for more than 7 days are left out of the ranking (about 10 % of stations on 2026-11-03; one Paris E10 price dated from August 2025 and ranked first).
- Use case A: round trip = 2 x the one-way road route. Fuel burnt on the way is priced at the station's price. Only the 25 best stations on a crow-fly pre-ranking are routed (quota).
- Use case B (A -> B trip) is not in v1: see `src/_v2-trip.md`.
- Use case C (price map): every station of the snapshot with a price under 7 days old, coloured green -> red on the national 5th-95th percentile range (outliers do not flatten the scale). No live fallback: it needs the snapshot. About 160 KB gzipped per fuel.
- Wear: 0.10 EUR/km, on by default, off when unchecked.

## 5. Boundaries: what may change

| Part | Who changes it | How |
|---|---|---|
| `src/`, `tools/` | anyone on the project | edit here, rerun, run the check in section 8 |
| `sources/` | nobody | read-only, as received |
| `data/`, `out/` | scripts only | rebuilt by `tools/` and `src/`; never edited by hand |
| installed packages (`pyproject.toml`) | not from here | change them in their own repository, then `uv lock --upgrade-package <name>` |

## 6. Known limits and open questions

- Use case B needs real toll tariffs matched to routes: v2, see `src/_v2-trip.md`.
- The round trip assumes the way back equals the way there (one-way streets ignored).
- Default consumption curves are generic values for an average compact car, not measured.
- Stations' opening hours and price age (`updated`) are not yet used in the ranking.

## 7. History

- 2026-11-03: project created.
- 2026-11-03: local web app v1: both use cases, live prices, geocoding, ORS routing, Leaflet map.
- 2026-11-03: SP95 replaced by E10 (many stations sell only E10).
- 2026-11-03: use case A: detail card per station (pump price, refill, trip fuel and wear), comparison of two stations (table and both routes on the map). Fuel on fast roads stays at the ORS average speed, consistent with trip times (user choice).
- 2026-11-03: A -> B trip removed from the app (flat toll estimate too rough); v2 plan in `src/_v2-trip.md`.
- 2026-11-03: hourly price snapshot with history (`tools/fetch_prices.py`); prices older than 7 days left out.
- 2026-11-03: Dataiku and n8n dropped from this project; their tests moved elsewhere (`src/_tool-tests.md`).
- 2026-11-03: the app refreshes prices hourly by itself (for Railway: a cron service would not share the disk); Dockerfile; genau-kit moved to the `docs` dependency group.
- 2026-11-03: use case C, the national price map, in a second tab.
- 2026-11-03: public release is map-only: use case A behind `ENABLE_REFILL` (tab shown disabled, "bientôt"); optional GoatCounter visitor counting.

## 8. Setting up a machine

`bash tools/setup.sh` (safe to rerun; `--no-pull` skips the download). It checks the tools and the
GitHub sign-in, pulls `sources/ data/ out/ tasks/` from the drive, runs `uv sync`, checks the
`.env` variables of section 2 (if any is missing it appends the empty names and stops: the user
fills the values), then runs the project's check (its `CHECK` line) when there is one.
Never write credential values into `.env` yourself, and never print them.

The check: `uv run pytest -q` (cost model tests, no network).

Run the app: `uv run python src/app.py`, then open http://127.0.0.1:8000.

Prices: the app refreshes them by itself every hour while it runs (log lines "price snapshot").
If the snapshot is missing or over 3 h old, searches use the live API.

Deployment (Railway): `Dockerfile` at the root, no start command needed (the image runs
`python src/app.py` on `0.0.0.0:$PORT`). Set the variable `ORS_API_KEY`, and mount a volume on
`/app/data` so the snapshot and its history survive redeploys. Run one replica only: each
replica would refresh on its own. The image leaves out `genau-kit` (private GENAU repository,
`docs` dependency group): `uv sync --no-default-groups`.

Other environment variables, all optional: `HOST` (default 127.0.0.1, 0.0.0.0 in the image),
`PORT` (8000), `DATA_DIR` (the project's `data/`, `/app/data` in the image), `PRICE_REFRESH`
(`0` turns the hourly snapshot off), `ENABLE_REFILL` (`1` turns use case A on; off by default, so the
public site shows only the price map and `/api/refill`, `/api/leg` answer 404), `GOATCOUNTER_CODE`
(the GoatCounter site code, e.g. `simone` for `simone.goatcounter.com`; unset, no counting).
Locally, to work on use case A: `ENABLE_REFILL=1 uv run python src/app.py`.

## 9. Index: every file

| Folder | Holds | Stored in |
|---|---|---|
| `sources/` | Background and seed documents, as received | Own drive |
| `data/` | Input and intermediate data, pulled or computed | Own drive |
| `src/` | Document sources, working notes, and the code that turns `data/` into `out/` | GitHub |
| `tools/` | Scripts that fetch, convert or clean into `data/`; checkers and linters | GitHub |
| `out/reports/` | Compiled documents: PDFs, presentations | Own drive |
| `out/figures/` | Generated images | Own drive |
| `out/videos/` | Generated videos | Own drive |
| `out/data/` | Computed results: predictions, result tables | Own drive |
| `tasks/` | One file per task | Own drive + task board |

### Documents and code (`src/` -> `out/`)

- `src/app.py` — starts the local web app.
- `src/envoituresimone/cost.py` — cost model (consumption curve, refill cost, route cost).
- `src/envoituresimone/api.py` — web API and page server.
- `src/envoituresimone/connectors/prices.py` — live station prices around a point.
- `src/envoituresimone/connectors/geocode.py` — Géoplateforme address search, completion, reverse.
- `src/envoituresimone/connectors/routing.py` — OpenRouteService directions (tolls / no tolls) and matrix.
- `src/envoituresimone/snapshot.py` — hourly price snapshot and price history (run by the app).
- `src/envoituresimone/connectors/_http.py` — shared HTTP client and in-memory cache.
- `src/envoituresimone/static/index.html`, `app.js`, `style.css` — the map page (with Open Graph tags for link previews).
- `src/envoituresimone/static/og.jpg` — the link-preview image (1200×627 crop of the live map, 2026-11-04).
- `src/tests/test_cost.py` — cost model tests.
- `src/_v2-trip.md` — working note: why the A -> B trip left v1, toll data found, v2 plan.
- `src/_tool-tests.md` — working note: where n8n (meeting transcript bot) and Dataiku (GENAU mvp-software) get tested instead of here.

### Tools

- `tools/setup.sh` — sets the project up on a new machine (section 8).
- `Dockerfile`, `.dockerignore` (project root) — the deployed image (section 8).
- `LICENSE` — MIT, Léonard Tschora (the repository is public since 2026-11-04).
- `tools/fetch_prices.py` — takes one price snapshot by hand.

### Sources and data

- `data/prices/latest.parquet` — every station with its E10 and diesel price, position and update time; replaced hourly.
- `data/prices/history/YYYY-MM.parquet` — every price change seen (id, fuel, price, updated), one file a month.

Rebuild the documents with `uv run genau-docs`, and a video with `uv run genau-video`.
