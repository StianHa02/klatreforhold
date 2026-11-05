"""Parquet-arkiv for varselarkivet (varsel, stasjon_varsel).

Hvert ferdige UTC-døgn (etter `generert`) eksporteres med alle ledetider til én Parquet-fil, lagres lokalt
i data/arkiv/ og lastes opp til den private Storage-bøtta `arkiv` i Supabase. Fila lastes ned igjen og
kontrolleres (sha256 og antall rader) før døgnet får en kvittering i tabellen `arkiv_eksport`.
rydd_arkiv() i databasen sletter bare rader fra kvitterte døgn, så ingenting går tapt.

Lese arkivet til analyse:  les_arkiv("varsel")  (etter `python scripts/eksporter_arkiv.py --hent`)
"""
from __future__ import annotations

import datetime as dt
import hashlib
import io
from pathlib import Path

import pandas as pd

from .config import ROOT
from .storage import SupabaseStorage, _paged

BOTTE = "arkiv"
LOKAL = ROOT / "data" / "arkiv"

# Kolonnetyper som i Postgres (real -> float32, smallint -> Int16). Ukjente kolonner blir float32 hvis de er
# tall, ellers tekst, så en ny kolonne i tabellen kommer med uten at koden må endres.
TABELLER = {
    "varsel": {"nokkel": ["felt", "generert", "tid"],
               "tekst": {"felt", "status", "modellversjon", "konfigurasjon", "vaerkilde"},
               "sannhet": {"sol_pa_veggen"}},
    "stasjon_varsel": {"nokkel": ["stasjon", "generert", "tid"], "tekst": {"stasjon"}, "sannhet": set()},
}
TID = {"generert", "tid"}
HELTALL = {"ledetid_timer"}


def sti(tabell: str, dato: dt.date) -> str:
    """Sti i bøtta og under data/arkiv/, f.eks. varsel/2026-11/varsel_2026-11-04.parquet."""
    return f"{tabell}/{dato:%Y-%m}/{tabell}_{dato:%Y-%m-%d}.parquet"


def typet(df: pd.DataFrame, tabell: str) -> pd.DataFrame:
    spec = TABELLER[tabell]
    df = df.copy()
    for col in df.columns:
        if col in TID:
            # Postgres lagrer mikrosekunder; fast enhet gir samme skjema uansett pandas-versjon
            df[col] = pd.to_datetime(df[col], utc=True, format="ISO8601").astype("datetime64[us, UTC]")
        elif col in HELTALL:
            df[col] = pd.to_numeric(df[col]).astype("Int16")
        elif col in spec["sannhet"]:
            df[col] = df[col].astype("boolean")
        elif col in spec["tekst"]:
            df[col] = df[col].astype("string")
        else:
            try:
                df[col] = pd.to_numeric(df[col]).astype("float32")
            except (ValueError, TypeError):
                df[col] = df[col].astype("string")
    return df.sort_values(spec["nokkel"], ignore_index=True)


