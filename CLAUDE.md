# envoituresimone

Project created 2026-11-03 by leonardtschora. This file tells the agent how the folder works. `README.md`
is the short, non-technical page for people; `PROJECT.md` is the detailed map and the file index,
for agents and developers. Keep all three up to date.

## Project context

_Not filled in yet. State here: what the project is, who it is for, and the main question to answer._
When the user first describes the project, write it here, in the **What** line of `README.md`, and in
section 1 of `PROJECT.md`.

## Layout

| Folder | Holds | Rule |
|---|---|---|
| `sources/` | Background and seed documents, exactly as received (PDF, xlsx, emails, decks). | Read-only. Never edit, rename or delete a source. |
| `data/` | Input and intermediate data: anything pulled, scraped, cleaned or cached that code reads (CSV, parquet, JSON). | Reproducible: every file here comes from a source or from a script. |
| `src/` | The project's work: document sources (md, tex, slide sources), working notes, and the code that turns `data/` into `out/` (analysis, models, figure and prediction scripts). | Hand-written. Nothing compiled or generated. |
| `tools/` | Plumbing: scripts that fetch, convert or clean into `data/`, and checkers or linters. | One script per job. Never writes to `out/`. |
| `out/` | Results for people, in the four subfolders below. | Built from `src/`; never edited by hand. Nothing directly in `out/`. |
| `out/reports/` | Compiled documents: PDFs, presentations, docx. | The source is in `src/`, with the same base name. |
| `out/figures/` | Generated images (png, svg). | Made by a script in `src/`. |
| `out/videos/` | Generated videos (mp4). | Made by a script in `src/`. |
| `out/data/` | Computed results that people or other projects use: predictions, result tables (csv, xlsx, parquet). | Made by a script in `src/`. Intermediate files go in `data/`, not here. |
| `tasks/` | One file per task, in the format below. | Update `status` instead of deleting. |
| `.claude/` | Hooks and scripts that run the project (autosave, sync). | Do not edit unless asked. |

`src/` or `tools/`? Same rule in every project: code needed to rebuild `out/` from `data/` is
`src/`; code that only fills `data/` or checks things is `tools/`. Deleting `out/` must lose
nothing: `src/` rebuilds it.

Where a new file goes:
- Someone sent it to us -> `sources/`
- A script downloaded, cleaned or cached it, and other code will read it -> `data/`
- It is a compiled document a person will read (PDF, presentation) -> `out/reports/`
- It is a generated image -> `out/figures/`
- It is a generated video -> `out/videos/`
- It is a computed result someone will use (predictions, result table) -> `out/data/`
- It is the source of a document, or a working note -> `src/`
- It is code that produces something in `out/` (figure, prediction, model, analysis) -> `src/`
- It is code that fetches or prepares `data/`, or a checker -> `tools/`

Keep the project root clean: `README.md`, `PROJECT.md`, `CLAUDE.md`, `pyproject.toml`, `uv.lock` and the folders.

## Where things are stored

