from __future__ import annotations

import os
import time

import requests

# api.met.no krever at User-Agent identifiserer appen med kontaktinfo.
# Sett KLATREFORHOLD_CONTACT til e-post eller nettside (f.eks. i .env / miljøvariabel).
CONTACT = os.environ.get("KLATREFORHOLD_CONTACT", "https://ute.bergenklatreklubb.no")
USER_AGENT = f"klatreforhold/0.1 ({CONTACT})"

_session = requests.Session()
_session.headers["User-Agent"] = USER_AGENT


def get(url: str, params: dict | None = None, auth=None, retries: int = 3, timeout: int = 60):
    for attempt in range(retries):
        try:
            r = _session.get(url, params=params, auth=auth, timeout=timeout)
        except (requests.Timeout, requests.ConnectionError):
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)
            continue
        if r.status_code in (429, 500, 502, 503, 504) and attempt < retries - 1:
            time.sleep(2 ** attempt * 5)
            continue
        r.raise_for_status()
        return r
    r.raise_for_status()
