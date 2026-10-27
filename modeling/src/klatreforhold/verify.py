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


# ---------------------------------------------------------------------------------------------------
# Sesong og år: er feilene de samme hele året, og er de stabile fra år til år?

TZ = "Europe/Oslo"
SESONG = {12: "vinter", 1: "vinter", 2: "vinter", 3: "vår", 4: "vår", 5: "vår",
          6: "sommer", 7: "sommer", 8: "sommer", 9: "høst", 10: "høst", 11: "høst"}
SESONGER = ["vinter", "vår", "sommer", "høst"]
MANEDER = ["jan", "feb", "mar", "apr", "mai", "jun", "jul", "aug", "sep", "okt", "nov", "des"]


def period_key(index: pd.DatetimeIndex, by: str) -> pd.Index:
    local = pd.DatetimeIndex(index).tz_convert(TZ)
    if by == "sesong":
        return pd.Index([SESONG[m] for m in local.month])
    if by == "maned":
        return pd.Index([MANEDER[m - 1] for m in local.month])
    if by == "aar":
        return pd.Index(local.year.astype(str))
    if by == "doegn":
        return pd.Index(pd.cut(local.hour, [-1, 5, 11, 17, 23], labels=["00-06", "06-12", "12-18", "18-24"]).astype(str))
    raise ValueError(by)


def _order(by: str, keys) -> list:
    ref = {"sesong": SESONGER, "maned": MANEDER}.get(by)
    return [k for k in ref if k in set(keys)] if ref else sorted(set(keys))


def scores_by(fc: pd.DataFrame, obs: pd.DataFrame, by: str) -> pd.DataFrame:
    """Samme tall som scores(), men per sesong, måned, år eller tid på døgnet."""
    fc = fc.copy()
    fc["tid"] = pd.to_datetime(fc["tid"], utc=True)
    key = period_key(pd.DatetimeIndex(fc["tid"]), by)
    rows = []
    for k in _order(by, key):
        r = scores(fc[(key == k)], obs, by_lead=False)
        if not r.empty:
            r["ledetid"] = k
            rows.append(r)
    return pd.concat(rows).rename(columns={"ledetid": by}) if rows else pd.DataFrame()


def rain_windows_by(fc_mm: pd.Series, obs_mm: pd.Series, by: str) -> pd.DataFrame:
    key = period_key(fc_mm.index, by)
    rows = []
    for k in _order(by, key):
        m = np.asarray(key == k)
        rows.append({by: k, **rain_windows(fc_mm[m], obs_mm.reindex(fc_mm.index)[m])})
    return pd.DataFrame(rows)


def _rh_pair(fc_rh: pd.Series, obs_rh: pd.Series) -> pd.DataFrame:
    j = pd.concat({"v": fc_rh, "m": obs_rh}, axis=1).dropna()
    j.index = pd.to_datetime(j.index, utc=True)
    j["d"] = j["v"] - j["m"]
    return j


# Merk om fuktighet: sorterer man timene etter hva VARSELET sa, ser varselet alltid for fuktig ut i de fuktige
# timene og for tørt i de tørre, bare fordi tilfeldige feil er store (MAE ~8). Sorterer man etter det som ble
# MÅLT, snur fortegnet. Korreksjonen beregnes derfor fra ALLE timer, ikke fra et utvalg valgt på varselet.

def rh_bias_table(fc_rh: pd.Series, obs_rh: pd.Series, by: str) -> pd.DataFrame:
    """Skjevhet i luftfuktighet (varsel - målt) per periode, over alle timer."""
    j = _rh_pair(fc_rh, obs_rh)
    key = period_key(j.index, by)
    rows = []
    for k in _order(by, key):
        g = j[np.asarray(key == k)]
        rows.append({by: k, "timer": len(g), "skjevhet": round(g["d"].mean(), 2),
                     "median_varsel": round(g["v"].median(), 1), "median_malt": round(g["m"].median(), 1),
                     "andel_varsel>=95": round((g["v"] >= 95).mean(), 3), "andel_malt>=95": round((g["m"] >= 95).mean(), 3),
                     "mae": round(g["d"].abs().mean(), 2)})
    return pd.DataFrame(rows)