| | GitHub (https://github.com/leonardtschora/envoituresimone, private) | The user's own drive |
|---|---|---|
| `src/`, `tools/`, `pyproject.toml`, `uv.lock`, `CLAUDE.md`, `.claude/` | yes | no |
| `README.md` | yes | yes |
| `sources/`, `data/`, `out/`, `tasks/` | no (gitignored) | yes |
| `.env` files and other secrets | no | no (password vault only) |

This is a personal project, not a GENAU one (`.claude/personal`): the repository and the task board
are in the user's own GitHub account, and nothing goes to the Genau-AI organisation or to
SharePoint. Never create a repository or a board in the organisation for it, and never copy its
files to the GENAU drive.

The drive is the user's own, named in `.claude/sync.conf`. It holds what git does not, plus
`README.md`. `out/` is generated from `src/`, so it is never versioned: git holds what builds it,
the drive holds the built copy. If the project has no `.claude/sync.conf`, those four folders exist
on this machine only: say so to the user when it matters.

Write documents in `src/` (md, tex, slide sources) and compile them into `out/reports/`. Nothing in
`out/` is committed, so always keep the source in `src/`.

## Saving is automatic. Do not do it yourself

Hooks in `.claude/settings.json` run `.claude/scripts/autosave.sh`:
- after every prompt: a git commit;
- every 10 prompts and at the end of the session: a git push, and a copy of `sources/ data/ out/ tasks/` to the drive named in `.claude/sync.conf`.

So: **never run `git add`, `git commit` or `git push`, and never mention commits to the user.** The
user should not see git at all. Do not create branches. If something looks wrong, read
`.claude/state/autosave.log`.

The hooks only run in a Claude Code session opened in this folder. If you work on the project from
a session opened elsewhere, run `bash .claude/scripts/autosave.sh end` when the work is done.

## Status

**Status** in `README.md` is one of `in progress` (results may change or be wrong), `usable`
(results can be relied on) or `closed` (no further change). Only the user decides to move it past
`in progress`.

## Code and the python env

One env for `src/` and `tools/`: `.venv` at the project root, managed by `uv` from `pyproject.toml`
(`uv.lock` is versioned). Same commands on Mac, Windows and Linux. Run them from the project root:

    uv run python tools/<script>.py     # run a tool
    uv run python src/<script>.py       # run project code
    uv add <package>                    # add a dependency
    uv sync                             # rebuild the env (fresh clone)

- Never install into the system python, and never call `pip` or `.venv/bin/python` directly.
- `genau-kit` is already a dependency: the shared GENAU tools for documents, figures and videos
  (next section). Use them instead of writing a new build script.
- Scripts resolve paths from their own location, not from the caller's directory:
  `ROOT = Path(__file__).resolve().parent.parent`, then `ROOT / "data"`, `ROOT / "sources"`, `ROOT / "out" / "figures"`.
- `tools/` scripts read `sources/` and write `data/`.
- `src/` code reads `data/` and `sources/`, and writes `out/reports/`, `out/figures/`, `out/videos/` or `out/data/`.
  Intermediate files it wants to keep go in `data/`.
- Nothing writes to `sources/`. A script creates its output folder if it is missing.
- Every script starts with a header comment saying what it reads and writes.

## Documents, figures and videos: genau-kit

Shared tools, installed in every project from the `kit/` folder of the skills repository. The
version is pinned in `uv.lock`; `uv lock --upgrade-package genau-kit` moves to the newest.

**PDF documents.** Write markdown in `src/`. One command builds every `src/*.md` into
`out/reports/<same name>.pdf`, with the GENAU look (highlighted quotes, grey code blocks):

    uv run genau-docs                 # run src/figures/*.py, then build every document
    uv run genau-docs src/report.md   # one document

- Not built: `README.md` and files whose name starts with `_` (working notes).
- A figure script goes in `src/figures/` and writes to `out/figures/`; a document includes the
  image as `../out/figures/<name>.pdf`.
- Another language: first lines `---`, `lang: es-MX`, `---`. Name a translation `<name>.es.md`.
- A project changes the look with its own `src/pdf-style.tex`. Needs pandoc and xelatex.

**Figures.** Start a figure script with the shared style, so all figures look alike:

    from genau_kit import style
    from genau_kit.style import C     # colours by role: C.ink, C.muted, C.accent, C.dark, C.good, C.bad...
    style.use()

A project overrides lines of the style in `src/style.mplstyle` and colours in `src/palette.toml`.

**Videos.** Narrated videos are compiled from a script and scene files in `src/video/` into
`out/videos/`. Do not write one from scratch: use the `make-video` skill, which also installs
the voice engine the first time (it is not installed by default).

## Tasks

Tasks live in two places that must agree: a file in `tasks/` (full detail) and an item on the
project's task board (what people see, on a phone too). The board is filled with `task`
(task-planner), which reads the project's `.task.toml`: a GitHub project board by default, a Trello
board if the user set one up. Do not use any other task tool, and do not edit `.task.toml`.

    task "Title" --label <tag> --start YYYY-MM-DD --due YYYY-MM-DD --body "Description"   # prints the task's link
    task --list
    task --doing N        # In Progress
    task --close N        # Done
    task --delete N

`N` is the task's number: the end of its link on GitHub, the number `task --list` shows on Trello.

For every task:
1. Write `tasks/TASK-NN_short-slug.md` (format below), numbered in creation order.
2. Add it to the board with the same title. `--body`: the description. `--label`: the assignee's
   first name, lower-case. `--due`: the deadline, only if it is a real date. `--start`: today,
   unless stated. Write the link it prints in the file, as `pushed:`.
3. When the status changes, change both: the `status` field in the file, and `--doing` / `--close`
   on the board (`dropped` -> `--delete`).

A file that has a `pushed:` link is already on the board: never add it twice.

If `task` says the project has no board, run `task --setup github` once: it makes the board in the
user's own account. Then put its link in the last Summary line of `README.md`.

Task file:

    ---
    type: task
    title: Imperative title, 3-10 words
    meeting_date: 'YYYY-MM-DD'      # date the task was given; null if unknown
    assigned_to: Full Name          # null if not stated
    assigned_by: Full Name          # null if not stated
    deadline: as stated             # null if not stated
    duration: null                  # estimated effort, if stated
    confidence: high                # high | medium | low: how clearly it was assigned
    source_transcript: null         # file in sources/ the task comes from, if any
    status: open                    # open | in_progress | done | dropped
    pushed: null                    # the task's link on the board, once added
    ---

    # Same title

    ## Description

    What must be done and why, 2-5 sentences.

    ## Source

    Where the task comes from, with a verbatim quote if there is one.

Never invent a field: use `null` when it was not stated.

## README.md and PROJECT.md

`README.md` is for people who are not technical: the Summary, the question and the answer in a
few plain lines ("In short"), the deliverables they would open ("What is here"), and "Get started"
(ask Claude Code to set the project up). No commands, no code paths beyond the deliverables, no
file index. `PROJECT.md` holds everything else.

Update them in the same turn as the change:
- a new document, code module, tool, source or dataset -> one line in the matching part of the `PROJECT.md` index (section 9: path, one-sentence description), and a row in its section 3 if it is code;
- a new external input, or a new variable in `.env` -> `PROJECT.md` section 2, and the `ENV_VARS` line of `tools/setup.sh`;
- a new deliverable, or a changed headline result -> `README.md` ("In short", "What is here");
- the project's purpose becomes clear or changes -> the **What** line, and `PROJECT.md` section 1;
- the user says the results can be relied on, or that the project is over -> the **Status** line.

Keep the Summary at exactly six lines. Never change **Created by** or **Created on**.

`.env` holds only the variables the project needs, never a copy of another project's file. Never
write a credential value into it yourself, and never print one: the user fills them from the vault.
When a result is worth protecting, set `CHECK` in `tools/setup.sh` to a short command that fails if
it changes.

## Working rules

- Start a session by reading this file, then `PROJECT.md`, then `tasks/` for open work.
- "Set the project up" means: run `bash tools/setup.sh` and do what it says.
- Numbers in a document must trace back to a file in `data/`, `out/data/` or `sources/` and to the script that produced them.
- Flag inconsistencies found in sources in the research notes; do not fix the source.
