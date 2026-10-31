"""Kan Bønes værstasjon brukes av klatreforhold? Sammenligner stasjonen med MET Nordic-historikken.

Bønes værstasjon (Davis Vantage Pro2 Plus, weather.kippenbroeck.no) står ca. 1,3 km fra Ekstraveggen.
Stasjonen har et API med bare siste måling, så historikken leses fra en kopi av weewx-databasen:

  python scripts/evaluer_bones.py --db ~/Desktop/weewx-2026-10-31.sdb
  python scripts/evaluer_bones.py --db weewx.sdb --start 2023-01-01 --slutt 2026-10-30

Databasen åpnes skrivebeskyttet og har US-enheter. Hver rad er slutten av et 5-minuttsintervall, så timen
som slutter kl. T er radene i (T-1t, T], samme regel som modellen (nedbør gjelder timen før tidsstempelet).
Timer med færre enn 10 av 12 rader regnes som manglende, og nedbør fylles aldri med null.
MET Nordic hentes fra Open-Meteo og lagres i data/raw, som verify_forecast.py --historikk. Med FROST_CLIENT_ID
sammenlignes stasjonen også direkte med Florida (SN50540). Data:
Bønes værstasjon, weather.kippenbroeck.no (CC BY 4.0).
"""
import argparse
import os
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
from _common import ROOT
from verify_forecast import _cached, _crag_weather, _show

from klatreforhold.predict import load_crag
from klatreforhold.verify import (MANEDER, TZ, rain_windows, rain_windows_by, rh_bias_table, rh_quantiles, scores,
                                  scores_by, to_obs_frame)

NAVN = "Bønes"
LAT, LON = 60.326413, 5.295834
API = "https://weather.kippenbroeck.no/api/naa.php"
FELT = ["ekstraveggen", "loddefjord"]
MIN_RADER = 10  # av 12 femminuttsrader per time
REGN_MM = 0.2
RAW = ROOT / "data" / "raw"


def les_db(db, start, slutt) -> pd.DataFrame:
    """Femminuttsrader i metriske enheter, indeksert på slutten av intervallet (UTC)."""
    s, e = pd.Timestamp(start, tz=TZ), pd.Timestamp(slutt, tz=TZ) + pd.Timedelta(days=1)
    con = sqlite3.connect(f"file:{Path(db).expanduser()}?mode=ro", uri=True)
    try:
        df = pd.read_sql_query(
            "SELECT dateTime, usUnits, outTemp, outHumidity, windSpeed, windDir, rain FROM archive "
            "WHERE dateTime > ? AND dateTime <= ? ORDER BY dateTime",
            con, params=(int(s.timestamp()), int(e.timestamp())))
    finally:
        con.close()
    if (df["usUnits"] != 1).any():
        raise SystemExit("Forventet bare US-enheter (usUnits = 1) i databasen")
    out = pd.DataFrame({
        "air_temperature": (df["outTemp"] - 32) * 5 / 9,
        "relative_humidity": df["outHumidity"],
        "wind_speed": df["windSpeed"] * 0.44704,
        "wind_direction": df["windDir"],
        "precipitation": df["rain"] * 25.4,
    })
    out.index = pd.to_datetime(df["dateTime"], unit="s", utc=True).rename("time")
    return out


def til_timer(rader: pd.DataFrame) -> pd.DataFrame:
    """Timeverdier: timen som slutter kl. T er radene i (T-1t, T]. Snitt, men regn summeres og vind er en vektor."""
    r = rader.copy()
    rad = np.deg2rad(r["wind_direction"])
    r["u"] = r["wind_speed"] * np.sin(rad)  # vektet med fart, så stille rader ikke trekker retningen
    r["v"] = r["wind_speed"] * np.cos(rad)
    g = r.groupby(r.index.ceil("h").rename("time"))
    t = pd.DataFrame({
        "air_temperature": g["air_temperature"].mean(),
        "relative_humidity": g["relative_humidity"].mean(),
        "wind_speed": g["wind_speed"].mean(),
        "precipitation": g["precipitation"].sum(min_count=1),
        "rader": g.size(),
    })
    u, v = g["u"].sum(min_count=1), g["v"].sum(min_count=1)
    t["wind_direction"] = np.where((u ** 2 + v ** 2) > 0, np.mod(np.rad2deg(np.arctan2(u, v)), 360), np.nan)
    t = t.asfreq("1h")
    t["rader"] = t["rader"].fillna(0).astype(int)
    t.loc[t["rader"] < MIN_RADER, ["air_temperature", "relative_humidity", "wind_speed", "precipitation",
                                    "wind_direction"]] = np.nan
    return t


