"""Timesjobben: kjør modellen for alle felt og skriv resultatet til Supabase.

- varsel_siste: hele varselet (nå, 48 t fram, 7 døgn bakover) som nettsiden leser
- varsel:       én rad per time, for å måle treffsikkerhet per ledetid senere
"""
from __future__ import annotations

import json

import pandas as pd

import os

from .predict import list_crags, load_crag, predict

HISTORIKK_TIMER = 7 * 24  # historikken på feltsiden


def archive_rows(slug: str, v: dict) -> list[dict]:
    generert = pd.Timestamp(v["na"]).tz_convert("UTC")
    return [{
        "felt": slug, "generert": generert.isoformat(),
        "tid": pd.Timestamp(h["tid"]).tz_convert("UTC").isoformat(),
        "ledetid_timer": int((pd.Timestamp(h["tid"]) - generert) / pd.Timedelta(hours=1)),
        "status": h["status"], "vann_mm": h["vann_mm"], "p_vatt": h["p_vatt"], "bergtemp": h["bergtemp"],
        "duggpunkt": h["duggpunkt"], "nedbor_mm": h["nedbor_mm"],
        "regn_mot_veggen_mm": h["regn_mot_veggen_mm"], "sol_pa_veggen": h["sol_pa_veggen"],
    } for h in v["timer"]]


def publish_all(storage, now: pd.Timestamp | None = None, dry_run: bool = False) -> dict:
    result = {}
    for c in list_crags():
        slug = c["slug"]
        try:
            v = predict(slug, now=now, hours=48, history_hours=HISTORIKK_TIMER)
            rows = archive_rows(slug, v)
            if dry_run:
                result[slug] = {"timer": len(v["timer"]), "bytes": len(json.dumps(v))}
                continue
            storage.save_latest(slug, v)
            storage.save_forecast(slug, rows)
            result[slug] = {"timer": len(rows), "status_na": v["sammendrag"]["status_na"]}
        except Exception as err:  # ett felt som feiler skal ikke stoppe resten
            result[slug] = {"feil": str(err)}
    # Kontroll av værvarselet mot målestasjoner (bare med FROST_CLIENT_ID). Feil her stopper ikke jobben.
    stations = [load_crag(c["slug"])[0].frost_station for c in list_crags()]
    stations = [s for s in stations if s]
    if stations and os.environ.get("FROST_CLIENT_ID") and not dry_run:
        from .verify import collect
        result["_kontroll"] = collect(storage, stations, now=now)
    return result
