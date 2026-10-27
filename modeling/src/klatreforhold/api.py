"""HTTP-API for klatreforhold (FastAPI). Kjører lokalt, i Docker og på Vercel.

  GET  /api/health
  GET  /api/felt                              felt med konfig
  GET  /api/felt/{slug}/varsel                status nå + hver time neste 24 t (+ 12 t bakover)
  POST /api/felt/{slug}/observasjoner         bruker sier tørt/fuktig/vått (blir treningsdata)
  GET  /api/felt/{slug}/observasjoner         siste observasjoner + hvor ofte varselet stemte
  POST /api/cron/lagre-varsel                 kalles hver time av Supabase Cron (krever CRON_SECRET)

Lagring: Supabase hvis SUPABASE_URL og SUPABASE_SERVICE_ROLE_KEY er satt, ellers CSV i data/labels/.
"""
from __future__ import annotations

import hmac
import os
import threading
import time
from datetime import datetime, timezone
from typing import Literal

import pandas as pd
from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .predict import list_crags, predict
from .storage import get_storage

CACHE_SECONDS = int(os.environ.get("KLATREFORHOLD_CACHE_SECONDS", "1200"))  # MET: ikke hent oftere enn nødvendig
_cache: dict[tuple, tuple[float, dict]] = {}
_lock = threading.Lock()
storage = get_storage()

app = FastAPI(title="klatreforhold", version="0.2.0",
              description="Er fjellet tørt? Prediksjon per time for klatrefelt i Bergen.")
app.add_middleware(CORSMiddleware, allow_origins=os.environ.get("KLATREFORHOLD_CORS", "*").split(","),
                   allow_methods=["GET", "POST"], allow_headers=["*"])


class Observasjon(BaseModel):
    status: Literal["tort", "fuktig", "vatt"] = Field(description="Hva brukeren opplevde på veggen")
    tid: datetime | None = Field(None, description="Når brukeren var der (standard: nå)")
    predikert_status: Literal["tort", "fuktig", "vatt", "is"] | None = Field(None, description="Hva varselet sa")
    kommentar: str | None = Field(None, max_length=500)
    kilde: str = Field("web", max_length=40)


def _known(slug: str):
    if slug not in {c["slug"] for c in list_crags()}:
        raise HTTPException(404, f"Ukjent felt: {slug}")


def _varsel(slug: str, timer: int = 24, kilde: str = "openmeteo", na: datetime | None = None) -> dict:
    key = (slug, timer, kilde, na.isoformat() if na else None)
    with _lock:
        hit = _cache.get(key)
        if hit and time.time() - hit[0] < CACHE_SECONDS:
            return hit[1]
    now = pd.Timestamp(na) if na else None
    if now is not None and now.tzinfo is None:
        now = now.tz_localize("Europe/Oslo")
    res = predict(slug, now=now, hours=timer, source=kilde)
    with _lock:
        _cache[key] = (time.time(), res)
    return res


@app.get("/api/health")
def health():
    return {"ok": True, "lagring": storage.navn}


@app.get("/api/felt")
def felt():
    return list_crags()


@app.get("/api/felt/{slug}/varsel")
def varsel(slug: str, timer: int = Query(24, ge=1, le=48), kilde: Literal["openmeteo", "metno"] = "openmeteo",
           na: datetime | None = Query(None, description="for testing: late som om klokka er dette")):
    _known(slug)
    try:
        return _varsel(slug, timer, kilde, na)
    except Exception as err:
        raise HTTPException(502, f"Klarte ikke å lage varsel: {err}") from err


@app.post("/api/felt/{slug}/observasjoner", status_code=201)
def ny_observasjon(slug: str, obs: Observasjon):
    _known(slug)
    t = obs.tid or datetime.now(timezone.utc)
    ts = pd.Timestamp(t)
    ts = ts.tz_localize("Europe/Oslo") if ts.tzinfo is None else ts
    t_utc = ts.tz_convert("UTC")
    now = pd.Timestamp.now(tz="UTC")
    if t_utc > now + pd.Timedelta(minutes=5):
        raise HTTPException(422, "Kan ikke registrere observasjoner fram i tid")
    if t_utc < now - pd.Timedelta(days=14):
        raise HTTPException(422, "Observasjonen er for gammel (maks 14 dager)")
    riktig = None
    if obs.predikert_status:  # to klasser: tørt mot ikke-tørt
        riktig = (obs.predikert_status == "tort") == (obs.status == "tort")
    row = {"time": t_utc.isoformat(), "status": obs.status, "predikert_status": obs.predikert_status or "",
           "riktig": "" if riktig is None else int(riktig), "kommentar": (obs.kommentar or "").replace("\n", " ").strip(),
           "kilde": os.environ.get("KLATREFORHOLD_KILDE") or obs.kilde, "registrert": datetime.now(timezone.utc).isoformat()}
    try:
        storage.add_observation(slug, row)
    except Exception as err:
        raise HTTPException(502, f"Klarte ikke å lagre: {err}") from err
    return {"lagret": row}


@app.get("/api/felt/{slug}/observasjoner")
def observasjoner(slug: str, siste: int = Query(50, ge=1, le=1000)):
    _known(slug)
    try:
        df = storage.list_observations(slug, limit=siste)
    except Exception as err:
        raise HTTPException(502, f"Klarte ikke å hente observasjoner: {err}") from err
    vurdert = df[df["riktig"].astype(str) != ""] if len(df) else df
    andel = round(float(vurdert["riktig"].astype(int).mean()), 3) if len(vurdert) else None
    return {"antall": int(len(df)), "antall_vurdert": int(len(vurdert)), "andel_riktig": andel,
            "observasjoner": df.to_dict(orient="records")}


@app.post("/api/cron/lagre-varsel")
def cron_lagre_varsel(authorization: str | None = Header(None)):
    """Lagrer varselet for alle felt i varselarkivet. Kalles av Supabase Cron hver time."""
    secret = os.environ.get("CRON_SECRET")
    if not secret or not authorization or not hmac.compare_digest(authorization, f"Bearer {secret}"):
        raise HTTPException(401, "Ugyldig nøkkel")
    resultat = {}
    for c in list_crags():
        slug = c["slug"]
        try:
            v = predict(slug, hours=48)
            generert = pd.Timestamp(v["na"]).tz_convert("UTC")
            rows = [{
                "felt": slug, "generert": generert.isoformat(),
                "tid": pd.Timestamp(h["tid"]).tz_convert("UTC").isoformat(),
                "ledetid_timer": int((pd.Timestamp(h["tid"]) - generert) / pd.Timedelta(hours=1)),
                "status": h["status"], "vann_mm": h["vann_mm"], "p_vatt": h["p_vatt"], "bergtemp": h["bergtemp"],
                "duggpunkt": h["duggpunkt"], "nedbor_mm": h["nedbor_mm"],
                "regn_mot_veggen_mm": h["regn_mot_veggen_mm"], "sol_pa_veggen": h["sol_pa_veggen"],
            } for h in v["timer"]]
            resultat[slug] = storage.save_forecast(slug, rows)
        except Exception as err:  # ett felt som feiler skal ikke stoppe resten
            resultat[slug] = f"feil: {err}"
    return {"lagret": resultat}
