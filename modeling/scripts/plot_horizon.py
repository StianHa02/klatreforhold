"""Plotter horisonten i en feltkonfig: flat kurve (asimut mot høyde) og polarplott med solbane.

  python scripts/plot_horizon.py                                  # Ekstraveggen
  python scripts/plot_horizon.py --config config/bymuren.yaml --dato 2026-10-30
"""
import argparse

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pvlib
from _common import DEFAULT_CONFIG, ROOT

from klatreforhold.config import load_config


def solbane(crag, dato):
    t = pd.date_range(f"{dato} 00:00", f"{dato} 23:59", freq="10min", tz=crag.timezone)
    sp = pvlib.location.Location(crag.lat, crag.lon, altitude=crag.elevation_m).get_solarposition(t)
    el = 90 - sp["apparent_zenith"].to_numpy()
    return t, sp["azimuth"].to_numpy(), el


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(DEFAULT_CONFIG))
    ap.add_argument("--dato", default=None, help="dato for solbane (YYYY-MM-DD); standard = i dag")
    a = ap.parse_args()
    crag, _ = load_config(a.config)
    dato = a.dato or pd.Timestamp.now(tz=crag.timezone).strftime("%Y-%m-%d")
    hz = np.array(crag.horizon, dtype=float)
    az, h = hz[:, 0], hz[:, 1]
    t, saz, sel = solbane(crag, dato)
    oppe = sel > 0

    fig = plt.figure(figsize=(15, 6))
    ax = fig.add_subplot(1, 2, 1)
    ax.fill_between(az, 0, h, color="#7a8a6a", alpha=0.6, label="terreng/trær (horisont)")
    ax.plot(az, h, color="#3b4a2a", lw=1)
    ax.plot(saz[oppe], sel[oppe], color="#e0a020", lw=2, label=f"solbane {dato}")
    for hh in range(0, 24, 2):
        m = (t.hour == hh) & (t.minute == 0) & oppe
        if m.any():
            ax.annotate(f"{hh:02d}", (saz[m][0], sel[m][0]), textcoords="offset points", xytext=(0, 6), ha="center", fontsize=8)
    ax.axvline(crag.face_azimuth_deg, color="#c0392b", ls="--", lw=1, label=f"veggen vender mot {crag.face_azimuth_deg:.0f}°")
    ax.set_xlim(0, 360); ax.set_ylim(0, max(70, h.max() + 5))
    ax.set_xticks(range(0, 361, 45)); ax.set_xticklabels(["N", "NØ", "Ø", "SØ", "S", "SV", "V", "NV", "N"])
    ax.set_xlabel("asimut (sann nord)"); ax.set_ylabel("høyde over horisontalplanet (°)")
    ax.set_title(f"{crag.name}: horisont fra veggfoten"); ax.grid(alpha=0.3); ax.legend(loc="upper right", fontsize=8)

    pax = fig.add_subplot(1, 2, 2, projection="polar")
    pax.set_theta_zero_location("N"); pax.set_theta_direction(-1)
    # radius = 90 - høyde: senit i midten, horisont ytterst
    pax.fill_between(np.deg2rad(az), 90 - h, 90, color="#7a8a6a", alpha=0.6)
    pax.plot(np.deg2rad(saz[oppe]), 90 - sel[oppe], color="#e0a020", lw=2)
    pax.plot([np.deg2rad(crag.face_azimuth_deg)] * 2, [0, 90], color="#c0392b", ls="--", lw=1)
    pax.set_rlim(0, 90); pax.set_rticks([0, 30, 60, 90]); pax.set_yticklabels(["90°", "60°", "30°", "0°"], fontsize=7)
    pax.set_title("sett ovenfra (senit i midten)", fontsize=10)

    out = ROOT / "outputs" / f"{crag.name.lower()}_horisont.png"
    fig.tight_layout(); fig.savefig(out, dpi=130)
    print(f"Lagret -> {out}")


if __name__ == "__main__":
    main()
