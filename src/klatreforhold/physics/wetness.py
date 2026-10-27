"""Fysisk modell for vann på bergflaten (time for time).

Ideen er den samme som i vegvær-modeller (METRo) og bladfukt-modeller: en energibalanse
for overflaten gir bergtemperaturen, og en "bøtte"-vannbalanse holder styr på vannet.

Vannlagre (mm = liter per m2):
  film   - tynn vannfilm på flaten. Fylles av regn som treffer veggen og av kondens,
           tømmes av fordampning og avrenning. Styrer "er det vått å ta på".
  holds  - vann i tak, sprekker og hyller. Fylles av overløp fra filmen og av siging,
           tørker saktere. Styrer "fuktige tak etter regn".
  seep   - sakte reservoar (jord/sprekker over veggen) matet av nedbør. Gir siging dager etter.

Energibalanse for et tynt berglag (temperatur Ts):
  C dTs/dt = (1-albedo)*SW_face + eps*(LW_inn - sigma*Ts^4) - h_c*(Ts-Ta) - k/d*(Ts-T_dyp) - L*E
der h_c = 5.7 + 3.8*U (McAdams), og fordampning/kondens E følger av Lewis-relasjonen:
  E = h_c/(rho*cp) * (rho_v,sat(Ts) - rho_v,luft).  E < 0 betyr kondens (dugg/"svett" berg).

Regn på vertikal vegg (ISO 15927-3, semi-empirisk):
  R_vegg = 2/9 * U * R_h^(8/9) * cos(D - theta)   når vinden blåser mot veggen.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..config import Crag
from .solar import SIGMA, dew_point_c, face_irradiance, saturation_vapour_pressure_hpa

RV = 461.5        # J/kg/K, gasskonstant vanndamp
RHO_AIR = 1.225   # kg/m3
CP_AIR = 1005.0   # J/kg/K
LV = 2.45e6       # J/kg, fordampningsvarme

DEFAULTS = dict(
    wdr_coefficient=0.222, wdr_exponent=0.889, wind_exposure=0.6,
    direct_rain_fraction=0.10, runoff_from_above=0.05,
    film_capacity_mm=0.3, holds_capacity_mm=1.5, film_to_holds_rate=0.3, holds_drying_factor=0.25,
    seep_enabled=True, seep_catchment_factor=0.02, seep_timescale_h=72.0, seep_threshold_mm=0.5,
    albedo=0.30, emissivity=0.95, surface_layer_m=0.05, rock_heat_capacity=2.2e6,
    rock_conductivity=2.5, conduction_depth_m=0.25, deep_temp_timescale_h=120.0, sky_view_factor=0.5,
    wet_threshold_mm=0.05, damp_threshold_mm=0.01,
)

REQUIRED = ["air_temperature", "relative_humidity", "precipitation", "wind_speed", "wind_direction"]


def _rho_v(e_hpa, t_c):
    return e_hpa * 100.0 / (RV * (t_c + 273.15))


def wind_driven_rain(precip, wind_speed, wind_dir, face_azimuth, p) -> np.ndarray:
    """Regn som treffer en vertikal vegg (mm/t), ISO 15927-3-formen."""
    cosang = np.cos(np.deg2rad(np.asarray(wind_dir) - face_azimuth))
    u = np.asarray(wind_speed) * p["wind_exposure"]
    r = np.clip(np.asarray(precip, dtype=float), 0, None)
    return p["wdr_coefficient"] * u * r ** p["wdr_exponent"] * np.clip(cosang, 0, None)


def run_model(weather: pd.DataFrame, crag: Crag, params: dict | None = None,
              substeps: int = 12, init_state: dict | None = None) -> pd.DataFrame:
    """Kjører modellen på en timesserie.

    weather: indeks = tidsstempler (UTC, tz-aware), timesverdier. Påkrevde kolonner:
      air_temperature (C), relative_humidity (%), precipitation (mm siste time),
      wind_speed (m/s, 10 m), wind_direction (grader, retningen vinden kommer FRA).
    Valgfrie: ghi, dni, dhi (W/m2), cloud_cover (0-1), longwave_down (W/m2).
    """
    p = {**DEFAULTS, **(params or {})}
    missing = [c for c in REQUIRED if c not in weather]
    if missing:
        raise ValueError(f"Mangler kolonner: {missing}")
    w = weather.sort_index().copy()
    w[REQUIRED] = w[REQUIRED].interpolate(limit=3).ffill().bfill()
    w["precipitation"] = w["precipitation"].fillna(0).clip(lower=0)

    rad = face_irradiance(w, crag)
    ta = w["air_temperature"].to_numpy(float)
    rh = w["relative_humidity"].to_numpy(float)
    pr = w["precipitation"].to_numpy(float)
    u10 = w["wind_speed"].to_numpy(float)
    wd = w["wind_direction"].to_numpy(float)
    sw = rad["sw_face"].to_numpy(float)
    lw_sky = rad["lw_sky"].to_numpy(float)

    # Helning: 90 = vertikal vegg, lavere = sva. På sva treffer vanlig regn rett på (cos(helning) av
    # horisontal nedbør per m2 flate), mens slagregnet fra siden blir mindre (sin(helning)).
    tilt = np.deg2rad(crag.face_tilt_deg)
    wdr = wind_driven_rain(pr, u10, wd, crag.face_azimuth_deg, p) * np.sin(tilt)
    if crag.rain_sheltered:
        wdr = wdr * 0.1
    direct = p["direct_rain_fraction"] + max(float(np.cos(tilt)), 0.0)
    rain_face = wdr + (direct + p["runoff_from_above"]) * pr

    n = len(w)
    dt = 3600.0 / substeps
    C = p["rock_heat_capacity"] * p["surface_layer_m"]
    k_g = p["rock_conductivity"] / p["conduction_depth_m"]
    svf = p["sky_view_factor"]
    eps = p["emissivity"]
    alpha_deep = 1.0 / p["deep_temp_timescale_h"]

    s = dict(Ts=ta[0], Tdeep=np.nanmean(ta[: min(n, 72)]), film=0.0, holds=0.0, seep=0.0)
    if init_state:
        s.update(init_state)

    out = {k: np.zeros(n) for k in
           ["rock_temp", "deep_temp", "film_mm", "holds_mm", "seep_mm", "condensation_mm",
            "evaporation_mm", "seep_flux_mm", "evap_potential_mm"]}

    for i in range(n):
        Ta, RH, U = ta[i], rh[i], max(u10[i], 0.0)
        U_loc = U * p["wind_exposure"]
        h_c = 5.7 + 3.8 * U_loc
        h_m = h_c / (RHO_AIR * CP_AIR)  # m/s (Lewis, Le ~ 1)
        e_a = saturation_vapour_pressure_hpa(Ta) * min(max(RH, 0), 100) / 100.0
        rho_va = _rho_v(e_a, Ta)
        lw_in = svf * lw_sky[i] + (1 - svf) * SIGMA * (Ta + 273.15) ** 4  # terreng ~ lufttemp

        # Vanntilførsel denne timen, fordelt jevnt på deltrinn
        rain_step = rain_face[i] / substeps
        seep_flux = 0.0
        if p["seep_enabled"]:
            s["seep"] += p["seep_catchment_factor"] * pr[i]
            out_flow = s["seep"] / p["seep_timescale_h"]
            s["seep"] -= out_flow
            seep_flux = out_flow if s["seep"] > p["seep_threshold_mm"] else 0.0
        seep_step = seep_flux / substeps

        cond_h = evap_h = evap_pot_h = 0.0
        for _ in range(substeps):
            Ts = s["Ts"]
            rho_vs = _rho_v(saturation_vapour_pressure_hpa(Ts), Ts)
            flux = h_m * (rho_vs - rho_va)            # kg/m2/s, >0 fordamping
            pot = flux * dt                             # mm (kg/m2) per deltrinn
            latent = 0.0
            # vann inn
            s["film"] += rain_step
            s["holds"] += seep_step
            if pot < 0:  # kondens
                s["film"] += -pot
                cond_h += -pot
                latent = flux * LV  # negativ = varme tilført
            else:
                evap_pot_h += pot
                e1 = min(s["film"], pot)
                s["film"] -= e1
                rest = (pot - e1) * p["holds_drying_factor"]
                e2 = min(s["holds"], rest)
                s["holds"] -= e2
                evap_h += e1 + e2
                latent = (e1 + e2) / dt * LV
            # overløp fra film til tak/sprekker, resten renner av
            if s["film"] > p["film_capacity_mm"]:
                over = s["film"] - p["film_capacity_mm"]
                s["film"] = p["film_capacity_mm"]
                s["holds"] += p["film_to_holds_rate"] * over
            s["holds"] = min(s["holds"], p["holds_capacity_mm"])
            # energibalanse (eksplisitt Euler)
            q = ((1 - p["albedo"]) * sw[i]
                 + eps * (lw_in - SIGMA * (Ts + 273.15) ** 4)
                 - h_c * (Ts - Ta)
                 - k_g * (Ts - s["Tdeep"])
                 - latent)
            s["Ts"] = Ts + q * dt / C
        s["Tdeep"] += alpha_deep * (Ta - s["Tdeep"])

        out["rock_temp"][i] = s["Ts"]
        out["deep_temp"][i] = s["Tdeep"]
        out["film_mm"][i] = s["film"]
        out["holds_mm"][i] = s["holds"]
        out["seep_mm"][i] = s["seep"]
        out["condensation_mm"][i] = cond_h
        out["evaporation_mm"][i] = evap_h
        out["evap_potential_mm"][i] = evap_pot_h
        out["seep_flux_mm"][i] = seep_flux

    res = pd.DataFrame(out, index=w.index)
    res["rain_on_face_mm"] = rain_face
    res["wind_driven_rain_mm"] = wdr
    res["dew_point"] = dew_point_c(ta, rh)
    res["rock_minus_dewpoint"] = res["rock_temp"] - res["dew_point"]
    res = res.join(rad[["sw_face", "sun_on_face", "sun_elevation", "cloud_cover_used"]])

    water = res["film_mm"] + res["holds_mm"]
    res["water_mm"] = water
    status = np.where(water >= p["wet_threshold_mm"], "vatt",
                      np.where(water >= p["damp_threshold_mm"], "fuktig", "tort"))
    # Is/rim: vann på berg under 0 °C
    status = np.where((status != "tort") & (res["rock_temp"].to_numpy() < 0.0), "is", status)
    res["status"] = status
    res["wet"] = res["status"] != "tort"
    return res


def hours_until_dry(result: pd.DataFrame) -> pd.Series:
    """For hvert tidspunkt: antall timer til modellen sier tørt (0 hvis tørt nå, NaN hvis ikke innen serien)."""
    dry = (~result["wet"]).to_numpy()
    n = len(dry)
    out = np.full(n, np.nan)
    next_dry = None
    for i in range(n - 1, -1, -1):
        if dry[i]:
            next_dry = i
        if next_dry is not None:
            out[i] = next_dry - i
    return pd.Series(out, index=result.index, name="hours_until_dry")
