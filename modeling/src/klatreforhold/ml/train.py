"""Trening og evaluering mot etiketter. Alltid tidsdelt (trener på tidlig periode, tester på senere),
og alltid sammenlignet med fysikkmodellen alene, så vi ser om ML faktisk hjelper."""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import balanced_accuracy_score, roc_auc_score


def time_split(X: pd.DataFrame, y: pd.Series, test_frac: float = 0.3):
    idx = y.dropna().index.intersection(X.index).sort_values()
    cut = idx[int(len(idx) * (1 - test_frac))]
    tr = idx[idx < cut]
    te = idx[idx >= cut]
    return tr, te


def _scores(y_true, prob, pred) -> dict:
    out = {"n": int(len(y_true)), "andel_vatt": float(np.mean(y_true)),
           "balanced_accuracy": float(balanced_accuracy_score(y_true, pred))}
    if len(np.unique(y_true)) == 2:
        out["auc"] = float(roc_auc_score(y_true, prob))
    return out


def evaluate_physics(X: pd.DataFrame, y: pd.Series, te) -> dict:
    p = X.loc[te, "phys_water_mm"].to_numpy()
    return _scores(y.loc[te].astype(int).to_numpy(), p, X.loc[te, "phys_wet"].astype(int).to_numpy())


def evaluate_simple_rules(weather: pd.DataFrame, y: pd.Series, te) -> dict:
    """Enkle bladfukt-regler som fysikkmodellen MÅ slå (Sentelhas/Lulu m.fl.)."""
    from ..physics.solar import dew_point_c

    w = weather.reindex(te)
    yt = y.loc[te].astype(int).to_numpy()
    rh = w["relative_humidity"].to_numpy()
    dpd = w["air_temperature"].to_numpy() - dew_point_c(w["air_temperature"], w["relative_humidity"])
    rain = w["precipitation"].fillna(0).to_numpy() > 0
    rh_rule = ((rh >= 90) | rain).astype(int)
    dpd_rule = ((dpd < 2.0) | rain).astype(int)
    return {"regel_RH_90": _scores(yt, rh, rh_rule),
            "regel_duggpunktsdifferanse_2C": _scores(yt, -dpd, dpd_rule)}


def train_sklearn(X: pd.DataFrame, y: pd.Series, tr, te, use_physics: bool = True):
    cols = [c for c in X.columns if use_physics or not c.startswith("phys_")]
    m = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05, max_leaf_nodes=15,
                                       l2_regularization=1.0, class_weight="balanced", random_state=0)
    m.fit(X.loc[tr, cols], y.loc[tr].astype(int))
    prob = m.predict_proba(X.loc[te, cols])[:, 1]
    return m, cols, _scores(y.loc[te].astype(int).to_numpy(), prob, (prob > 0.5).astype(int))


def train_torch(X: pd.DataFrame, y: pd.Series, tr, te, window: int = 48, epochs: int = 40,
                hidden: int = 32, use_physics: bool = True):
    """Trener GRU-modellen (ml/torch_model.py) og evaluerer på testperioden."""
    from .torch_model import GRUWetModel, _device

    cols = [c for c in X.columns if use_physics or not c.startswith("phys_")]
    m = GRUWetModel(cols, window=window, hidden=hidden).fit(X, y, tr, epochs=epochs)
    prob = m.predict_proba(X).reindex(te)
    ok = prob.notna()
    yt = y.loc[te][ok.to_numpy()].astype(int).to_numpy()
    pv = prob[ok].to_numpy()
    return m, cols, {**_scores(yt, pv, (pv > 0.5).astype(int)), "device": _device()}
