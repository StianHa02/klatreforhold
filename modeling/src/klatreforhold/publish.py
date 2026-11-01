"""Timesjobben: kjør modellen for alle felt og skriv resultatet til Supabase.

- varsel_siste: hele varselet (nå, ut dag +4 fram, 7 døgn bakover) som nettsiden leser
- varsel:       én rad per time og ledetid (maks 48 t), for å måle treffsikkerhet per ledetid
- vaer:         værinput for passerte timer (siste 72 t), så trening kan bruke samme vær som varselet
"""
from __future__ import annotations

import json

import pandas as pd

import os

from .predict import list_crags, load_crag, predict
from .version import config_hash

HISTORIKK_TIMER = 7 * 24  # historikken på feltsiden
FRAM_TIMER = 5 * 24  # rekker alltid ut dag +4 i norsk tid (folk planlegger fire dager fram)
ARKIV_MAKS_LEDETID = 48  # lengre ledetider arkiveres ikke, så arkivet ikke vokser 2.5 ganger
VAER_TIMER = 72  # passerte timer som skrives til vaer hver kjøring; dekker hull i timesjobben opptil 3 døgn
# Målinger fra Bønes som hentes til modellen: API-et gir høyst 168 timer, som dekker visningshistorikken.
# Timene før det (oppvarming fra lagret tilstand) bruker modellens regn.
BONES_TIMER = 168
VAER_KOLONNER = ["air_temperature", "relative_humidity", "dew_point_2m", "precipitation", "cloud_cover", "ghi",
                 "dni", "dhi", "longwave_down", "wind_speed", "wind_direction", "snow_probability", "snow_water_mm",
                 "weather_source", "weather_kind", "weather_issued", "precipitation_source"]


def archive_rows(slug: str, v: dict) -> list[dict]:
    generert = pd.Timestamp(v["generert"]).tz_convert("UTC")
    return [{
        "felt": slug, "generert": generert.isoformat(),
        "tid": pd.Timestamp(h["tid"]).tz_convert("UTC").isoformat(),
        "ledetid_timer": max(0, int((pd.Timestamp(h["tid"]) - generert) / pd.Timedelta(hours=1))),
        "modellversjon": v.get("modellversjon"), "konfigurasjon": v.get("konfigurasjon"),
        "is_mm": h.get("is_mm"), "sno_mm": h.get("sno_mm"), "vaerkilde": h.get("vaerkilde"),
        "status": h["status"], "vann_mm": h["vann_mm"], "p_vatt": h["p_vatt"], "bergtemp": h["bergtemp"],
        "duggpunkt": h["duggpunkt"], "nedbor_mm": h["nedbor_mm"],
        "regn_mot_veggen_mm": h["regn_mot_veggen_mm"], "sol_pa_veggen": h["sol_pa_veggen"],
    } for h in v["timer"] if (pd.Timestamp(h["tid"]) - generert) <= pd.Timedelta(hours=ARKIV_MAKS_LEDETID)]


def weather_rows(slug: str, weather: pd.DataFrame, generert) -> list[dict]:
    """Rader til vaer: de siste VAER_TIMER passerte timene. Tomme verdier blir null (JSON tåler ikke NaN)."""
    generert = pd.Timestamp(generert).tz_convert("UTC")
    w = weather.loc[generert.floor("h") - pd.Timedelta(hours=VAER_TIMER - 1):generert.floor("h")]
    rows = []
    for t, h in w.iterrows():
        row = {"felt": slug, "tid": t.tz_convert("UTC").isoformat(), "generert": generert.isoformat()}
        for c in VAER_KOLONNER:
            v = h.get(c)
            if isinstance(v, str):
                row[c] = v or None
            else:
                row[c] = None if v is None or pd.isna(v) else float(v)
        rows.append(row)
    return rows


