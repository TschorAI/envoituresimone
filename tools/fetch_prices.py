# Hourly snapshot of the live fuel prices of every French station (prix-carburants.gouv.fr
# instant flow, bulk parquet export of data.economie.gouv.fr). One call, about 600 KB.
# Reads: https://data.economie.gouv.fr. Writes: data/prices/latest.parquet (the app reads it),
# data/prices/history/YYYY-MM.parquet (every price change, appended, deduplicated).
#
#   uv run python tools/fetch_prices.py
#
# Scheduled hourly by cron (see PROJECT.md section 8). Timestamps `*_updated` are French local
# time (Europe/Paris): the source labels them UTC but they are local.
from __future__ import annotations

import io
import struct
import sys
from datetime import datetime
from pathlib import Path

import httpx
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "prices"
URL = ("https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/"
       "prix-des-carburants-en-france-flux-instantane-v2/exports/parquet")
FUELS = ["e10", "gazole"]  # same keys as src/envoituresimone/connectors/prices.py


def wkb_point(b: bytes) -> tuple[float, float]:
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
    lonlat = raw["geom"].map(wkb_point)
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
        both, new_rows = long.drop_duplicates(["id", "fuel", "updated"]), len(long)
    tmp = path.with_suffix(".tmp")
    both.to_parquet(tmp, index=False); tmp.replace(path)
    return new_rows


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    df = fetch()
    if len(df) < 5000:  # a broken export must not replace a good snapshot
        print(f"{datetime.now():%F %T} only {len(df)} stations: snapshot NOT replaced", file=sys.stderr)
        return 1
    tmp = OUT / "latest.tmp"
    df.to_parquet(tmp, index=False); tmp.replace(OUT / "latest.parquet")
    n = append_history(df)
    counts = ", ".join(f"{f} {df[f'{f}_price'].notna().sum()}" for f in FUELS)
    print(f"{datetime.now():%F %T} {len(df)} stations ({counts}), {n} new price rows in history")
    return 0


if __name__ == "__main__":
    sys.exit(main())
