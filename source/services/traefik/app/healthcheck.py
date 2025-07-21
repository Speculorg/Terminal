# source\services\traefik\app\healthcheck.py


from __future__ import annotations
import sys
from pathlib import Path
import requests
import sys as _sys
_sys.path.append("/")
from core.base.settings import settings   # noqa: E402


# ────────────────────────────────────
TRAEFIK_HOST    = "traefik"
HTTPS_PORT      = 443
HTTP_PORT       = 80

CA_FILE = Path("/certs/ca.crt")
USE_TLS = CA_FILE.exists()

scheme = "https" if USE_TLS else "http"
port   = HTTPS_PORT if USE_TLS else HTTP_PORT
URL    = f"{scheme}://{TRAEFIK_HOST}:{port}/ping"


def main() -> None:
    try:
        r = requests.get(URL, timeout=5, verify=str(CA_FILE) if USE_TLS else False)
        if r.status_code == 200:
            sys.exit(0)
    except Exception:
        pass

    sys.exit(1)


if __name__ == "__main__":
    main()
