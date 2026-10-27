"""Kontroll av værvarselet mot målestasjoner (Frost).

Vi lagrer varselet for stasjonens EGNE koordinater, ikke feltets. Da måler vi hvor godt varselet treffer
værets faktiske utvikling, og ikke forskjellen mellom to steder (Bergen-været er veldig lokalt).

- collect():        kalles av timesjobben. Lagrer varselet for stasjonen (0-48 t fram) og siste målinger.
- scores():         treff per ledetid: regn (traff vi timene med regn?), temperatur, luftfuktighet, vind.
- scripts/verify_forecast.py bruker dette både på arkivet i Supabase og på flere år med historikk.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# Open-Meteo-kolonner -> tabellkolonner
VAR = {"air_temperature": "lufttemp", "relative_humidity": "luftfuktighet", "precipitation": "nedbor_mm",
       "wind_speed": "vind_ms", "wind_direction": "vindretning"}
REGN_MM = 0.2
LEDETIDER = [(0, 0, "nå"), (1, 6, "1-6 t"), (7, 12, "7-12 t"), (13, 24, "13-24 t"), (25, 48, "25-48 t")]


def forecast_rows(station: str, w: pd.DataFrame, generert: pd.Timestamp, max_lead: int = 48) -> list[dict]:
    fram = w.loc[generert: generert + pd.Timedelta(hours=max_lead)]
    rows = []
    for t, r in fram.iterrows():
        row = {"stasjon": station, "generert": generert.isoformat(), "tid": t.isoformat(),
               "ledetid_timer": int((t - generert) / pd.Timedelta(hours=1))}
        for src, dst in VAR.items():
            v = r.get(src)
            row[dst] = None if v is None or pd.isna(v) else round(float(v), 2)
        rows.append(row)
    return rows


def observation_rows(station: str, obs: pd.DataFrame) -> list[dict]:
    rows = []
    for t, r in obs.dropna(how="all").iterrows():
        row = {"stasjon": station, "tid": t.isoformat()}
        for src, dst in VAR.items():
            v = r.get(src)
            row[dst] = None if v is None or pd.isna(v) else round(float(v), 2)
        rows.append(row)
    return rows


def collect(storage, stations: list[str], now: pd.Timestamp | None = None) -> dict:
    """Henter og lagrer varsel (for stasjonens koordinater) og målinger for hver stasjon."""
    from .data.frost import fetch_recent, station_info
    from .data.openmeteo import fetch_forecast

    now = (now or pd.Timestamp.now(tz="UTC")).ceil("h")
    out = {}
    for st in sorted(set(stations)):
        try:
            info = station_info(st)
            w = fetch_forecast(info["lat"], info["lon"], past_days=1, forecast_days=3)
            obs = fetch_recent(st, hours=48)
            nf = storage.save_station_forecast(forecast_rows(st, w, now))
            no = storage.save_station_obs(observation_rows(st, obs))
            out[st] = {"varseltimer": nf, "malinger": no, "navn": info.get("navn")}
        except Exception as err:  # kontrollen skal aldri stoppe varselet
            out[st] = {"advarsel": str(err)}
    return out


def _regn(pred_mm: np.ndarray, obs_mm: np.ndarray) -> dict:
    p, o = pred_mm >= REGN_MM, obs_mm >= REGN_MM
    hits, miss, fa = int((p & o).sum()), int((~p & o).sum()), int((p & ~o).sum())
    return {
        "regntimer_malt": int(o.sum()),
        "traff_regn": None if hits + miss == 0 else round(hits / (hits + miss), 3),   # andel regntimer varselet fanget
        "falsk_regn": None if hits + fa == 0 else round(fa / (hits + fa), 3),         # andel varslet regn som uteble
        "mm_forhold": None if obs_mm.sum() == 0 else round(float(pred_mm.sum() / obs_mm.sum()), 2),
    }


def scores(fc: pd.DataFrame, obs: pd.DataFrame, by_lead: bool = True) -> pd.DataFrame:
    """fc: kolonner tid, (ledetid_timer), lufttemp, luftfuktighet, nedbor_mm, vind_ms. obs: samme, indeksert på tid."""
    fc = fc.copy()
    fc["tid"] = pd.to_datetime(fc["tid"], utc=True)
    obs = obs.copy()
    obs.index = pd.to_datetime(obs.index, utc=True)
    j = fc.join(obs, on="tid", rsuffix="_malt", how="inner")
    groups = [(lo, hi, name) for lo, hi, name in LEDETIDER] if by_lead and "ledetid_timer" in j else [(None, None, "alle")]
    rows = []
    for lo, hi, name in groups:
        g = j if lo is None else j[(j["ledetid_timer"] >= lo) & (j["ledetid_timer"] <= hi)]
        if g.empty:
            continue
        row = {"ledetid": name, "timer": int(len(g))}
        for v, navn in [("lufttemp", "temp"), ("luftfuktighet", "rh"), ("vind_ms", "vind")]:
            d = (g[v] - g[f"{v}_malt"]).dropna()
            row[f"{navn}_mae"] = None if d.empty else round(float(d.abs().mean()), 2)
            row[f"{navn}_skjevhet"] = None if d.empty else round(float(d.mean()), 2)
        r = g[["nedbor_mm", "nedbor_mm_malt"]].dropna()
        row.update(_regn(r["nedbor_mm"].to_numpy(), r["nedbor_mm_malt"].to_numpy()))
        rows.append(row)
    return pd.DataFrame(rows)


def rain_windows(fc_mm: pd.Series, obs_mm: pd.Series) -> dict:
    """Regn over lengre vinduer. For tørking teller hvor mye som kom siste 6-24 t, ikke nøyaktig hvilken time."""
    j = pd.concat({"v": fc_mm, "m": obs_mm}, axis=1).dropna()
    out = {}
    for h in (6, 24):
        r = j.resample(f"{h}h").sum(min_count=h // 2).dropna()
        p, o = r["v"] >= 0.5, r["m"] >= 0.5
        hits, miss, fa = int((p & o).sum()), int((~p & o).sum()), int((p & ~o).sum())
        out[f"traff_regn_{h}t"] = None if hits + miss == 0 else round(hits / (hits + miss), 3)
        out[f"falsk_regn_{h}t"] = None if hits + fa == 0 else round(fa / (hits + fa), 3)
    d = j.resample("24h").sum(min_count=12).dropna()
    out["korr_mm_24t"] = round(float(d["v"].corr(d["m"])), 3) if len(d) > 2 else None
    return out


def to_obs_frame(w: pd.DataFrame) -> pd.DataFrame:
    """Gjør en værramme (Open-Meteo/Frost-kolonner) om til tabellkolonnene."""
    return w.rename(columns=VAR)[[c for c in VAR.values() if c in w.rename(columns=VAR)]]
