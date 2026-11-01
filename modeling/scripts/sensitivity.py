"""Følsomhetsanalyse: hvor mye betyr hver modellparameter for status (tørt/fuktig/vått)?

Hver parameter endres én om gangen med ±faktor (standard ±50 %) på samme værserie, og innflytelse
måles som andel timer der status endres i forhold til basis. Resultatet vises som kake per gruppe
(regn på veggen, vannlagre, sig) og stolper per parameter, og lagres i outputs/<felt>_folsomhet.{png,csv}.

  python scripts/sensitivity.py                                   # Ekstraveggen, 92 døgn fra Open-Meteo
  python scripts/sensitivity.py --config config/bymuren.yaml --faktor 0.3
  python scripts/sensitivity.py --weather data/raw/<fil>.csv      # historikk fra fetch_history.py
"""
import argparse

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from _common import DEFAULT_CONFIG, ROOT
from train import load_weather

from klatreforhold.config import load_config
from klatreforhold.physics.wetness import run_model

GRUPPER = {
    "Regn på veggen": ["wdr_coefficient", "wdr_exponent", "wind_exposure", "direct_rain_fraction", "runoff_from_above"],
    "Vannlagre": ["film_capacity_mm", "holds_capacity_mm", "film_to_holds_rate", "holds_drying_factor"],
    "Sig": ["seep_catchment_factor", "seep_timescale_h", "seep_threshold_mm"],
}
FARGER = {"Regn på veggen": "#3b6fb6", "Vannlagre": "#e0732c", "Sig": "#4caf50"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(DEFAULT_CONFIG))
    ap.add_argument("--weather", help="CSV med værdata; ellers hentes 92 døgn fra Open-Meteo (cache i outputs/)")
    ap.add_argument("--faktor", type=float, default=0.5, help="relativ endring per parameter (0.5 = ±50 %%)")
    ap.add_argument("--refresh", action="store_true")
    a = ap.parse_args()
    crag, params = load_config(a.config)

    if a.weather:
        w = load_weather(a.weather)
    else:
        cache = ROOT / "outputs" / f"{crag.name.lower()}_vaer_92d.csv"
        if a.refresh or not cache.exists():
            from klatreforhold.data.openmeteo import fetch_forecast
            w = fetch_forecast(crag.lat, crag.lon, past_days=92, forecast_days=1)
            w.to_csv(cache)
        else:
            w = load_weather(cache)
    num = w.select_dtypes("number").columns
    w[num] = w[num].interpolate(limit=3)
    w = w.dropna(subset=["air_temperature", "precipitation"])

    basis = run_model(w, crag, params)
    n = len(basis)
    rader = []
    for gruppe, navn in GRUPPER.items():
        for p in navn:
            if p not in params:
                continue
            v0 = float(params[p])
            endret, vaat_diff = [], []
            for f in (1 - a.faktor, 1 + a.faktor):
                r = run_model(w, crag, {**params, p: v0 * f})
                endret.append((r["status"] != basis["status"]).mean() * 100)
                vaat_diff.append(int(r["wet"].sum() - basis["wet"].sum()))
            rader.append({"gruppe": gruppe, "parameter": p, "verdi": v0,
                          "endret_pst_lav": endret[0], "endret_pst_hoy": endret[1],
                          "endret_pst": float(np.mean(endret)),
                          "vaate_timer_lav": vaat_diff[0], "vaate_timer_hoy": vaat_diff[1]})
            print(f"{p:24s} {v0:>8.3g}  status endret {endret[0]:5.1f} % / {endret[1]:5.1f} %   "
                  f"våte timer {vaat_diff[0]:+d} / {vaat_diff[1]:+d}")
    df = pd.DataFrame(rader).sort_values("endret_pst", ascending=False)
    out = ROOT / "outputs" / f"{crag.name.lower()}_folsomhet"
    df.to_csv(out.with_suffix(".csv"), index=False)

    per_gruppe = df.groupby("gruppe")["endret_pst"].sum().reindex(GRUPPER.keys()).fillna(0)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6), gridspec_kw={"width_ratios": [1, 1.6]})
    ax1.pie(per_gruppe, labels=per_gruppe.index, colors=[FARGER[g] for g in per_gruppe.index],
            autopct="%1.0f %%", startangle=90, wedgeprops={"edgecolor": "white"})
    ax1.set_title(f"Andel av samlet følsomhet (±{a.faktor:.0%} per parameter)")
    ax2.barh(df["parameter"], df["endret_pst"], color=[FARGER[g] for g in df["gruppe"]])
    for y, (lo, hi) in enumerate(zip(df["endret_pst_lav"], df["endret_pst_hoy"])):
        ax2.plot([lo, hi], [y, y], color="black", lw=1, marker="|")
    ax2.invert_yaxis()
    ax2.set_xlabel("timer med endret status (%), snitt av −/+; strek = hver retning")
    ax2.set_title(f"{crag.name}: {n} timer, {int(basis['wet'].sum())} våte/fuktige i basis "
                  f"({basis['wet'].mean():.0%}), {w.index[0]:%d.%m}–{w.index[-1]:%d.%m.%Y}")
    ax2.grid(axis="x", alpha=0.3)
    fig.tight_layout()
    fig.savefig(out.with_suffix(".png"), dpi=130)
    print(f"\nPer gruppe (sum av %-poeng): {per_gruppe.round(1).to_dict()}")
    print(f"Lagret -> {out}.png / .csv")


if __name__ == "__main__":
    main()
