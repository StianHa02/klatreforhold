"""Rettferdig evaluering når etikettene er skjeve.

Brukerne er mest på feltet når det er tørt. Total treffprosent blir da pen uansett, fordi nesten alt
er "tørt varslet, tørt observert" i lange tørkeperioder. Vi deler derfor opp etter værsituasjon:

  under_regn   det regner (>= 0.2 mm) denne timen
  etter_regn   0-48 timer siden sist det regnet: her avgjøres om modellen kan tørking
  torkeperiode mer enn 48 timer siden regn: lett å treffe, sier lite

og rapporterer treff på vått (sensitivitet) og tørt (spesifisitet) hver for seg.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .features import hours_since

STRATA = ["under_regn", "etter_regn", "torkeperiode"]


def strata(weather: pd.DataFrame, rain_mm: float = 0.2, after_h: int = 48) -> pd.Series:
    p = weather["precipitation"].fillna(0)
    since = hours_since(p >= rain_mm)
    s = np.where(p >= rain_mm, "under_regn", np.where(since <= after_h, "etter_regn", "torkeperiode"))
    return pd.Series(s, index=weather.index, name="situasjon")


def _metrics(y: np.ndarray, pred: np.ndarray) -> dict:
    y = y.astype(bool)
    pred = pred.astype(bool)
    n_wet, n_dry = int(y.sum()), int((~y).sum())
    sens = float((pred & y).sum() / n_wet) if n_wet else None      # vått varslet når det var vått
    spec = float((~pred & ~y).sum() / n_dry) if n_dry else None    # tørt varslet når det var tørt
    bal = None if sens is None or spec is None else (sens + spec) / 2
    return {"n": int(len(y)), "n_vatt": n_wet, "n_tort": n_dry, "treff_total": float((pred == y).mean()) if len(y) else None,
            "treff_vatt": sens, "treff_tort": spec, "balansert": bal,
            "falskt_tort": int((~pred & y).sum()), "falskt_tort_andel": None if sens is None else 1-sens}


def evaluate(pred_wet: pd.Series, labels: pd.Series, weather: pd.DataFrame) -> dict:
    """pred_wet/labels: bool-serier på timer (UTC). Returnerer metrikk totalt og per situasjon."""
    idx = labels.dropna().index.intersection(pred_wet.dropna().index)
    y = labels.loc[idx].astype(bool).to_numpy()
    pr = pred_wet.loc[idx].astype(bool).to_numpy()
    st = strata(weather).reindex(idx).to_numpy()
    out = {"totalt": _metrics(y, pr)}
    for s in STRATA:
        m = st == s
        out[s] = _metrics(y[m], pr[m])
    return out


def simple_rules(weather: pd.DataFrame) -> dict[str, pd.Series]:
    from ..physics.solar import dew_point_c
    w = weather
    rain = w["precipitation"].fillna(0) > 0
    dpd = w["air_temperature"] - dew_point_c(w["air_temperature"], w["relative_humidity"])
    return {"regel_RH_90": (w["relative_humidity"] >= 90) | rain, "regel_duggpunkt_2C": (dpd < 2.0) | rain,
            "regel_12t_etter_regn": hours_since(w.precipitation >= .2) < 12}


def rain_event_ids(weather: pd.DataFrame) -> pd.Series:
    rain = weather.precipitation.ge(.2)
    gap = hours_since(rain.shift(1, fill_value=False))
    return (rain & (gap >= 6)).cumsum().rename("regnepisode")


def event_split(weather, labels, fraction=.7):
    groups = rain_event_ids(weather).reindex(labels.index)
    groups = groups[groups > 0]
    unique = sorted(groups.unique())
    if len(unique) < 10:
        raise ValueError(f"Trenger minst 10 uavhengige regnepisoder; fant {len(unique)}")
    cut = unique[min(len(unique)-1, max(1, int(len(unique)*fraction)))]
    train, test = groups.index[groups < cut], groups.index[groups >= cut]
    if labels.loc[train].nunique() < 2 or labels.loc[test].nunique() < 2:
        raise ValueError("Både trenings- og testepisoder må inneholde tørt og ikke-tørt")
    return train, test


def forecast_skill_by_lead(archive: pd.DataFrame, labels: pd.Series,
                           leads: tuple = (0, 3, 6, 12, 24, 48)) -> pd.DataFrame:
    """Treff for varselet slik det så ut X timer i forveien (fra varselarkivet i Supabase).

    archive: kolonner tid, generert, ledetid_timer, status. labels: bool (True = vått) per time (UTC).
    For hver observasjon og ledetid brukes det nyeste varselet laget minst X timer før timen.
    """
    if archive.empty or labels.empty:
        return pd.DataFrame()
    a = archive.copy()
    a["tid"] = pd.to_datetime(a["tid"], utc=True)
    a["varslet_vatt"] = a["status"] != "tort"
    rows = []
    for lead in leads:
        sub = a[a["ledetid_timer"] >= lead].sort_values("generert").groupby("tid").tail(1).set_index("tid")
        idx = labels.index.intersection(sub.index)
        if len(idx) == 0:
            continue
        m = _metrics(labels.loc[idx].to_numpy(), sub.loc[idx, "varslet_vatt"].to_numpy())
        rows.append({"ledetid_timer": lead, **m})
    return pd.DataFrame(rows)


def format_table(results: dict[str, dict]) -> str:
    """results: {modellnavn: evaluate(...)} -> lesbar tabell."""
    lines = []
    for name, res in results.items():
        for s in ["totalt", *STRATA]:
            m = res[s]
            f = lambda v: "  - " if v is None else f"{v:4.2f}"  # noqa: E731
            lines.append(f"{name:<24} {s:<13} n={m['n']:<5} (vått {m['n_vatt']:<4}) total {f(m['treff_total'])}  "
                         f"vått {f(m['treff_vatt'])}  tørt {f(m['treff_tort'])}  balansert {f(m['balansert'])}")
        lines.append("")
    return "\n".join(lines)