def kontroll_mot_dokumentasjon(db):
    """Tall fra weather.kippenbroeck.no/database.md. Stemmer de, er enheter og døgngrenser lest riktig."""
    jan = les_db(db, "2026-01-01", "2026-01-31")
    aar = les_db(db, "2020-01-01", "2020-12-31")
    con = sqlite3.connect(f"file:{Path(db).expanduser()}?mode=ro", uri=True)
    try:
        rate, tid = con.execute("SELECT rainRate, dateTime FROM archive WHERE dateTime NOT IN (1601717100, 1601717400) "
                                "ORDER BY rainRate DESC LIMIT 1").fetchone()
    finally:
        con.close()
    return pd.DataFrame([
        {"tall": "snittemperatur jan 2026 (°C)", "beregnet": round(jan["air_temperature"].mean(), 2), "dokumentert": -1.33},
        {"tall": "nedbør 2020 (mm)", "beregnet": round(aar["precipitation"].sum()), "dokumentert": "ca. 2179"},
        {"tall": "høyeste regnintensitet (mm/t)", "beregnet": round(rate * 25.4, 1), "dokumentert": 215.1},
        {"tall": "tidspunkt for den", "beregnet": pd.Timestamp(tid, unit="s", tz="UTC").tz_convert(TZ).strftime("%d.%m.%Y %H:%M"),
         "dokumentert": "26.08.2023 16:30"},
    ])


def sjekk_api(db) -> pd.DataFrame:
    """Siste måling fra API-et mot samme femminuttsrad i databasekopien (hvis kopien rekker så langt)."""
    from klatreforhold.data.http import get
    js = get(API, timeout=20).json()
    t = pd.Timestamp(js["tidspunkt_utc"])
    dag = t.tz_convert(TZ).strftime("%Y-%m-%d")
    rader = les_db(db, dag, dag)
    d = js["data"]
    rad = {"tidspunkt": js["tidspunkt"], "alder_sekunder": js["alder_sekunder"], "fersk": js["fersk"],
           "api_temp": d["temperatur_c"], "api_rh": d["luftfuktighet_pst"], "api_vind": d["vind_ms"]}
    if t in rader.index:
        r = rader.loc[t]
        rad.update(db_temp=round(r["air_temperature"], 1), db_rh=r["relative_humidity"], db_vind=round(r["wind_speed"], 1))
    else:
        rad["db"] = f"kopien slutter {rader.index.max().tz_convert(TZ):%d.%m.%Y %H:%M}"
    return pd.DataFrame([rad])


