# source\services\vault\app\healthcheck.py


from __future__ import annotations
import sys
from pathlib import Path
import requests
import sys as _sys
_sys.path.append("/")
from core.base.settings import settings   # noqa: E402


# ────────────────────────────────────
VAULT_HOST = settings.VAULT_HOST
PORT       = settings.VAULT_PORT          # 8200

CA_FILE = Path("/certs/ca.crt")
USE_TLS = Path("/certs/vault.crt").exists() and CA_FILE.exists()


def main() -> None:
    scheme = "https" if USE_TLS else "http"
    url    = f"{scheme}://{VAULT_HOST}:{PORT}/v1/sys/health"

    kwargs: dict = {"timeout": 5, "verify": str(CA_FILE) if USE_TLS else False}

    try:
        r = requests.get(url, **kwargs)
        if r.status_code in (200, 429, 501, 503):
            sys.exit(0)
    except Exception:
        pass

    sys.exit(1)


if __name__ == "__main__":
    main()