def til_parquet(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    df.to_parquet(buf, engine="pyarrow", compression="zstd", index=False)
    return buf.getvalue()


def hent_dogn(st: SupabaseStorage, tabell: str, dato: dt.date) -> pd.DataFrame:
    """Alle rader med `generert` i UTC-døgnet, sidevis med stabil sortering (primærnøkkelen)."""
    fra = dt.datetime.combine(dato, dt.time(), dt.timezone.utc)
    til = fra + dt.timedelta(days=1)
    params = [("select", "*"), ("generert", f"gte.{fra.isoformat()}"), ("generert", f"lt.{til.isoformat()}"),
              ("order", ",".join(f"{k}.asc" for k in TABELLER[tabell]["nokkel"]))]
    return _paged(st, tabell, params)


def eldste_dato(st: SupabaseStorage, tabell: str) -> dt.date | None:
    r = st.s.get(f"{st.base}/{tabell}", params={"select": "generert", "order": "generert.asc", "limit": "1"},
                 timeout=30)
    r.raise_for_status()
    rows = r.json()
    return pd.Timestamp(rows[0]["generert"]).tz_convert("UTC").date() if rows else None


def kvitteringer(st: SupabaseStorage, tabell: str | None = None) -> pd.DataFrame:
    params = {"select": "*", "order": "tabell.asc,dato.asc"}
    if tabell:
        params["tabell"] = f"eq.{tabell}"
    return _paged(st, "arkiv_eksport", params)


def _storage_url(st: SupabaseStorage) -> str:
    return st.base.removesuffix("/rest/v1") + "/storage/v1"


def last_opp(st: SupabaseStorage, path: str, data: bytes) -> None:
    r = st.s.post(f"{_storage_url(st)}/object/{BOTTE}/{path}", data=data, timeout=120,
                  headers={"Content-Type": "application/vnd.apache.parquet", "x-upsert": "true"})
    r.raise_for_status()


def last_ned(st: SupabaseStorage, path: str) -> bytes:
    r = st.s.get(f"{_storage_url(st)}/object/{BOTTE}/{path}", timeout=120)
    r.raise_for_status()
    return r.content


def _skriv(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_bytes(data)
    tmp.replace(path)


def eksporter_dogn(st: SupabaseStorage, tabell: str, dato: dt.date, lokal: Path = LOKAL,
                   dry_run: bool = False) -> dict:
    """Eksporterer ett døgn. Returnerer kvitteringen (rader=0 betyr at døgnet er tomt og hoppes over)."""
    df = hent_dogn(st, tabell, dato)
    if df.empty:
        return {"tabell": tabell, "dato": dato.isoformat(), "rader": 0}
    data = til_parquet(typet(df, tabell))
    path = sti(tabell, dato)
    sha = hashlib.sha256(data).hexdigest()
    _skriv(lokal / path, data)
    kvittering = {"tabell": tabell, "dato": dato.isoformat(), "rader": len(df), "fil": path,
                  "bytes": len(data), "sha256": sha}
    if dry_run:
        return kvittering
    last_opp(st, path, data)
    tilbake = last_ned(st, path)
    if hashlib.sha256(tilbake).hexdigest() != sha or len(pd.read_parquet(io.BytesIO(tilbake))) != len(df):
        raise RuntimeError(f"{path}: fila i Storage stemmer ikke med den som ble lastet opp")
    st._upsert("arkiv_eksport", [kvittering], "tabell,dato")
    return kvittering


def eksporter(st: SupabaseStorage, til: dt.date | None = None, tabeller=None, lokal: Path = LOKAL,
              dry_run: bool = False, logg=print) -> list[dict]:
    """Eksporterer alle ferdige døgn til og med `til` (standard i går, UTC) som mangler kvittering."""
    til = til or dt.datetime.now(dt.timezone.utc).date() - dt.timedelta(days=1)
    i_dag = dt.datetime.now(dt.timezone.utc).date()
    if til >= i_dag:
        raise ValueError(f"{til} er ikke et ferdig døgn (UTC); bruk tidligst {i_dag - dt.timedelta(days=1)}")
    ut = []
    for tabell in tabeller or TABELLER:
        start = eldste_dato(st, tabell)
        if start is None:
            continue
        ferdige = kvitteringer(st, tabell)
        ferdige = set(pd.to_datetime(ferdige["dato"]).dt.date) if not ferdige.empty else set()
        dato = start
        while dato <= til:
            if dato not in ferdige:
                k = eksporter_dogn(st, tabell, dato, lokal, dry_run)
                logg(f"{tabell} {dato}: " + (f"{k['rader']} rader, {k['bytes'] / 1024:.0f} kB -> {k['fil']}"
                                             if k["rader"] else "ingen rader, hoppet over"))
                ut.append(k)
            dato += dt.timedelta(days=1)
    return ut


def hent(st: SupabaseStorage, lokal: Path = LOKAL, logg=print) -> int:
    """Laster ned kvitterte filer som mangler lokalt eller avviker (sha256). Returnerer antall nedlastet."""
    n = 0
    for k in kvitteringer(st).to_dict("records"):
        path = lokal / k["fil"]
        if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() == k["sha256"]:
            continue
        data = last_ned(st, k["fil"])
        if hashlib.sha256(data).hexdigest() != k["sha256"]:
            raise RuntimeError(f"{k['fil']}: sha256 stemmer ikke med kvitteringen")
        _skriv(path, data)
        logg(f"hentet {k['fil']}")
        n += 1
    return n


def les_arkiv(tabell: str = "varsel", lokal: Path = LOKAL) -> pd.DataFrame:
    """Hele det lokale Parquet-arkivet for tabellen som én DataFrame (alle ledetider)."""
    filer = sorted((lokal / tabell).glob(f"*/{tabell}_*.parquet"))
    if not filer:
        return pd.DataFrame()
    return pd.concat([pd.read_parquet(f) for f in filer], ignore_index=True)
