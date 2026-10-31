"""Samler vær uten å skjule hull; kilde følger hver time og hvert nedbørsoverlegg."""
import logging
import math
import pandas as pd
from . import openmeteo, metnordic_thredds
from .nowcast import fetch_nowcast, apply_nowcast
from ..physics.forcing import REQUIRED

log = logging.getLogger(__name__)


def overlay(base, preferred):
    """Bytter komplette timeverdier; reservefelt må ikke blande gammel GHI med ny DNI."""
    if preferred.empty:
        return base
    usable = preferred.dropna(subset=REQUIRED)
    idx = base.index.intersection(usable.index)
    result = base.copy()
    for col in usable:
        if col not in result:
            result[col] = float("nan") if pd.api.types.is_numeric_dtype(usable[col]) else ""
        elif pd.api.types.is_numeric_dtype(usable[col]) and pd.api.types.is_numeric_dtype(result[col]):
            result[col] = result[col].astype(float)
        result.loc[idx, col] = usable.loc[idx, col]
    for col in ("dni", "dhi", "snow_water_mm"):
        if col in result and col not in usable:
            result.loc[idx, col] = float("nan")
    return result


def fetch_weather(crag, source="auto", start=None, now=None, history_hours=24):
    now = pd.Timestamp(now or pd.Timestamp.now(tz="UTC")).tz_convert("UTC")
    display_start = now.floor("h") - pd.Timedelta(hours=history_hours)
    begin = pd.Timestamp(start) if start is not None else display_start - pd.Timedelta(days=30)
    # Prognose-API-et har nylig historikk også. Det unngår et tregt flerårsarkiv i timesjobben.
    past_days = min(92, max(2, math.ceil((now - begin).total_seconds()/86400)))
    # forecast_days teller hele UTC-døgn fra i dag. 120 t fram fra kl 23 UTC rekker inn i døgn sju,
    # så 6 døgn ga «Været dekker ikke hele det forespurte varselet» den siste timen før midnatt UTC.
    w = openmeteo.fetch_forecast(crag.lat, crag.lon, past_days=past_days, forecast_days=7)
    if start is None and w.loc[:now].air_temperature.le(0).any() and past_days < 90:
        past_days = min(92, 90 + math.ceil(history_hours/24))
        w = openmeteo.fetch_forecast(crag.lat, crag.lon, past_days=past_days, forecast_days=7)
        begin = max(w.index.min(), display_start - pd.Timedelta(days=90))
    w = w.sort_index().loc[begin:]
    fallback = []
    # Direkte MET er foretrukket for varselet og nylige analyser. Eldre oppvarming
    # kommer fra det sammenhengende Open-Meteo-arkivet og merkes som sådan.
    if source in ("auto", "metnordic"):
        try:
            native = metnordic_thredds.fetch_forecast(crag.lat, crag.lon)
            w = overlay(w, native)
            analyses = metnordic_thredds.fetch_history(crag.lat, crag.lon,
                max(begin, now.floor("h") - pd.Timedelta(hours=12)), now.floor("h") - pd.Timedelta(hours=1))
            w = overlay(w, analyses)
        except Exception as err:
            log.warning("Direkte MET utilgjengelig for %s (%s: %s); bruker reserve", crag.name, type(err).__name__, err)
            fallback.append("metnordic")
    elif source == "metno":
        from .metno import fetch_locationforecast
        w = overlay(w, fetch_locationforecast(crag.lat, crag.lon))
    if source in ("auto", "metnordic", "metno"):
        try:
            w = apply_nowcast(w, fetch_nowcast(crag.lat, crag.lon), now)
        except Exception as err:
            log.warning("Nowcast utilgjengelig (%s); beholder grunnvarsel", type(err).__name__)
            fallback.append("nowcast")
    if start is None:
        # Enkelte punkter har kortere arkiv enn API-ets past_days-grense. Kutt bare
        # ukjent start på innkjøringen, og behold minst 30 hele døgn før visningen.
        complete = w[REQUIRED].notna().all(axis=1)
        if complete.any():
            first = complete[complete].index[0]
            if first > display_start - pd.Timedelta(days=30):
                raise ValueError("Ufullstendig vær: mindre enn 30 døgn innkjøring før visningshistorikken")
            if first > w.index[0]:
                log.warning("Værarkivet mangler starten av innkjøringen; starter %s", first)
                w = w.loc[first:]
                begin = first
    w.attrs["fallback_sources"] = fallback
    w.attrs["bootstrap_days"] = (display_start - begin).total_seconds()/86400 if start is None else 0
    return w
