"""Lagring av observasjoner og varselarkiv.

- Supabase (produksjon): settes opp når SUPABASE_URL og SUPABASE_SERVICE_ROLE_KEY finnes.
  Bruker PostgREST direkte med requests (ingen ekstra avhengighet).
- CSV i data/labels/ (lokal utvikling): brukes ellers.
"""
from __future__ import annotations

import csv
import os
import threading
from pathlib import Path

import pandas as pd
import requests

from .config import ROOT

FIELDS = ["time", "status", "predikert_status", "riktig", "kommentar", "kilde", "registrert"]


class CsvStorage:
    navn = "csv"

    def __init__(self, label_dir: Path | None = None):
        self.dir = Path(label_dir or ROOT / "data" / "labels")
        self._lock = threading.Lock()

    def _path(self, felt: str) -> Path:
        self.dir.mkdir(parents=True, exist_ok=True)
        return self.dir / f"{felt}_observasjoner.csv"

    def add_observation(self, felt: str, row: dict) -> None:
        path = self._path(felt)
        with self._lock:
            new = not path.exists() or path.stat().st_size == 0
            with open(path, "a", newline="", encoding="utf-8") as f:
                wr = csv.DictWriter(f, fieldnames=FIELDS)
                if new:
                    wr.writeheader()
                wr.writerow({k: row.get(k, "") for k in FIELDS})

    def list_observations(self, felt: str, limit: int = 50) -> pd.DataFrame:
        path = self._path(felt)
        if not path.exists() or path.stat().st_size == 0:
            return pd.DataFrame(columns=FIELDS)
        df = pd.read_csv(path, dtype={"kommentar": str}).fillna("")
        return df.tail(limit).iloc[::-1]

    def save_forecast(self, felt: str, rows: list[dict]) -> int:
        return 0  # varselarkiv lagres bare i Supabase

    def save_station_forecast(self, rows: list[dict]) -> int:
        return 0

    def save_station_obs(self, rows: list[dict]) -> int:
        return 0


class SupabaseStorage:
    navn = "supabase"

    def __init__(self, url: str, key: str):
        self.base = url.rstrip("/") + "/rest/v1"
        self.s = requests.Session()
        self.s.headers.update({"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"})

    def add_observation(self, felt: str, row: dict) -> None:
        body = {"felt": felt, "tid": row["time"], "status": row["status"],
                "predikert_status": row.get("predikert_status") or None,
                "riktig": None if row.get("riktig") in ("", None) else bool(int(row["riktig"])),
                "kommentar": row.get("kommentar") or None, "kilde": row.get("kilde") or "web"}
        r = self.s.post(f"{self.base}/observasjoner", json=body, headers={"Prefer": "return=minimal"}, timeout=20)
        r.raise_for_status()

    def list_observations(self, felt: str, limit: int = 50) -> pd.DataFrame:
        r = self.s.get(f"{self.base}/observasjoner", params={
            "felt": f"eq.{felt}", "order": "registrert.desc", "limit": str(limit),
            "select": "tid,status,predikert_status,riktig,kommentar,kilde,registrert"}, timeout=20)
        r.raise_for_status()
        df = pd.DataFrame(r.json())
        if df.empty:
            return pd.DataFrame(columns=FIELDS)
        df = df.rename(columns={"tid": "time"})
        df["riktig"] = df["riktig"].map(lambda v: "" if v is None else int(bool(v)))
        return df.fillna("")

    def all_observations(self, felt: str | None = None, include_dev: bool = False) -> pd.DataFrame:
        """Alle observasjoner (for trening), sidevis. Observasjoner fra utvikling (kilde=dev/test) utelates."""
        out, start, page = [], 0, 1000
        while True:
            params = {"select": "*", "order": "id.asc"}
            if felt:
                params["felt"] = f"eq.{felt}"
            if not include_dev:
                params["kilde"] = "not.in.(dev,test)"
            r = self.s.get(f"{self.base}/observasjoner", params=params,
                           headers={"Range-Unit": "items", "Range": f"{start}-{start + page - 1}"}, timeout=30)
            r.raise_for_status()
            rows = r.json()
            out.extend(rows)
            if len(rows) < page:
                break
            start += page
        return pd.DataFrame(out)

    def forecast_archive(self, felt: str) -> pd.DataFrame:
        """Hele varselarkivet for feltet (tid, generert, ledetid_timer, status), sidevis."""
        out, start, page = [], 0, 1000
        while True:
            r = self.s.get(f"{self.base}/varsel", params={
                "felt": f"eq.{felt}", "select": "tid,generert,ledetid_timer,status", "order": "generert.asc,tid.asc"},
                headers={"Range-Unit": "items", "Range": f"{start}-{start + page - 1}"}, timeout=60)
            r.raise_for_status()
            rows = r.json()
            out.extend(rows)
            if len(rows) < page:
                break
            start += page
        return pd.DataFrame(out)

    def save_latest(self, felt: str, varsel: dict) -> None:
        """Overskriver siste komplette varsel for feltet (leses av nettsiden)."""
        body = {"felt": felt, "generert": varsel["generert"], "data": varsel}
        r = self.s.post(f"{self.base}/varsel_siste", json=body, params={"on_conflict": "felt"},
                        headers={"Prefer": "resolution=merge-duplicates,return=minimal"}, timeout=30)
        r.raise_for_status()

    def _upsert(self, table: str, rows: list[dict], conflict: str) -> int:
        if not rows:
            return 0
        r = self.s.post(f"{self.base}/{table}", json=rows, params={"on_conflict": conflict},
                        headers={"Prefer": "resolution=merge-duplicates,return=minimal"}, timeout=60)
        r.raise_for_status()
        return len(rows)

    def save_station_forecast(self, rows: list[dict]) -> int:
        return self._upsert("stasjon_varsel", rows, "stasjon,generert,tid")

    def save_station_obs(self, rows: list[dict]) -> int:
        return self._upsert("stasjon_maling", rows, "stasjon,tid")

    def station_forecasts(self, station: str) -> pd.DataFrame:
        return _paged(self, "stasjon_varsel", {"stasjon": f"eq.{station}", "select": "*", "order": "generert.asc,tid.asc"})

    def station_observations(self, station: str) -> pd.DataFrame:
        return _paged(self, "stasjon_maling", {"stasjon": f"eq.{station}", "select": "*", "order": "tid.asc"})

    def save_forecast(self, felt: str, rows: list[dict]) -> int:
        if not rows:
            return 0
        r = self.s.post(f"{self.base}/varsel", json=rows, params={"on_conflict": "felt,generert,tid"},
                        headers={"Prefer": "resolution=merge-duplicates,return=minimal"}, timeout=30)
        r.raise_for_status()
        return len(rows)


def _paged(storage, table: str, params: dict, page: int = 1000) -> pd.DataFrame:
    out, start = [], 0
    while True:
        r = storage.s.get(f"{storage.base}/{table}", params=params,
                          headers={"Range-Unit": "items", "Range": f"{start}-{start + page - 1}"}, timeout=60)
        r.raise_for_status()
        rows = r.json()
        out.extend(rows)
        if len(rows) < page:
            return pd.DataFrame(out)
        start += page


def get_storage():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_SECRET_KEY")
    if url and key:
        return SupabaseStorage(url, key)
    return CsvStorage()
