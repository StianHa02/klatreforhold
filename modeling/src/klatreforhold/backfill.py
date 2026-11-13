"""Etterfylling av arkivet: spiller lagret vær (`vaer`) gjennom dagens konfigurasjon.

Gir én sammenhengende «analyse» per felt: modellens svar for hver passert time med dagens parametre og været
som faktisk kom. Det er ikke det opprinnelige varselet. Ledetider over 0 kan ikke gjenskapes, fordi
værprognosene ikke lagres. Derfor skal bare ledetid 0 (varselet for timen som akkurat kom) kunne skrives
tilbake til `varsel`; lengre ledetider beholder sin gamle konfigurasjon så treffsikkerheten forblir ærlig.
"""
from __future__ import annotations

import pandas as pd

from .physics.forcing import REQUIRED, prepare_weather
from .physics.wetness import hours_until_dry, run_model
from .predict import _format_hours, load_crag
from .version import MODEL_VERSION, config_hash

SPINUP_TIMER = 30 * 24  # samme innkjøring som timesjobben (predict.py)
# Kolonnene en etterfylling overskriver. p_vatt, p_tort og vaerkilde røres ikke (ML og MEPS kan ikke gjenskapes).
OPPDATERTE = ["status", "vann_mm", "is_mm", "sno_mm", "bergtemp", "duggpunkt", "nedbor_mm",
              "regn_mot_veggen_mm", "sol_pa_veggen"]


def sammenhengende_slutt(w: pd.DataFrame) -> pd.DataFrame:
    """Lengste sammenhengende stykke med komplett vær som ender på siste time. Hull gir ellers ValueError."""
    w = w.sort_index().asfreq("h")
    ok = w[REQUIRED].notna().all(axis=1)
    if ok.all():
        return w
    if not ok.iloc[-1]:
        w = w.loc[:ok[ok].index[-1]]
        ok = ok.loc[w.index]
    siste_hull = ok[~ok].index.max()
    return w.loc[siste_hull + pd.Timedelta(hours=1):]


def innkjoring(slug: str, forste_time: pd.Timestamp, fetch=None) -> pd.DataFrame:
    """Open-Meteo-vær for SPINUP_TIMER før første lagrede time. `fetch` kan byttes ut i tester."""
    crag, _ = load_crag(slug)
    if fetch is None:
        from .data import openmeteo
        fetch = lambda lat, lon: openmeteo.fetch_forecast(lat, lon, past_days=92, forecast_days=1)  # noqa: E731
    w = fetch(crag.lat, crag.lon).sort_index()
    w = w.loc[forste_time - pd.Timedelta(hours=SPINUP_TIMER):forste_time - pd.Timedelta(hours=1)]
    w = w.assign(weather_source=w.get("weather_source", "openmeteo"), weather_kind="spinup")
    return w


def spill_om(slug: str, vaer: pd.DataFrame, spinup: pd.DataFrame | None = None) -> tuple[pd.DataFrame, dict]:
    """Kjører modellen over vaer (+ innkjøring). Returnerer (resultat per time, info).

    Timer før første lagrede time er innkjøring og returneres ikke som gyldige (`analyse_gyldig`)."""
    crag, params = load_crag(slug)
    vaer = sammenhengende_slutt(vaer)
    forste = vaer.index[0]
    w = vaer
    if spinup is not None and not spinup.empty:
        w = sammenhengende_slutt(pd.concat([spinup.loc[:forste - pd.Timedelta(hours=1)], vaer]))
        if w.index[0] > forste - pd.Timedelta(hours=1):  # hull rett før lagret vær: ingen brukbar innkjøring
            w = vaer
    prep = prepare_weather(w)
    res = run_model(prep, crag, params)
    res["hours_until_dry"] = hours_until_dry(res)
    innkjort = (forste - w.index[0]) / pd.Timedelta(hours=1)
    info = {"felt": slug, "konfigurasjon": config_hash(crag, params), "modellversjon": MODEL_VERSION,
            "fra": forste.isoformat(), "til": w.index[-1].isoformat(), "innkjoring_timer": int(innkjort),
            "innkjoring_fullstendig": innkjort >= SPINUP_TIMER}
    timer = _format_hours(res.loc[forste:], res, prep, None, crag)
    out = pd.DataFrame(timer)
    out["tid"] = pd.to_datetime(out["tid"], utc=True)
    return out.set_index("tid"), info


def endringer(arkiv: pd.DataFrame, analyse: pd.DataFrame, konfigurasjon: str) -> pd.DataFrame:
    """Arkivrader med annen konfigurasjon enn dagens, parret med analysen for samme time.

    arkiv: kolonnene felt, generert, tid, ledetid_timer, status, konfigurasjon. Kolonner `ny_*` er den nye analysen."""
    if arkiv.empty:
        return arkiv.copy()
    a = arkiv.copy()
    a["tid"] = pd.to_datetime(a["tid"], utc=True)
    a = a[(a["konfigurasjon"] != konfigurasjon) & a["tid"].isin(analyse.index)]
    nytt = analyse.loc[a["tid"], ["status", "vann_mm", "is_mm", "sno_mm", "bergtemp", "duggpunkt",
                                  "nedbor_mm", "regn_mot_veggen_mm", "sol_pa_veggen"]]
    nytt.index = a.index
    a = a.join(nytt.add_prefix("ny_"))
    a["status_endret"] = a["status"] != a["ny_status"]
    return a


def skriverader(felt: str, endret: pd.DataFrame, konfigurasjon: str, modellversjon: str = MODEL_VERSION) -> list[dict]:
    """Rader som kan skrives tilbake: bare ledetid 0. Ledetider over 0 er varsler med et vær som ikke lagres."""
    rader = []
    for r in endret[endret["ledetid_timer"] == 0].itertuples():
        rad = {"felt": felt, "generert": pd.Timestamp(r.generert).tz_convert("UTC").isoformat(),
               "tid": r.tid.isoformat(), "ledetid_timer": 0, "konfigurasjon": konfigurasjon,
               "modellversjon": modellversjon}
        for k in OPPDATERTE:
            v = getattr(r, f"ny_{k}")
            rad[k] = bool(v) if k == "sol_pa_veggen" else (v if isinstance(v, str) else float(v))
        rader.append(rad)
    return rader
