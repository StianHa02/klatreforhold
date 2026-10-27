"""Beregner horisontprofil (og himmelsynsfaktor) for veggen fra Kartverkets høydemodell.

1. Last ned DOM1 (overflatemodell, med trær og bygg) som GeoTIFF fra https://hoydedata.no
   for et område på ~2-3 km rundt feltet (lisens CC BY 4.0, kreditér Kartverket).
2. python scripts/horizon_from_dem.py --dem data/raw/dom1_bones.tif
3. Lim inn 'horizon'-lista som skrives ut i config/ekstraveggen.yaml, og bruk sky_view_factor.

Krever: pip install rasterio pyproj
"""
import argparse

import numpy as np
from _common import DEFAULT_CONFIG

from klatreforhold.config import load_config


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(DEFAULT_CONFIG))
    ap.add_argument("--dem", required=True, help="GeoTIFF med DOM1/DTM1")
    ap.add_argument("--offset-m", type=float, default=3.0, help="observatør så mange meter ut fra veggen")
    ap.add_argument("--eye-height-m", type=float, default=1.5)
    ap.add_argument("--max-dist-m", type=float, default=3000)
    ap.add_argument("--step-deg", type=float, default=2.0)
    a = ap.parse_args()

    import rasterio
    from pyproj import Transformer

    crag, _ = load_config(a.config)
    with rasterio.open(a.dem) as ds:
        z = ds.read(1).astype(float)
        if ds.nodata is not None:
            z[z == ds.nodata] = np.nan
        tr = Transformer.from_crs("EPSG:4326", ds.crs, always_xy=True)
        x0, y0 = tr.transform(crag.lon, crag.lat)
        az = np.deg2rad(crag.face_azimuth_deg)
        x0 += a.offset_m * np.sin(az)
        y0 += a.offset_m * np.cos(az)
        res = abs(ds.transform.a)
        inv = ~ds.transform

        def height(x, y):
            c, r = inv * (x, y)
            r, c = int(r), int(c)
            if 0 <= r < z.shape[0] and 0 <= c < z.shape[1]:
                return z[r, c]
            return np.nan

        zg = height(x0, y0)
        zobs = zg + a.eye_height_m
        dists = np.arange(res, a.max_dist_m, res)
        profile = []
        for azd in np.arange(0, 360, a.step_deg):
            # bak veggen: veggen selv blokkerer
            rel = (azd - crag.face_azimuth_deg + 180) % 360 - 180
            if abs(rel) >= 90:
                profile.append((azd, 90.0))
                continue
            th = np.deg2rad(azd)
            xs, ys = x0 + dists * np.sin(th), y0 + dists * np.cos(th)
            hs = np.array([height(x, y) for x, y in zip(xs, ys)])
            ang = np.degrees(np.arctan2(hs - zobs, dists))
            profile.append((azd, float(np.nanmax(np.r_[ang, 0.0]))))

    prof = np.array(profile)
    # himmelsynsfaktor for vertikal flate: integral over halvkula foran veggen
    front = prof[np.abs((prof[:, 0] - crag.face_azimuth_deg + 180) % 360 - 180) < 90]
    rel = np.deg2rad((front[:, 0] - crag.face_azimuth_deg + 180) % 360 - 180)
    h = np.deg2rad(front[:, 1])
    dphi = np.deg2rad(a.step_deg)
    svf = float(np.sum(np.cos(rel) * (np.pi / 2 - h - np.sin(h) * np.cos(h)) / 2) * dphi / np.pi)
    print(f"Bakkehøyde ved observatør: {zg:.1f} m")
    print("horizon:")
    for azd, el in prof:
        print(f"  - [{azd:.0f}, {el:.1f}]")
    print("  - [360, %.1f]" % prof[0, 1])
    print(f"sky_view_factor: {svf:.2f}   (flat terreng gir 0.50)")


if __name__ == "__main__":
    main()
