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

Luftfuktighet: MET Nordic er for fuktig på ettermiddagen vår og sommer og litt for tørr om natta vinterstid,
sammenlignet med målestasjoner (se scripts/verify_forecast.py). rh_correction() retter dette før
energibalansen, med en verdi per måned og en døgnsvingning. Timer som er
målt (kolonnen rh_malt, satt når Frost-målinger erstatter historikken) korrigeres ikke.

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
    rh_korreksjon=0.0, rh_korreksjon_maned=None, rh_korreksjon_doegn_cos=None, rh_korreksjon_doegn_sin=None,
    rh_korreksjon_styrke=1.0,
    rh_correction_source="openmeteo", evaporation_efficiency=1.0,
    winter_enabled=True, rain_shelter_factor=0.1, ice_threshold_mm=0.01,
    snow_albedo=0.6, snow_full_cover_mm=1.0, catchment_melt_mm_day_c=3.0,
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


def rh_correction(index: pd.DatetimeIndex, p: dict, timezone: str = "Europe/Oslo") -> np.ndarray:
    """Prosentpoeng som legges til modellens luftfuktighet, time for time.

    rh_korreksjon_maned: 12 verdier (midten av hver måned, interpolert langs året så det ikke blir hopp).
    rh_korreksjon_doegn_cos/_sin: valgfri døgnsvingning per måned, b cos(2 pi t/24) + c sin(2 pi t/24),
    t = lokal klokketime. rh_korreksjon_styrke skalerer alt (1 = som målt mot stasjonen).
    """
    styrke = float(p.get("rh_korreksjon_styrke", 1.0))
    m = p.get("rh_korreksjon_maned")
    if m is None or len(m) != 12:
        return np.full(len(index), styrke * float(p.get("rh_korreksjon") or 0.0))
    local = index.tz_convert(timezone) if index.tz is not None else index
    dager = np.where(local.is_leap_year, 366.0, 365.0)
    mnd = 12 * (local.dayofyear.to_numpy() - 1 + local.hour.to_numpy() / 24.0) / dager  # 0-12 gjennom året
    mid = np.arange(12) + 0.5
    x = np.concatenate([mid - 12, mid, mid + 12])

    def langs_aaret(v):
        return np.interp(mnd, x, np.tile(np.asarray(v, dtype=float), 3))

    out = langs_aaret(m)
    b, c = p.get("rh_korreksjon_doegn_cos"), p.get("rh_korreksjon_doegn_sin")
    if b is not None and c is not None and len(b) == 12 and len(c) == 12:
        t = 2 * np.pi * local.hour.to_numpy() / 24.0
        out = out + langs_aaret(b) * np.cos(t) + langs_aaret(c) * np.sin(t)
    return styrke * out


def run_model(weather: pd.DataFrame, crag: Crag, params: dict | None = None,
              substeps: int = 12, init_state: dict | None = None) -> pd.DataFrame:
    """Timeverdier i UTC. Nedbør og stråling gjelder timen før tidsstempelet."""
    from .balance import run_balance
    return run_balance(weather, crag, params, substeps, init_state)

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