def rh_bias_year_month(fc_rh: pd.Series, obs_rh: pd.Series) -> pd.DataFrame:
    """Skjevhet over alle timer, år x måned. Viser om sesongmønsteret går igjen hvert år."""
    j = _rh_pair(fc_rh, obs_rh)
    t = pd.DataFrame({"aar": period_key(j.index, "aar"), "maned": period_key(j.index, "maned"), "d": j["d"].to_numpy()})
    tab = t.pivot_table(index="aar", columns="maned", values="d", aggfunc="mean").round(1)
    return tab[[m for m in MANEDER if m in tab.columns]]


def rh_bias_by_level(fc_rh: pd.Series, obs_rh: pd.Series) -> pd.DataFrame:
    """Skjevhet etter fuktighetsnivå, sortert etter varselet og etter målingen.

    Snur fortegnet mellom de to kolonnene, er forskjellen mest tilfeldig feil og ikke en fast skjevhet.
    """
    j = _rh_pair(fc_rh, obs_rh)
    bins = [0, 60, 70, 80, 90, 95, 101]
    lab = ["<60", "60-70", "70-80", "80-90", "90-95", ">=95"]
    v = j.groupby(pd.cut(j["v"], bins, labels=lab, right=False), observed=False)["d"]
    m = j.groupby(pd.cut(j["m"], bins, labels=lab, right=False), observed=False)["d"]
    return pd.DataFrame({"rh": lab, "timer_varslet": v.size().to_numpy(), "skjevhet_etter_varslet": v.mean().round(2).to_numpy(),
                         "timer_malt": m.size().to_numpy(), "skjevhet_etter_malt": m.mean().round(2).to_numpy()})


def rh_quantiles(fc_rh: pd.Series, obs_rh: pd.Series) -> pd.DataFrame:
    """Fordelingen av varslet og målt fuktighet. Systematisk skjevhet uten tilfeldig feil."""
    j = _rh_pair(fc_rh, obs_rh)
    q = [0.05, 0.25, 0.5, 0.75, 0.9, 0.95, 0.99]
    return pd.DataFrame({"varsel": j["v"].quantile(q).round(1), "malt": j["m"].quantile(q).round(1)}).T.rename(
        columns=lambda x: f"p{int(round(x * 100))}")


def _smooth12(x: np.ndarray) -> np.ndarray:
    return 0.25 * np.roll(x, 1) + 0.5 * x + 0.25 * np.roll(x, -1)


def rh_correction_fit(fc_rh: pd.Series, obs_rh: pd.Series, min_hours: int = 300) -> dict:
    """Korreksjon (legges til varselet) per måned med døgnsvingning, fra alle timer over alle år.

    For hver måned tilpasses  skjevhet(t) = a + b cos(2 pi t/24) + c sin(2 pi t/24)  (t = lokal klokketime),
    og korreksjonen er minus dette. Månedsverdiene glattes med nabomånedene, fordi enkeltmåneder varierer
    mye fra år til år mens sesongmønsteret og døgnsvingningen går igjen.
    """
    j = _rh_pair(fc_rh, obs_rh)
    if j.empty:
        return {}
    loc = j.index.tz_convert(TZ)
    h = loc.hour.to_numpy()
    X = np.c_[np.ones(len(j)), np.cos(2 * np.pi * h / 24), np.sin(2 * np.pi * h / 24)]
    alle = np.linalg.lstsq(X, j["d"].to_numpy(), rcond=None)[0]
    coef = []
    for mnd in range(1, 13):
        m = loc.month == mnd
        coef.append(np.linalg.lstsq(X[m], j["d"].to_numpy()[m], rcond=None)[0] if m.sum() >= min_hours else alle)
    coef = -np.array(coef)  # korreksjon = minus skjevheten
    a, b, c = (_smooth12(coef[:, k]) for k in range(3))
    r = lambda x: [round(float(v), 2) for v in x]
    return {"konstant": round(float(-alle[0]), 1), "maned": r(a), "doegn_cos": r(b), "doegn_sin": r(c),
            "timer": int(len(j)), "fra": str(j.index.min().date()), "til": str(j.index.max().date())}