def collect_bones(storage, now: pd.Timestamp | None = None) -> tuple[dict, pd.DataFrame | None]:
    """Henter siste 168 timer fra Bønes i ett kall, lagrer siste måling som reserve, og gir timeverdier til modellen.

    Timeverdier returneres bare hvis et felt har regnmaler_bruk: erstatt. Svarer ikke historikk-API-et, brukes
    snapshot-tabellen bones_maling. Feil her stopper aldri varselet: uten målinger brukes modellens regn som før.
    """
    crags = [load_crag(c["slug"])[0] for c in list_crags()]
    if not any(c.regnmaler == "bones" for c in crags) or not hasattr(storage, "save_bones"):
        return {}, None
    from .data import bones
    erstatt = any(c.regnmaler == "bones" and c.regnmaler_bruk == "erstatt" for c in crags)
    now = now or pd.Timestamp.now(tz="UTC")
    status = {}
    try:
        raw = bones.fetch_raw(BONES_TIMER)
        rad = bones.latest_row(raw, now)
        status["lagret"] = storage.save_bones([rad]) if rad else 0
        if rad is None:
            status["advarsel"] = "målingen er ikke fersk"
        if not erstatt:
            return status, None
        timer = bones.hourly_from_raw(raw)
        status["timer"] = int(timer["precipitation"].notna().sum()) if "precipitation" in timer else 0
        return status, timer
    except Exception as err:
        status["advarsel"] = f"{type(err).__name__}: {err}"
    if not erstatt:
        return status, None
    try:
        malinger = storage.bones_readings(now - pd.Timedelta(hours=BONES_TIMER))
        timer = bones.hourly(malinger)
        status["timer_fra_lager"] = int(timer["precipitation"].notna().sum())
        return status, timer
    except Exception as err:
        status["advarsel_lesing"] = f"{type(err).__name__}: {err}"
        return status, None


def publish_all(storage, now: pd.Timestamp | None = None, dry_run: bool = False) -> dict:
    result = {}
    bones_regn = None
    if not dry_run:
        result["_bones"], bones_regn = collect_bones(storage, now)
        if not result["_bones"]:
            del result["_bones"]
    for c in list_crags():
        slug = c["slug"]
        try:
            checkpoint = None
            if not dry_run and hasattr(storage, "load_checkpoint"):
                crag, params = load_crag(slug)
                before = (now or pd.Timestamp.now(tz="UTC")) - pd.Timedelta(hours=HISTORIKK_TIMER + 24)
                checkpoint = storage.load_checkpoint(slug, before, config_hash(crag, params))
            v = predict(slug, now=now, hours=FRAM_TIMER, history_hours=HISTORIKK_TIMER, checkpoint=checkpoint,
                        include_checkpoints=not dry_run, include_weather=not dry_run, bones_regn=bones_regn)
            checkpoints = v.pop("_checkpoints", [])
            weather = v.pop("_vaer", None)
            rows = archive_rows(slug, v)
            if dry_run:
                result[slug] = {"timer": len(v["timer"]), "arkivrader": len(rows), "bytes": len(json.dumps(v))}
                continue
            storage.save_forecast(slug, rows)
            storage.save_latest(slug, v)
            if checkpoints and hasattr(storage, "save_checkpoints"):
                storage.save_checkpoints(checkpoints)
            result[slug] = {"timer": len(rows), "status_na": v["sammendrag"]["status_na"]}
            if weather is not None and hasattr(storage, "save_weather"):
                try:  # treningsdata; varselet over er allerede publisert og skal ikke merkes som feilet
                    result[slug]["vaer"] = storage.save_weather(weather_rows(slug, weather, v["generert"]))
                except Exception as err:
                    result[slug]["vaer_feil"] = str(err)
        except Exception as err:  # ett felt som feiler skal ikke stoppe resten
            result[slug] = {"feil": str(err)}
    # Kontroll av værvarselet mot målestasjoner (bare med FROST_CLIENT_ID). Feil her stopper ikke jobben.
    stations = [load_crag(c["slug"])[0].frost_station for c in list_crags()]
    stations = [s for s in stations if s]
    if stations and os.environ.get("FROST_CLIENT_ID") and not dry_run:
        from .verify import collect
        result["_kontroll"] = collect(storage, stations, now=now)
    return result
