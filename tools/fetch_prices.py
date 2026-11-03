# Takes one price snapshot by hand (the app also does it hourly by itself).
# Reads: https://data.economie.gouv.fr. Writes: data/prices/ (see src/envoituresimone/snapshot.py).
#
#   uv run python tools/fetch_prices.py
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from envoituresimone import snapshot  # noqa: E402

if __name__ == "__main__":
    try:
        print(f"{datetime.now():%F %T} {snapshot.refresh()}")
    except Exception as e:
        print(f"{datetime.now():%F %T} FAILED: {e}", file=sys.stderr)
        sys.exit(1)
