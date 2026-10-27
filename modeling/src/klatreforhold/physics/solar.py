"""Sol og stråling på veggflaten.

Tar timesverdier for globalstråling (GHI) hvis vi har det, ellers beregnes klarværsstråling
og skaleres ned med skydekke. Deretter: dekomponering (Erbs) og transponering til en
vertikal flate med gitt asimut (isotropisk himmel), med horisontmaske for direktestråling.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pvlib

from ..config import Crag

SIGMA = 5.670374419e-8


def horizon_elevation(crag: Crag, sun_azimuth: np.ndarray) -> np.ndarray:
    """Interpolerer horisonthøyde (grader) i solas asimut fra horisontprofilen i konfigen."""
    h = np.asarray(crag.horizon, dtype=float)
    h = h[np.argsort(h[:, 0])]
    return np.interp(np.mod(sun_azimuth, 360.0), h[:, 0], h[:, 1])


def estimate_cloud_cover(df: pd.DataFrame) -> pd.Series:
    """Grovt skydekke-anslag (0-1) når vi bare har stasjonsdata uten stråling/skyer.

    Brukes bare som nødløsning for stasjonsdata. Bruk ekte skydekke/stråling fra MET Nordic når mulig.
    """
    rh = df["relative_humidity"].clip(0, 100)
    c = ((rh - 55.0) / 40.0).clip(0, 1)
    c = c.where(df["precipitation"] <= 0, 1.0)
    return c.rolling(3, min_periods=1, center=True).mean()


def face_irradiance(df: pd.DataFrame, crag: Crag) -> pd.DataFrame:
    """Returnerer stråling på veggen.

    Kolonner: sun_elevation, sun_azimuth, ghi, sw_face (W/m2 totalt på flaten),
    sw_face_direct, sun_on_face (bool), lw_sky (W/m2, langbølget fra himmelen).
    """
    times = df.index
    loc = pvlib.location.Location(crag.lat, crag.lon, tz="UTC", altitude=crag.elevation_m)
    # Timesverdier gjelder vanligvis timen som slutter ved tidsstempelet: bruk midtpunktet
    mid = times - pd.Timedelta(minutes=30)
    sp = loc.get_solarposition(mid)
    zen = sp["apparent_zenith"].to_numpy()
    azi = sp["azimuth"].to_numpy()
    elev = 90.0 - zen

    cloud = df["cloud_cover"] if "cloud_cover" in df else estimate_cloud_cover(df)
    cloud = cloud.clip(0, 1).fillna(0.5)

    if "ghi" in df and df["ghi"].notna().any():
        ghi = df["ghi"].clip(lower=0).fillna(0.0)
    else:
        cs = loc.get_clearsky(mid, model="ineichen")
        ghi_cs = cs["ghi"].to_numpy()
        # Kasten & Czeplak (1980)
        ghi = pd.Series(ghi_cs * (1.0 - 0.75 * cloud.to_numpy() ** 3.4), index=times)

    dni_extra = pvlib.irradiance.get_extra_radiation(mid).to_numpy()
    if {"dni", "dhi"}.issubset(df.columns) and df["dni"].notna().any():
        dni = df["dni"].clip(lower=0).fillna(0).to_numpy()
        dhi = df["dhi"].clip(lower=0).fillna(0).to_numpy()
    else:
        erbs = pvlib.irradiance.erbs(ghi.to_numpy(), zen, mid)
        dni = np.nan_to_num(erbs["dni"].to_numpy())
        dhi = np.nan_to_num(erbs["dhi"].to_numpy())

    # Direktestråling bare når sola er over horisonten i den retningen
    hz = horizon_elevation(crag, azi)
    sun_visible = elev > hz
    dni_eff = np.where(sun_visible, dni, 0.0)

    poa = pvlib.irradiance.get_total_irradiance(
        surface_tilt=crag.face_tilt_deg,
        surface_azimuth=crag.face_azimuth_deg,
        solar_zenith=zen,
        solar_azimuth=azi,
        dni=dni_eff,
        ghi=ghi.to_numpy(),
        dhi=dhi,
        dni_extra=dni_extra,
        model="isotropic",
        albedo=0.15,
    )
    aoi = pvlib.irradiance.aoi(crag.face_tilt_deg, crag.face_azimuth_deg, zen, azi)
    direct = np.nan_to_num(np.asarray(poa["poa_direct"], dtype=float))
    sun_on_face = sun_visible & (np.asarray(aoi) < 90.0) & (dni_eff > 20.0)

    # Langbølget fra himmelen: bruk data hvis vi har det, ellers Brutsaert + skykorreksjon
    if "longwave_down" in df and df["longwave_down"].notna().any():
        lw_sky = df["longwave_down"].to_numpy()
    else:
        ta_k = df["air_temperature"].to_numpy() + 273.15
        e_hpa = vapour_pressure_hpa(df["air_temperature"].to_numpy(), df["relative_humidity"].to_numpy())
        eps0 = 1.24 * (e_hpa / ta_k) ** (1.0 / 7.0)
        c = cloud.to_numpy()
        eps = eps0 * (1 - c) + c * 0.98
        lw_sky = eps * SIGMA * ta_k ** 4

    return pd.DataFrame(
        {
            "sun_elevation": elev,
            "sun_azimuth": azi,
            "ghi": ghi.to_numpy(),
            "sw_face": np.nan_to_num(np.asarray(poa["poa_global"], dtype=float)),
            "sw_face_direct": direct,
            "sun_on_face": sun_on_face,
            "cloud_cover_used": cloud.to_numpy(),
            "lw_sky": lw_sky,
        },
        index=times,
    )


def saturation_vapour_pressure_hpa(t_c: np.ndarray) -> np.ndarray:
    """Magnus-formel over vann (hPa)."""
    t_c = np.asarray(t_c, dtype=float)
    return 6.112 * np.exp(17.62 * t_c / (243.12 + t_c))


def vapour_pressure_hpa(t_c, rh) -> np.ndarray:
    return saturation_vapour_pressure_hpa(t_c) * np.clip(np.asarray(rh, dtype=float), 0, 100) / 100.0


def dew_point_c(t_c, rh) -> np.ndarray:
    e = np.maximum(vapour_pressure_hpa(t_c, rh), 1e-3)
    g = np.log(e / 6.112)
    return 243.12 * g / (17.62 - g)
