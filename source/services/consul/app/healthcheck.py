# source\services\consul\app\healthcheck.py


from __future__ import annotations
import sys
from pathlib import Path
import requests
import sys as _sys
_sys.path.append("/")
from core.base.settings import settings   # noqa: E402


# ────────────────────────────────────
CONSUL_HOST = settings.CONSUL_HOST
HTTP_PORT   = 8500
HTTPS_PORT  = 8501

CERT_CRT = Path("/certs/consul.crt")
CERT_KEY = Path("/certs/consul.key")
CA_FILE  = Path("/certs/ca.crt")


def main() -> None:
    use_https = CERT_CRT.exists() and CERT_KEY.exists() and CA_FILE.exists()
    scheme = "https" if use_https else "http"
    port   = HTTPS_PORT if use_https else HTTP_PORT
    url    = f"{scheme}://{CONSUL_HOST}:{port}/v1/status/leader"

    kwargs: dict = {"timeout": 5}
    if use_https:
        kwargs["verify"] = str(CA_FILE)
        kwargs["cert"]   = (str(CERT_CRT), str(CERT_KEY))  # mTLS
    else:
        kwargs["verify"] = False

    try:
        r = requests.get(url, **kwargs)
        if r.ok and r.text and r.text != '""':
            sys.exit(0)
    except Exception:
        pass

    sys.exit(1)


if __name__ == "__main__":
    main()
