"""Kalibrering av fysikkmodellen mot brukernes observasjoner, laget for skjeve data.

Ideen: hver observasjon er et vitnesbyrd om hvor mye vann modellen burde hatt på veggen akkurat da.
"Tørt 8 timer etter 5 mm regn" sier at veggen tørker raskere enn det; "fortsatt vått" sier motsatt.
Vi finner de få parametrene som gjør observasjonene mest sannsynlige (maksimum a posteriori):

  P(vått | vann) = sigmoid((ln(vann + eps) - ln(terskel)) / skala)
  mål = -sum(vekt * loglik) + prior

Hvorfor dette tåler at folk mest er der når det er tørt:
  - Observasjoner i lange tørkeperioder har nesten null vann uansett parametre, så de bidrar nesten
    ingenting til gradienten. Det er timene rett etter regn som flytter parametrene, og der er
    tørt-observasjoner like nyttige som vått-observasjoner (de setter en grense for tørketiden).
  - Prioren holder parametrene nær litteraturverdiene når det er få observasjoner.
  - Valgfrie vekter (1/sannsynlighet for å bli observert) kan rette opp for hvem som drar når.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from ..config import Crag
from ..physics.wetness import DEFAULTS, run_model

# Parametre som kalibreres, med (prior-median, prior-sd i log-rom, nedre, øvre grense)
PARAMS = {
    "wdr_coefficient":     (0.12, 0.7, 0.01, 0.4),   # hvor mye slagregn veggen fanger
    "holds_capacity_mm":   (0.6, 0.7, 0.05, 3.0),    # vann i tak/sprekker
    "holds_drying_factor": (0.5, 0.7, 0.05, 1.0),    # hvor fort tak/sprekker tørker
}
# wind_exposure kalibreres IKKE: i slagregnformelen ganges den med wdr_coefficient, så dataene kan ikke
# skille dem (kun produktet er identifiserbart). Den beholdes fra konfigen.
EPS = 1e-3


@dataclass
class Resultat:
    params: dict
    prior_params: dict
    nll_for: float
    nll_etter: float
    n: int


def _p_wet(water: np.ndarray, threshold: float, scale: float = 0.6) -> np.ndarray:
    z = (np.log(water + EPS) - np.log(threshold)) / scale
    return 1.0 / (1.0 + np.exp(-z))


def neg_log_lik(water_at_obs: np.ndarray, y: np.ndarray, w: np.ndarray, threshold: float) -> float:
    p = np.clip(_p_wet(water_at_obs, threshold), 1e-4, 1 - 1e-4)
    return float(-np.sum(w * (y * np.log(p) + (1 - y) * np.log(1 - p))))


def _to_x(params: dict) -> np.ndarray:
    return np.array([np.log(params[k]) for k in PARAMS])


def _from_x(x: np.ndarray) -> dict:
    out = {}
    for (k, (_, _, lo, hi)), v in zip(PARAMS.items(), x):
        out[k] = float(np.clip(np.exp(v), lo, hi))
    return out


def _window(weather: pd.DataFrame, obs_index: pd.DatetimeIndex, spinup_days: int = 14) -> pd.DataFrame:
    """Kutt værserien til perioden med observasjoner (+ innkjøring), så kalibreringen går raskt."""
    start = obs_index.min() - pd.Timedelta(days=spinup_days)
    return weather.loc[start: obs_index.max()]


def calibrate(weather: pd.DataFrame, labels: pd.Series, crag: Crag, base_params: dict,
              weights: pd.Series | None = None, prior_strength: float = 1.0, maxiter: int = 200,
              verbose: bool = False) -> Resultat:
    """labels: bool (True = vått/fuktig) på hele timer (UTC). Returnerer kalibrerte parametre."""
    labels = labels.dropna().astype(bool)
    w = weather.sort_index()
    labels = labels[labels.index.isin(w.index)]
    if len(labels) < 5:
        raise ValueError(f"For få observasjoner å kalibrere på ({len(labels)})")
    ww = _window(w, labels.index)
    y = labels.to_numpy().astype(float)
    wt = np.ones(len(y)) if weights is None else weights.reindex(labels.index).fillna(1.0).to_numpy()
    base = {**DEFAULTS, **base_params}
    prior = {k: base.get(k, v[0]) for k, v in PARAMS.items()}
    mu = _to_x(prior)
    sd = np.array([v[1] for v in PARAMS.values()]) / max(prior_strength, 1e-6) ** 0.5
    threshold = base["wet_threshold_mm"]
    cache: dict[tuple, float] = {}

    def objective(x):
        key = tuple(np.round(x, 4))
        if key in cache:
            return cache[key]
        p = {**base, **_from_x(x)}
        res = run_model(ww, crag, p, substeps=6)
        water = res["water_mm"].reindex(labels.index).to_numpy()
        val = neg_log_lik(water, y, wt, threshold) + 0.5 * float(np.sum(((x - mu) / sd) ** 2))
        cache[key] = val
        if verbose:
            print(f"  {val:9.3f}  " + "  ".join(f"{k}={v:.3f}" for k, v in _from_x(x).items()))
        return val

    nll0 = objective(mu)
    opt = minimize(objective, mu, method="Nelder-Mead",
                   options={"maxiter": maxiter, "xatol": 0.02, "fatol": 0.01, "initial_simplex": None})
    best = _from_x(opt.x)
    return Resultat(params=best, prior_params=prior, nll_for=nll0, nll_etter=float(opt.fun), n=len(y))


def observation_propensity_weights(weather: pd.DataFrame, observed_index: pd.DatetimeIndex,
                                   timezone: str = "Europe/Oslo", clip: float = 10.0) -> pd.Series:
    """Vekt = 1 / P(observert | vær og tidspunkt), estimert med logistisk regresjon over alle timer.

    Retter opp for at folk mest drar på tørre ettermiddager i helger. Retter bare opp for det vi kan se
    (vær, tid), ikke for at folk snur når det ser vått ut.
    """
    from sklearn.linear_model import LogisticRegression

    from .features import hours_since

    w = weather.sort_index()
    local = w.index.tz_convert(timezone)
    p = w["precipitation"].fillna(0)
    X = pd.DataFrame({
        "regn_24t": p.rolling(24, min_periods=1).sum(),
        "timer_siden_regn": hours_since(p >= 0.2).clip(upper=168),
        "rh": w["relative_humidity"],
        "temp": w["air_temperature"],
        "helg": (local.dayofweek >= 5).astype(float),
        "time_sin": np.sin(2 * np.pi * local.hour / 24), "time_cos": np.cos(2 * np.pi * local.hour / 24),
        "doy_sin": np.sin(2 * np.pi * local.dayofyear / 365.25), "doy_cos": np.cos(2 * np.pi * local.dayofyear / 365.25),
    }, index=w.index).fillna(0)
    yobs = w.index.isin(observed_index).astype(int)
    if yobs.sum() < 5:
        return pd.Series(1.0, index=observed_index)
    m = LogisticRegression(max_iter=1000, class_weight=None).fit((X - X.mean()) / X.std().replace(0, 1), yobs)
    prop = pd.Series(m.predict_proba((X - X.mean()) / X.std().replace(0, 1))[:, 1], index=w.index)
    wts = (1.0 / prop.reindex(observed_index)).clip(upper=None)
    wts = wts / wts.mean()
    return wts.clip(upper=clip)
