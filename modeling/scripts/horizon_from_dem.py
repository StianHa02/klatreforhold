"""Regenerer horisont fra DOM/DTM. --write oppdaterer bare valgt feltkonfig.

Kartverket DTM gir bakkehøyden; DOM inkluderer trær og bygg langs synsstrålene.
Sann nord beregnes geodetisk, uavhengig av rasterets koordinatsystem.
"""
import argparse
from dataclasses import replace
from pathlib import Path
import re
from _common import DEFAULT_CONFIG
from klatreforhold.config import load_config
from klatreforhold.physics.terrain import terrain_horizon
from klatreforhold.physics.solar import sky_view_factor


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(DEFAULT_CONFIG))
    ap.add_argument("--dem", required=True)
    ap.add_argument("--ground-elevation", type=float, help="DTM-høyde ved veggpunktet; ellers fra konfig")
    ap.add_argument("--eye-height-m", type=float, default=1.5)
    ap.add_argument("--offset-m", type=float, default=3)
    ap.add_argument("--step-deg", type=float, default=5)
    ap.add_argument("--min-dist-m", type=float, default=10)
    ap.add_argument("--max-dist-m", type=float, default=3000)
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    crag, _ = load_config(a.config)
    ground = a.ground_elevation if a.ground_elevation is not None else crag.elevation_m
    horizon = terrain_horizon(crag, a.dem, ground, a.eye_height_m, a.offset_m, a.step_deg, a.min_dist_m, a.max_dist_m)
    svf = sky_view_factor(replace(crag, horizon=horizon))
    block = "  horizon:\n" + "".join(f"    - [{az:g}, {el:.2f}]\n" for az, el in horizon)
    print(block + f"sky_view_factor: {svf:.4f}")
    if a.write:
        path = Path(a.config)
        text = path.read_text(encoding="utf-8")
        text, n = re.subn(r"(?m)^  horizon:\n(?:    - .*\n)+", block, text)
        if n != 1:
            raise ValueError("Fant ikke én horisont å oppdatere")
        text = re.sub(r"(?m)^  sky_view_factor:.*$", f"  sky_view_factor: {svf:.4f}  # kontrollverdi; beregnes fra horisont og helning", text)
        path.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
