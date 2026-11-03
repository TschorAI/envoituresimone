# Price snapshot: downloads the live prices of every French station (prix-carburants.gouv.fr
# instant flow, bulk parquet export of data.economie.gouv.fr, one call, about 600 KB), and keeps
# a history of every price change. Run hourly, by the app itself (see `refresh_loop`) or by
# tools/fetch_prices.py.
# Reads: https://data.economie.gouv.fr. Writes: <DATA_DIR>/prices/latest.parquet,
# <DATA_DIR>/prices/history/YYYY-MM.parquet. DATA_DIR defaults to the project's data/.
#
# Timestamps `*_updated` are French local time (Europe/Paris): the source labels them UTC but
# they are local.
from __future__ import annotations

import asyncio
import io
import logging
import os
import struct
from datetime import datetime, timedelta
from pathlib import Path

import httpx
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.environ.get("DATA_DIR") or ROOT / "data")
OUT = DATA_DIR / "prices"
LATEST = OUT / "latest.parquet"
URL = ("https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/"
       "prix-des-carburants-en-france-flux-instantane-v2/exports/parquet")
FUELS = ["e10", "gazole"]   # same keys as connectors/prices.py
MIN_STATIONS = 5000         # a broken export must not replace a good snapshot
REFRESH_MINUTE = 7          # the app refreshes at HH:07
log = logging.getLogger("envoituresimone.snapshot")


def _wkb_point(b: bytes) -> tuple[float, float]:
    """WKB point -> (lon, lat)."""
    order = "<" if b[0] == 1 else ">"
    return struct.unpack(f"{order}dd", b[5:21])


def fetch() -> pd.DataFrame:
    select = "id,adresse,ville,cp,geom," + ",".join(f"{f}_prix,{f}_maj" for f in FUELS)
    r = httpx.get(URL, params={"select": select}, timeout=120,
                  headers={"User-Agent": "envoituresimone/0.1 (personal demo app)"})
    r.raise_for_status()
    raw = pd.read_parquet(io.BytesIO(r.content))
    raw = raw[raw["geom"].notna()]
    lonlat = raw["geom"].map(_wkb_point)
    df = pd.DataFrame({
        "id": raw["id"].astype(str),
        "lat": lonlat.map(lambda p: p[1]), "lon": lonlat.map(lambda p: p[0]),
        "address": raw["adresse"].fillna("").str.title(), "city": raw["ville"].fillna(""),
        "postcode": raw["cp"].fillna(""),
    })
    for f in FUELS:
        df[f"{f}_price"] = raw[f"{f}_prix"].astype(float)
        df[f"{f}_updated"] = pd.to_datetime(raw[f"{f}_maj"]).dt.tz_localize(None)  # local time, see header
    df["fetched_at"] = pd.Timestamp(datetime.now().replace(microsecond=0))
    return df.reset_index(drop=True)


def _write(df: pd.DataFrame, path: Path) -> None:
    tmp = path.with_suffix(".tmp")
    df.to_parquet(tmp, index=False)
    tmp.replace(path)  # atomic: readers never see a half-written file


def append_history(df: pd.DataFrame) -> int:
    hist_dir = OUT / "history"
    hist_dir.mkdir(parents=True, exist_ok=True)
    long = pd.concat([
        df[["id", f"{f}_price", f"{f}_updated"]].dropna()
          .rename(columns={f"{f}_price": "price", f"{f}_updated": "updated"}).assign(fuel=f)
        for f in FUELS])[["id", "fuel", "price", "updated"]]
    path = hist_dir / f"{datetime.now():%Y-%m}.parquet"
    if path.exists():
        old = pd.read_parquet(path)
        both = pd.concat([old, long]).drop_duplicates(["id", "fuel", "updated"])
        new_rows = len(both) - len(old)
    else:
        both = long.drop_duplicates(["id", "fuel", "updated"])
        new_rows = len(both)
    _write(both, path)
    return new_rows


def refresh() -> str:
    """One snapshot: replaces latest.parquet and extends the history. Returns a log line.
    Raises if the download fails or looks broken (the previous snapshot is kept)."""
    OUT.mkdir(parents=True, exist_ok=True)
    df = fetch()
    if len(df) < MIN_STATIONS:
        raise RuntimeError(f"only {len(df)} stations in the export: snapshot not replaced")
    _write(df, LATEST)
    n = append_history(df)
    counts = ", ".join(f"{f} {df[f'{f}_price'].notna().sum()}" for f in FUELS)
    return f"{len(df)} stations ({counts}), {n} new price rows in history"


def age() -> timedelta | None:
    """Age of latest.parquet, or None if there is none."""
    try:
        return datetime.now() - datetime.fromtimestamp(LATEST.stat().st_mtime)
    except FileNotFoundError:
        return None


def _seconds_to_next_run(now: datetime) -> float:
    nxt = now.replace(minute=REFRESH_MINUTE, second=0, microsecond=0)
    if nxt <= now:
        nxt += timedelta(hours=1)
    return (nxt - now).total_seconds()


async def refresh_loop() -> None:
    """Background task of the app: refresh now if the snapshot is missing or over an hour old,
    then at HH:07 every hour. Failures are logged; the loop keeps going."""
    first = True
    while True:
        a = age()
        if not first or a is None or a > timedelta(hours=1):
            try:
                log.warning("price snapshot: %s", await asyncio.to_thread(refresh))
            except Exception as e:  # noqa: BLE001 - keep the loop alive
                log.error("price snapshot failed: %s", e)
        first = False
        await asyncio.sleep(_seconds_to_next_run(datetime.now()))
