# Starts the web app. Local: http://127.0.0.1:8000 (`--reload` to reload on code change).
# Deployed: HOST=0.0.0.0 and PORT come from the environment (Railway sets PORT).
# Reads: src/envoituresimone/, .env, the data services. Writes: <DATA_DIR>/prices/ (hourly snapshot).
import os
import sys
from pathlib import Path

import uvicorn

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

if __name__ == "__main__":
    port = int(sys.argv[sys.argv.index("--port") + 1]) if "--port" in sys.argv else int(os.environ.get("PORT", 8000))
    uvicorn.run("envoituresimone.api:app", host=os.environ.get("HOST", "127.0.0.1"), port=port,
                reload="--reload" in sys.argv, reload_dirs=[str(ROOT / "src")], proxy_headers=True,
                forwarded_allow_ips="*")