def dekning(timer: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Andel hele timer per måned, og de lengste sammenhengende hullene."""
    ok = timer["air_temperature"].notna() & timer["precipitation"].notna()
    lokal = timer.index.tz_convert(TZ)
    mnd = ok.groupby(lokal.strftime("%Y-%m")).mean().round(3).rename("andel_timer").rename_axis("maned").reset_index()
    blokk = (ok != ok.shift()).cumsum()
    hull = timer.index.to_series()[~ok].groupby(blokk[~ok]).agg(["min", "max", "size"])
    hull = hull.sort_values("size", ascending=False).head(8)
    hull = pd.DataFrame({"fra": (hull["min"] - pd.Timedelta(hours=1)).dt.tz_convert(TZ).dt.strftime("%d.%m.%Y %H:%M"),
                         "til": hull["max"].dt.tz_convert(TZ).dt.strftime("%d.%m.%Y %H:%M"), "timer": hull["size"]})
    return mnd, hull


def manedssum(varsel: pd.Series, malt: pd.Series, timer: pd.DataFrame) -> pd.DataFrame:
    """Nedbør per hele måned (minst 95 % av timene målt), og forholdet varsel/målt."""
    j = pd.concat({"varsel": varsel, "malt": malt}, axis=1).dropna()
    key = j.index.tz_convert(TZ).strftime("%Y-%m")
    timer_i_mnd = timer.index.tz_convert(TZ).strftime("%Y-%m").value_counts()
    g = j.groupby(key).sum().round(1)
    g["andel_timer"] = (j.groupby(key).size() / timer_i_mnd.reindex(g.index)).round(3)
    g = g[g["andel_timer"] >= 0.95]
    g["forhold"] = (g["varsel"] / g["malt"]).round(2)
    return g.reset_index(names="maned")


def regnepisoder(malt: pd.Series, min_mm: float = 1.0, pause_t: int = 2) -> pd.DataFrame:
    """Sammenhengende regn i målingene (opphold opptil pause_t timer slås sammen), minst min_mm totalt."""
    vatt = (malt >= REGN_MM).to_numpy()
    idx = malt.index
    ep, start, siste = [], None, None
    for i, w in enumerate(vatt):
        if not w:
            continue
        if start is not None and i - siste > pause_t + 1:
            ep.append((start, siste))
            start = None
        if start is None:
            start = i
        siste = i
    if start is not None:
        ep.append((start, siste))
    rows = [{"start": idx[a], "slutt": idx[b], "mm": float(malt.iloc[a:b + 1].sum())} for a, b in ep]
    return pd.DataFrame([r for r in rows if r["mm"] >= min_mm])


def timing(episoder: pd.DataFrame, varsel: pd.Series, margin_t: int = 3) -> pd.DataFrame:
    """For hver målt regnepisode: når startet og sluttet regnet i varselet (>= 0.2 mm/t) innen +-margin_t timer?

    Siste regntime er den som teller mest for tørking, så slutt-feilen er hovedtallet.
    """
    rows = []
    for _, e in episoder.iterrows():
        vindu = varsel.loc[e["start"] - pd.Timedelta(hours=margin_t):e["slutt"] + pd.Timedelta(hours=margin_t)]
        if vindu.isna().mean() > 0.2:
            continue
        v = vindu.index[vindu >= REGN_MM]
        rad = {"start": e["start"], "mm_malt": round(e["mm"], 1), "mm_varsel": round(float(vindu.sum()), 1),
               "funnet": len(v) > 0}
        if len(v):
            rad["start_feil_t"] = (v[0] - e["start"]) / pd.Timedelta(hours=1)
            rad["slutt_feil_t"] = (v[-1] - e["slutt"]) / pd.Timedelta(hours=1)
        rows.append(rad)
    return pd.DataFrame(rows)


def timing_sammendrag(t: pd.DataFrame) -> dict:
    f = t[t["funnet"]]
    return {"episoder": len(t), "funnet": round(float(t["funnet"].mean()), 3),
            "start_innen_1t": round(float((f["start_feil_t"].abs() <= 1).mean()), 3),
            "slutt_innen_1t": round(float((f["slutt_feil_t"].abs() <= 1).mean()), 3),
            "start_median_t": float(f["start_feil_t"].median()), "slutt_median_t": float(f["slutt_feil_t"].median()),
            "slutt_median_abs_t": float(f["slutt_feil_t"].abs().median())}


def vind_retning(varsel: pd.DataFrame, malt: pd.DataFrame, min_ms: float = 2.0) -> dict:
    """Forskjell i vindretning (grader, -180..180) når begge har minst min_ms."""
    j = pd.concat({"v": varsel["wind_direction"], "m": malt["wind_direction"],
                   "fv": varsel["wind_speed"], "fm": malt["wind_speed"]}, axis=1).dropna()
    j = j[(j["fv"] >= min_ms) & (j["fm"] >= min_ms)]
    d = (j["v"] - j["m"] + 180) % 360 - 180
    return {"timer": len(j), "median_avvik": round(float(d.median()), 1), "median_abs": round(float(d.abs().median()), 1),
            "andel_innen_45": round(float((d.abs() <= 45).mean()), 3)}


def duggpunkt(t_c, rh):
    """Magnus-formelen. Duggpunktet endrer seg lite mellom to steder selv om temperaturen gjør det."""
    g = np.log(np.clip(rh, 1, 100) / 100) + 17.62 * t_c / (243.12 + t_c)
    return 243.12 * g / (17.62 - g)


def mot_florida(timer, met, start, slutt, stasjon="SN50540"):
    """Bønes mot Florida (Frost). Skiller en fast sensorforskjell fra en ekte forskjell i fuktighet mellom stedene.

    I vind og regn er lufta godt blandet og nær lik over noen km. Står Bønes fortsatt for fuktig da, og er
    duggpunktet høyere selv om temperaturen er lik, peker det mot sensoren og ikke mot stedet.
    """
    from klatreforhold.data.frost import RECENT_ELEMENTS, fetch_observations, station_info
    from klatreforhold.data.openmeteo import fetch_history

    info = station_info(stasjon)
    frost = _cached(RAW / f"frost_{stasjon}_{start}_{slutt}.csv",
                    lambda: fetch_observations(stasjon, start, slutt, elements=RECENT_ELEMENTS))
    flo = to_obs_frame(frost)
    met_flo = _cached(RAW / f"stasjon_{stasjon}_openmeteo_metno_{start}_{slutt}.csv",
                      lambda: fetch_history(info["lat"], info["lon"], start, slutt))
    print(f"\n=== {stasjon} {info.get('navn')} ({info['lat']:.4f}, {info['lon']:.4f}), "
          f"{flo.dropna(how='all').shape[0]} timer med målinger ===")

    serier = {f"{NAVN} målt": timer, f"MET Nordic ved {stasjon}": met_flo, f"MET Nordic ved {NAVN}": met}
    rows = []
    for navn, w in serier.items():
        r = scores(to_obs_frame(w).reset_index(names="tid"), flo, by_lead=False)
        r.insert(0, "mot Florida", navn)
        rows.append(r)
    res = pd.concat(rows).drop(columns="ledetid")
    _show("Mot Florida, time for time (rad - Florida):", res)
    _show("Regnvinduer mot Florida:", pd.DataFrame(
        [{"mot Florida": n, **rain_windows(w["precipitation"], flo["nedbor_mm"])} for n, w in serier.items()]))

    j = pd.concat({"tb": timer["air_temperature"], "rb": timer["relative_humidity"], "nb": timer["precipitation"],
                   "tf": frost["air_temperature"], "rf": frost["relative_humidity"], "nf": frost["precipitation"],
                   "vf": frost["wind_speed"]}, axis=1).dropna()
    j["dt"] = j["tb"] - j["tf"]
    j["drh"] = j["rb"] - j["rf"]
    j["dtd"] = duggpunkt(j["tb"], j["rb"]) - duggpunkt(j["tf"], j["rf"])
    utvalg = {
        "alle timer": j.index == j.index,
        "vind >= 6 m/s, oppholdsvær": (j["vf"] >= 6) & (j["nb"] == 0) & (j["nf"] == 0),
        "regn begge steder (>= 0.5 mm)": (j["nb"] >= 0.5) & (j["nf"] >= 0.5),
        "rolig natt (< 2 m/s, kl. 00-06)": (j["vf"] < 2) & np.isin(j.index.tz_convert(TZ).hour, range(0, 6)),
        "ettermiddag (kl. 12-18)": np.isin(j.index.tz_convert(TZ).hour, range(12, 18)),
    }
    diff = pd.DataFrame([{"utvalg": k, "timer": int(m.sum()), "temp": round(j.loc[m, "dt"].mean(), 2),
                          "rh": round(j.loc[m, "drh"].mean(), 2), "duggpunkt": round(j.loc[m, "dtd"].mean(), 2),
                          "rh_median_bones": round(j.loc[m, "rb"].median(), 1),
                          "rh_median_florida": round(j.loc[m, "rf"].median(), 1)} for k, m in utvalg.items()])
    _show(f"{NAVN} - Florida, målt mot målt:", diff)
    niva = j.groupby(pd.cut(j["rf"], [0, 60, 70, 80, 90, 95, 101], right=False), observed=True)["drh"]
    _show("Fuktighetsforskjell etter nivå hos Florida (en fast sensorfeil er lik på alle nivåer):",
          pd.DataFrame({"rh_florida": niva.size().index.astype(str), "timer": niva.size().to_numpy(),
                        "rh_bones_minus_florida": niva.mean().round(2).to_numpy()}))

    rh = pd.DataFrame({f"MET - {stasjon}": rh_bias_table(met_flo["relative_humidity"], flo["luftfuktighet"], "maned")
                       .set_index("maned")["skjevhet"],
                       f"MET - {NAVN}": rh_bias_table(met["relative_humidity"], timer["relative_humidity"], "maned")
                       .set_index("maned")["skjevhet"]}).reindex(MANEDER)
    _show("Luftfuktighet, varsel - målt per måned ved hver stasjon:", rh.reset_index(names="maned"))
    return res, diff


def folsomhet(slug, w_met: pd.DataFrame, bones_mm: pd.Series) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Hvor mye endrer modellen seg med Bønes-regn i stedet for MET Nordic-regn? Ingen fasit, bare forskjellen.

    Regnet byttes som i predict.with_observations(): målt der det finnes, ellers modellens. Alt annet er likt.
    """
    from klatreforhold.physics.wetness import run_model

    crag, params = load_crag(slug)
    w_bones = w_met.copy()
    m = bones_mm.reindex(w_met.index)
    w_bones["precipitation"] = m.where(m.notna(), w_met["precipitation"])
    a = run_model(w_met, crag, params)["status"]
    b = run_model(w_bones, crag, params)["status"]
    lokal = a.index.tz_convert(TZ)
    dag = (lokal.hour >= 8) & (lokal.hour < 20)
    tab = pd.crosstab(a[dag].rename("MET Nordic-regn"), b[dag].rename("Bønes-regn"))

    # Tørketid: timer fra regnet slutter (i hver serie) til modellen sier tørt igjen
    ep = regnepisoder(bones_mm.reindex(w_met.index))
    rows = []
    for _, e in ep.iterrows():
        t0 = e["slutt"]
        vindu = slice(t0, t0 + pd.Timedelta(hours=72))
        ta, tb = a.loc[vindu], b.loc[vindu]
        ferdig_a = ta.index[ta == "tort"]
        ferdig_b = tb.index[tb == "tort"]
        if len(ferdig_a) and len(ferdig_b):
            rows.append({"slutt": t0, "mm": e["mm"], "endring_t": (ferdig_b[0] - ferdig_a[0]) / pd.Timedelta(hours=1)})
    tork = pd.DataFrame(rows)
    sammendrag = pd.DataFrame([{
        "felt": slug, "timer_dagtid": int(dag.sum()),
        "lik_status": round(float((a[dag] == b[dag]).mean()), 3),
        "tort_met": round(float((a[dag] == "tort").mean()), 3), "tort_bones": round(float((b[dag] == "tort").mean()), 3),
        "episoder": len(tork),
        "tort_tidligere_med_bones": round(float((tork["endring_t"] < 0).mean()), 3) if len(tork) else None,
        "tort_senere_med_bones": round(float((tork["endring_t"] > 0).mean()), 3) if len(tork) else None,
        "endring_median_t": float(tork["endring_t"].median()) if len(tork) else None,
        "endring_abs_over_3t": round(float((tork["endring_t"].abs() > 3).mean()), 3) if len(tork) else None,
    }])
    return sammendrag, tab


def main():
    from klatreforhold.config import rh_correction_for_station
    from klatreforhold.data.openmeteo import fetch_history
    from klatreforhold.physics.wetness import rh_correction

    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True, help="kopi av weewx.sdb (åpnes skrivebeskyttet)")
    ap.add_argument("--start", default="2023-01-01")
    ap.add_argument("--slutt", default="2026-10-30")
    ap.add_argument("--uten-api", action="store_true", help="ikke hent siste måling fra API-et")
    a = ap.parse_args()
    out = ROOT / "outputs"
    out.mkdir(exist_ok=True)

    _show("Kontroll mot tallene i database.md:", kontroll_mot_dokumentasjon(a.db))
    rader = les_db(a.db, a.start, a.slutt)
    timer = til_timer(rader)
    obs = to_obs_frame(timer)
    print(f"\n{NAVN}: {len(rader)} femminuttsrader, {obs.dropna(how='all').shape[0]} av {len(obs)} timer med målinger, "
          f"{a.start} – {a.slutt}")
    if not a.uten_api:
        try:
            _show("API-et mot databasekopien:", sjekk_api(a.db))
        except Exception as err:  # API-et er bare en stikkprøve
            print(f"\nAPI-et svarte ikke: {err}")

    mnd, hull = dekning(timer)
    _show("Andel hele timer per måned:", mnd)
    _show("Lengste hull:", hull)

    met = _cached(RAW / f"bones_openmeteo_metno_{a.start}_{a.slutt}.csv", lambda: fetch_history(LAT, LON, a.start, a.slutt))
    series = {f"MET Nordic ved {NAVN}": met}
    for slug in FELT:
        crag, _ = load_crag(slug)
        series[f"MET Nordic ved {slug}"] = _crag_weather(slug, crag, a.start, a.slutt)

    rows, vinduer = [], []
    for navn, w in series.items():
        r = scores(to_obs_frame(w).reset_index(names="tid"), obs, by_lead=False)
        r.insert(0, "værserie", navn)
        rows.append(r)
        vinduer.append({"værserie": navn, **rain_windows(w["precipitation"], obs["nedbor_mm"])})
    res = pd.concat(rows).drop(columns="ledetid")
    vin = pd.DataFrame(vinduer)
    _show(f"Hele perioden, time for time, mot {NAVN}:", res)
    _show("Regn over lengre vinduer (>= 0.5 mm i vinduet), og korrelasjon for døgnsum:", vin)

    fc = to_obs_frame(met).reset_index(names="tid")
    sesong = scores_by(fc, obs, "sesong")
    vin_s = rain_windows_by(met["precipitation"], obs["nedbor_mm"], "sesong")
    _show(f"Per sesong (MET Nordic ved {NAVN}):", sesong)
    _show("Regnvinduer per sesong:", vin_s)

    sum_mnd = manedssum(met["precipitation"], obs["nedbor_mm"], timer)
    _show("Nedbør per hele måned (mm):", sum_mnd)
    tot = sum_mnd[["varsel", "malt"]].sum()
    print(f"Sum over hele måneder: varsel {tot['varsel']:.0f} mm, målt {tot['malt']:.0f} mm, "
          f"forhold {tot['varsel'] / tot['malt']:.2f}")

    ep = regnepisoder(obs["nedbor_mm"])
    tim = {navn: timing(ep, w["precipitation"]) for navn, w in series.items()}
    _show("Regnepisoder (>= 1 mm målt): fant varselet dem, og hvor mange timer bommet start og slutt?",
          pd.DataFrame([{"værserie": n, **timing_sammendrag(t)} for n, t in tim.items()]))
    nyeste = tim[f"MET Nordic ved {NAVN}"].sort_values("mm_malt", ascending=False)
    nyeste = nyeste[nyeste["start"] >= pd.Timestamp(a.slutt, tz=TZ) - pd.Timedelta(days=90)].head(6).copy()
    nyeste["start"] = nyeste["start"].dt.tz_convert(TZ).dt.strftime("%d.%m.%Y %H:%M")
    _show("Største episoder siste 90 dager (MET Nordic ved Bønes):", nyeste)

    rh_v, rh_m = met["relative_humidity"], obs["luftfuktighet"]
    p = rh_correction_for_station("SN50540", ROOT / "config")
    rettet = (rh_v + rh_correction(rh_v.index, p)).clip(0, 100)
    rh = pd.concat([rh_bias_table(rh_v, rh_m, "maned").assign(serie="uten"),
                    rh_bias_table(rettet, rh_m, "maned").assign(serie="med SN50540-korreksjon")])
    _show("Luftfuktighet per måned (varsel - målt), uten og med korreksjonen fra Florida:",
          rh.pivot(index="maned", columns="serie", values="skjevhet").reindex(MANEDER).reset_index())
    _show("Per tid på døgnet:", pd.concat([rh_bias_table(rh_v, rh_m, "doegn").assign(serie="uten"),
                                           rh_bias_table(rettet, rh_m, "doegn").assign(serie="med")]))
    _show("Fordelingen (prosentiler):", rh_quantiles(rh_v, rh_m).reset_index(names="serie"))

    _show("Vindretning når begge har minst 2 m/s (varsel - målt):",
          pd.DataFrame([{"værserie": n, **vind_retning(w, timer)} for n, w in series.items()]))

    sammendrag, tab = folsomhet("ekstraveggen", series["MET Nordic ved ekstraveggen"], timer["precipitation"])
    _show("Ekstraveggen kjørt med Bønes-regn i stedet for MET Nordic-regn (dagtid kl. 08-20; tørketid etter "
          "regnepisoder >= 1 mm, positiv = tørt senere med Bønes):", sammendrag)
    _show("Status dagtid, MET Nordic-regn (rader) mot Bønes-regn (kolonner):", tab.reset_index())
    sammendrag.to_csv(out / "bones_folsomhet.csv", index=False)

    if os.environ.get("FROST_CLIENT_ID"):
        flo_res, flo_diff = mot_florida(timer, met, a.start, a.slutt)
        flo_res.to_csv(out / "bones_mot_florida.csv", index=False)
        flo_diff.to_csv(out / "bones_florida_forskjell.csv", index=False)
    else:
        print("\nFROST_CLIENT_ID mangler: hopper over sammenligningen med Florida (SN50540)")

    res.to_csv(out / "bones_historikk.csv", index=False)
    vin.to_csv(out / "bones_vinduer.csv", index=False)
    sesong.to_csv(out / "bones_sesong.csv", index=False)
    sum_mnd.to_csv(out / "bones_nedbor_maned.csv", index=False)
    rh.to_csv(out / "bones_rh_maned.csv", index=False)
    mnd.to_csv(out / "bones_dekning.csv", index=False)
    print(f"\nTabellene er lagret i {out.relative_to(ROOT)}/bones_*.csv")


if __name__ == "__main__":
    main()
