# envoituresimone — project description for agents and developers

`README.md` is the short version for people, kept non-technical. This file is the detailed map and
the file index: what each piece does, what it reads and writes, what it costs to run, and where the
boundaries are. `CLAUDE.md` holds the folder rules shared by every GENAU project. Keep this file
true when the code changes.

## 1. The question

A web app for French drivers that gives the real cost of a refill or a trip. Use case A: the cheapest station near home, counting fuel bought plus fuel, wear and tear spent to drive there. Use case B: the cost of an A -> B route, fastest (with tolls) against toll-free, counting fuel, wear and tolls. Data: prix-carburants.gouv.fr (live station prices), Géoplateforme geocoding, OpenRouteService routing (OSM, avoid tollways). V1: SP95 and Diesel, editable consumption-by-speed curve per fuel, wear 0.10 EUR/km (optional, on by default), tolls 0.11 EUR/km estimate with a warning on short tolled stretches (Duplex A86). Out of scope: price forecasting, car models.

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
| _none yet_ | | |

Note the cost of each: a web download (cached or not), a database read, a remote job, anything
that touches production. Mark what must never run by default.

**Environment variables** (`.env` at the project root, never committed, never synced). Only the
ones the project needs; `tools/setup.sh` checks exactly these (its `ENV_VARS` line):

| Variable | For |
|---|---|
| _none yet_ | |

## 3. The code

Run from the project root, in the project's env: `uv run python src/<script>.py`,
`uv run python tools/<script>.py`.

| Script or module | Does | Reads | Writes | Run time |
|---|---|---|---|---|
| _none yet_ | | | | |

## 4. Conventions

_To be written: time zone and clock, units, naming, any rule a result depends on._

## 5. Boundaries: what may change

| Part | Who changes it | How |
|---|---|---|
| `src/`, `tools/` | anyone on the project | edit here, rerun, run the check in section 8 |
| `sources/` | nobody | read-only, as received |
| `data/`, `out/` | scripts only | rebuilt by `tools/` and `src/`; never edited by hand |
| installed packages (`pyproject.toml`) | not from here | change them in their own repository, then `uv lock --upgrade-package <name>` |

## 6. Known limits and open questions

_None yet._

## 7. History

- 2026-11-03: project created.

## 8. Setting up a machine

`bash tools/setup.sh` (safe to rerun; `--no-pull` skips the download). It checks the tools and the
GitHub sign-in, pulls `sources/ data/ out/ tasks/` from the drive, runs `uv sync`, checks the
`.env` variables of section 2 (if any is missing it appends the empty names and stops: the user
fills the values), then runs the project's check (its `CHECK` line) when there is one.
Never write credential values into `.env` yourself, and never print them.

The check: _none yet. When the project has a result to protect, put one short command in
`CHECK` that fails if the result changes (about ten seconds, no remote jobs)._

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

_None yet._

### Tools

- `tools/setup.sh` — sets the project up on a new machine (section 8).

### Sources and data

_None yet._

Rebuild the documents with `uv run genau-docs`, and a video with `uv run genau-video`.
