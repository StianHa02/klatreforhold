"""Vann- og energibalanse med flytende vann, is, snø og et frostlåst sigereservoar."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .forcing import prepare_weather, precipitation_phase
from .solar import SIGMA, dew_point_c, face_irradiance, saturation_vapour_pressure_hpa
from .wetness import DEFAULTS, CP_AIR, RHO_AIR, LV, RV, rh_correction, wind_driven_rain

LF = 334000.0  # J/kg, smeltevarme
LS = LV + LF
STORES = ("film", "holds", "ice_film", "ice_holds", "snow", "seep", "catchment_snow")


def _phase_change(s: dict, energy: float, capacity: float) -> tuple[float, float]:
    """Bruker tilgjengelig følbar varme én gang. Blanding av vann/is holdes ved 0 °C."""
    heat = capacity * s["Ts"] + energy
    liquid = s["film"] + s["holds"]
    frozen = melted = 0.0
    if heat < 0 and liquid > 0:
        frozen = min(liquid, -heat / LF)
        for water, ice in [("film", "ice_film"), ("holds", "ice_holds")]:
            amount = frozen * s[water] / liquid
            s[water] -= amount
            s[ice] += amount
        heat += frozen * LF
    elif heat > 0:
        remaining = heat / LF
        for solid, water in [("snow", "holds"), ("ice_film", "film"), ("ice_holds", "holds")]:
            amount = min(s[solid], remaining)
            s[solid] -= amount
            s[water] += amount
            remaining -= amount
            melted += amount
        heat -= melted * LF
    s["Ts"] = heat / capacity
    return frozen, melted


def _vapour_remove(s: dict, potential: float, keys: list[tuple[str, float]]) -> float:
    used = 0.0
    for key, efficiency in keys:
        amount = min(s[key], max(0.0, potential - used) * efficiency)
        s[key] -= amount
        used += amount
    return used


def run_balance(weather, crag, params=None, substeps=12, init_state=None) -> pd.DataFrame:
    p = {**DEFAULTS, **(params or {})}
    if substeps < 1 or int(substeps) != substeps:
        raise ValueError("substeps må være et positivt heltall")
    for key in ("rock_heat_capacity", "surface_layer_m", "conduction_depth_m", "seep_timescale_h", "deep_temp_timescale_h"):
        if p[key] <= 0:
            raise ValueError(f"{key} må være positiv")
    for key in ("film_capacity_mm", "holds_capacity_mm", "wind_exposure", "evaporation_efficiency"):
        if p[key] < 0:
            raise ValueError(f"{key} kan ikke være negativ")
    w = prepare_weather(weather)
    correction = rh_correction(w.index, p, crag.timezone)
    if "weather_source" in w:
        correction = np.where(w["weather_source"] == p.get("rh_correction_source", "openmeteo"), correction, 0)
    if "rh_malt" in w:
        correction = np.where(w["rh_malt"].fillna(False), 0, correction)
    w["relative_humidity"] = (w["relative_humidity"] + correction).clip(0, 100)
    rain, snowfall, phase_estimated = precipitation_phase(w)
    if not p["winter_enabled"]:
        rain, snowfall = w["precipitation"].to_numpy(), np.zeros(len(w))
    rad = face_irradiance(w, crag)
    ta = w["air_temperature"].to_numpy(float)
    rh = w["relative_humidity"].to_numpy(float)
    wind = w["wind_speed"].to_numpy(float)
    wd = w["wind_direction"].to_numpy(float)
    tilt = np.deg2rad(crag.face_tilt_deg)
    sheltered = p["rain_shelter_factor"] if crag.rain_sheltered else 1.0
    # Bratthet >90° skjermer tak/hyller og slagregn. Anslag, ikke garanti for regnsikkerhet.
    overhang = float(np.interp(crag.face_tilt_deg, [0, 90, 110, 135, 180], [1, 1, .2, .05, 0]))
    overhang = {3: .2, 4: .05}.get(crag.steepness_id, overhang)
    overhang = float(p.get("overhang_rain_factor", overhang))
    direct_fraction = min(1.0, p["direct_rain_fraction"] * overhang + max(float(np.cos(tilt)), 0))
    wdr = wind_driven_rain(rain, wind, wd, crag.face_azimuth_deg, p) * max(0.0, np.sin(tilt)) * sheltered * overhang
    direct_rain = rain * direct_fraction * sheltered
    runoff_input = rain * p["runoff_from_above"] * float(p.get("overhang_runoff_factor", overhang))
    rain_face = wdr + direct_rain + runoff_input
    # Snø på sva og hyller. Vindtransport av snø er ikke utledet fra regnets slagregnformel.
    snow_face = snowfall * direct_fraction * sheltered
    capacity = p["rock_heat_capacity"] * p["surface_layer_m"]
    kg = p["rock_conductivity"] / p["conduction_depth_m"]
    svf = float(rad["sky_view_factor"].iloc[0])
    shortwave = rad["sw_face"].to_numpy()
    longwave = rad["lw_sky"].to_numpy()
    s = {k: 0.0 for k in STORES}
    s.update(Ts=float(ta[0]), Tdeep=float(ta[0]))
    if init_state:
        s.update({k: float(v) for k, v in init_state.items() if k in s})
    if not all(np.isfinite(v) for v in s.values()) or any(s[k] < 0 for k in STORES):
        raise ValueError("Ugyldig starttilstand")
    columns = ["rock_temp", "deep_temp", "film_mm", "holds_mm", "seep_mm", "ice_mm", "snow_mm",
               "ice_film_mm", "ice_holds_mm", "catchment_snow_mm", "condensation_mm", "deposition_mm",
               "evaporation_mm", "sublimation_mm", "seep_flux_mm", "seep_drainage_mm", "runoff_mm",
               "evap_potential_mm", "freeze_mm", "melt_mm", "catchment_melt_mm", "catchment_input_mm",
               "mass_balance_error_mm", "energy_balance_error_j_m2"]
    out = {k: np.zeros(len(w)) for k in columns}
    for i in range(len(w)):
        # Kortere delsteg under frysing/tining gir mindre sprang i små vannlagre.
        near_freezing = ta[i] <= 2 or s["Ts"] <= 1 or s["snow"] + s["ice_film"] + s["ice_holds"] > 0
        steps = max(substeps, 24) if p["winter_enabled"] and near_freezing else substeps
        dt = 3600.0 / steps
        before = sum(s[k] for k in STORES)
        totals = {k: 0.0 for k in columns}
        hc = 5.7 + 3.8 * wind[i] * p["wind_exposure"]
        hm = hc / (RHO_AIR * CP_AIR)
        vapour_air = saturation_vapour_pressure_hpa(ta[i]) * rh[i] / 100 * 100 / (RV * (ta[i] + 273.15))
        lw_in = svf * longwave[i] + (1 - svf) * SIGMA * (ta[i] + 273.15)**4
        catchment_factor = p["seep_catchment_factor"] if p["seep_enabled"] else 0.0
        catchment_input = (rain[i] + snowfall[i]) * catchment_factor
        for _ in range(steps):
            s["film"] += rain_face[i] / steps
            s["snow"] += snow_face[i] / steps
            s["catchment_snow"] += snowfall[i] * catchment_factor / steps
            catchment_melt = min(s["catchment_snow"], max(0, ta[i]) * p["catchment_melt_mm_day_c"]
                                 / 24 / steps * catchment_factor)
            s["catchment_snow"] -= catchment_melt
            s["seep"] += rain[i] * catchment_factor / steps + catchment_melt
            totals["catchment_melt_mm"] += catchment_melt
            # Terskelen gir en kontinuerlig overgang. Resten av dreneringen går utenom veggen.
            drainage = s["seep"] * (1 - np.exp(-dt / (3600 * p["seep_timescale_h"])))
            if p["winter_enabled"] and s["Tdeep"] <= 0:
                drainage = 0.0
            share = max(0, s["seep"] - p["seep_threshold_mm"]) / max(s["seep"], 1e-12)
            seep_face = drainage * share
            s["seep"] -= drainage
            s["holds"] += seep_face
            totals["seep_flux_mm"] += seep_face
            totals["seep_drainage_mm"] += drainage - seep_face

            ts = s["Ts"]
            over_ice = p["winter_enabled"] and (ts < 0 or (s["film"] + s["holds"] < 1e-12 and s["snow"] + s["ice_film"] + s["ice_holds"] > 0))
            saturation = (6.1078 * np.exp(21.875 * ts / (265.5 + ts)) if over_ice
                          else saturation_vapour_pressure_hpa(ts))
            rho_surface = saturation * 100 / (RV * (ts + 273.15))
            potential = hm * (rho_surface - vapour_air) * dt
            latent_energy = 0.0
            if potential < 0:
                if over_ice:
                    s["ice_film"] -= potential
                    totals["deposition_mm"] -= potential
                    latent_energy = potential * LS
                else:
                    s["film"] -= potential
                    totals["condensation_mm"] -= potential
                    latent_energy = potential * LV
            else:
                potential *= p["evaporation_efficiency"]
                totals["evap_potential_mm"] += potential
                if over_ice:
                    removed = _vapour_remove(s, potential, [("snow", 1), ("ice_film", 1), ("ice_holds", p["holds_drying_factor"])])
                    totals["sublimation_mm"] += removed
                    latent_energy = removed * LS
                else:
                    removed = _vapour_remove(s, potential, [("film", 1), ("holds", p["holds_drying_factor"])])
                    totals["evaporation_mm"] += removed
                    latent_energy = removed * LV
            # Snøens lysere flate vektes etter dekning; 1 mm vannekvivalent dekker referanseflaten.
            cover = min(1.0, s["snow"] / p["snow_full_cover_mm"])
            albedo = p["albedo"] * (1 - cover) + p["snow_albedo"] * cover
            energy = ((1 - albedo) * shortwave[i]
                      + p["emissivity"] * (lw_in - SIGMA * (ts + 273.15)**4)
                      - hc * (ts - ta[i]) - kg * (ts - s["Tdeep"])) * dt - latent_energy
            frozen = melted = 0.0
            if p["winter_enabled"]:
                frozen, melted = _phase_change(s, energy, capacity)
            else:
                s["Ts"] += energy / capacity
            totals["freeze_mm"] += frozen
            totals["melt_mm"] += melted
            totals["energy_balance_error_j_m2"] += capacity * (s["Ts"] - ts) + LF * (melted - frozen) - energy
            overflow = max(0.0, s["film"] - p["film_capacity_mm"])
            s["film"] -= overflow
            s["holds"] += overflow * p["film_to_holds_rate"]
            runoff = overflow * (1 - p["film_to_holds_rate"])
            excess = max(0.0, s["holds"] - p["holds_capacity_mm"])
            s["holds"] -= excess
            totals["runoff_mm"] += runoff + excess
        s["Tdeep"] += (1 - np.exp(-1 / p["deep_temp_timescale_h"])) * (ta[i] - s["Tdeep"])
        if not all(np.isfinite(v) for v in s.values()) or abs(s["Ts"]) > 150:
            raise ValueError("Ustabil energibalanse; kontroller vær/parametre eller øk substeps")
        flux_in = rain_face[i] + snow_face[i] + catchment_input + totals["condensation_mm"] + totals["deposition_mm"]
        flux_out = totals["evaporation_mm"] + totals["sublimation_mm"] + totals["runoff_mm"] + totals["seep_drainage_mm"]
        totals["mass_balance_error_mm"] = sum(s[k] for k in STORES) - before - flux_in + flux_out
        totals["catchment_input_mm"] = catchment_input
        for key in columns:
            out[key][i] = totals[key]
        for key in STORES:
            out[key + "_mm"][i] = s[key]
        out["ice_mm"][i] = s["ice_film"] + s["ice_holds"]
        out["rock_temp"][i], out["deep_temp"][i] = s["Ts"], s["Tdeep"]
    res = pd.DataFrame(out, index=w.index)
    res["rain_on_face_mm"], res["wind_driven_rain_mm"] = rain_face, wdr
    res["direct_rain_mm"], res["runoff_input_mm"] = direct_rain, runoff_input
    res["snow_on_face_mm"], res["snowfall_mm"] = snow_face, snowfall
    res["phase_estimated"] = phase_estimated
    res["rh_brukt"] = rh
    res["dew_point"] = dew_point_c(ta, rh)
    res["rock_minus_dewpoint"] = res["rock_temp"] - res["dew_point"]
    res = res.join(rad[["sw_face", "sw_face_direct", "sw_face_diffuse", "sw_face_reflected", "sky_view_factor",
                        "sun_on_face", "sun_possible", "sun_elevation", "cloud_cover_used"]])
    res["water_mm"] = res["film_mm"] + res["holds_mm"]
    res["status"] = np.where(res["water_mm"] >= p["wet_threshold_mm"], "vatt",
                            np.where(res["water_mm"] >= p["damp_threshold_mm"], "fuktig", "tort"))
    res.loc[res["ice_mm"] + res["snow_mm"] >= p["ice_threshold_mm"], "status"] = "is"
    res["wet"] = res["status"] != "tort"
    res.attrs["final_state"] = s.copy()
    res.attrs["initial_state_uncertain"] = init_state is None
    return res


def state_at(result: pd.DataFrame, timestamp) -> dict:
    row = result.loc[timestamp]
    return {**{k: float(row[k + "_mm"]) for k in STORES},
            "Ts": float(row["rock_temp"]), "Tdeep": float(row["deep_temp"])}
