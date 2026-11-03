# Starts the web app on http://127.0.0.1:8000 (reload on code change with --reload).
# Reads: src/envoituresimone/, .env, the live data services. Writes: nothing.
import sys
from pathlib import Path

import uvicorn

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

if __name__ == "__main__":
    uvicorn.run("envoituresimone.api:app", host="127.0.0.1", port=int(sys.argv[sys.argv.index("--port") + 1])
                if "--port" in sys.argv else 8000, reload="--reload" in sys.argv,
                reload_dirs=[str(ROOT / "src")])
