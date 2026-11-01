"""Tester Bønes-regnet uten nett: timeverdier fra API-historikk og lagrede målinger, bytte av regn og konfigsignaturen."""
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from klatreforhold.data import bones  # noqa: E402
from klatreforhold.predict import load_crag  # noqa: E402
from klatreforhold.storage import CsvStorage, SupabaseStorage  # noqa: E402
from klatreforhold.version import config_hash  # noqa: E402

CSV_HODE = ("tidspunkt,unix,intervall_minutter,temperatur_c,duggpunkt_c,luftfuktighet_pst,vind_ms,vindkast_ms,"
            "vindretning_grader,lufttrykk_hpa,nedbor_mm,nedbor_intensitet_mm_t,uv,straling_wm2")


def _csv(start="2026-10-31T08:05:00Z", n=36, regn=0.0, temp=8.0, hopp_over=()):
    """Femminuttsrader som API-et gir, start = første intervallslutt. hopp_over: indekser som mangler."""
    t0 = pd.Timestamp(start)
    rader = [CSV_HODE]
    for i in range(n):
        if i in hopp_over:
            continue
        t = t0 + pd.Timedelta(minutes=5 * i)
        lokal = t.tz_convert("Europe/Oslo").isoformat()
        r = regn(i) if callable(regn) else regn
        rader.append(f"{lokal},{int(t.timestamp())},5,{temp},6,90,1.3,2.2,135,1026.5,{r},0,0,12")
    return "\n".join(rader) + "\n"


def _maling(tid, mm, dato, temp=8.0):
    return {"tid": tid, "lufttemp": temp, "nedbor_i_dag_mm": mm, "nedbor_dato": dato}


def test_timeverdier_fra_api_historikk():
    # 08:05–11:00: tre hele timer (09, 10, 11). Regn 0,254 i hver rad i timen som slutter 10.
    raw = bones.parse_raw_csv(_csv(n=36, regn=lambda i: 0.254 if 12 <= i < 24 else 0.0, hopp_over=(30, 31, 32)))
    assert raw.index.tz is not None and list(raw.columns[:3]) == ["air_temperature", "dew_point_2m", "relative_humidity"]
    t = bones.hourly_from_raw(raw)
    assert list(t.index.strftime("%H")) == ["09", "10", "11"]
    np.testing.assert_allclose(t.loc["2026-10-31T09:00Z", "precipitation"], 0.0)
    np.testing.assert_allclose(t.loc["2026-10-31T10:00Z", "precipitation"], 12 * 0.254)
    assert t.loc["2026-10-31T11:00Z", "n_malinger"] == 9  # tre rader mangler: under 10 -> ukjent nedbør
    assert np.isnan(t.loc["2026-10-31T11:00Z", "precipitation"])
    np.testing.assert_allclose(t["air_temperature"], 8.0)
    np.testing.assert_allclose(t["wind_direction"], 135.0)


def test_siste_maling_som_snapshot():
    raw = bones.parse_raw_csv(_csv(start="2026-10-31T22:05:00Z", n=36, regn=0.254))  # 23:05–01:00 norsk tid
    rad = bones.latest_row(raw, now=pd.Timestamp("2026-11-01T01:03Z"))
    assert rad["tid"] == "2026-11-01T01:00:00+00:00" and rad["nedbor_dato"] == "2026-11-01"
    np.testing.assert_allclose(rad["nedbor_i_dag_mm"], 24 * 0.254)  # 00:05–02:00 norsk tid = nytt døgn
    assert bones.latest_row(raw, now=pd.Timestamp("2026-11-01T01:20Z")) is None  # eldre enn 15 min
    assert bones.latest_row(raw.iloc[:0]) is None


def test_timeverdier_fra_tellerdifferanser():
    m = pd.DataFrame([
        _maling("2026-10-31T09:05:00Z", 1.0, "2026-10-31"),
        _maling("2026-10-31T10:05:00Z", 1.4, "2026-10-31"),
        _maling("2026-10-31T10:30:00Z", 1.5, "2026-10-31"),  # ekstra kjøring samme time: den nærmest hel time teller
        _maling("2026-10-31T11:20:00Z", 2.0, "2026-10-31"),  # sen kjøring, 75 min etter forrige: fortsatt med
        _maling("2026-10-31T13:05:00Z", 2.0, "2026-10-31"),  # hoppet over 12: ukjent, ikke null
    ])
    t = bones.hourly(m)
    assert list(t.index.strftime("%H")) == ["09", "10", "11", "13"]
    assert np.isnan(t.loc["2026-10-31T09:00Z", "precipitation"])  # ingen forrige måling
    np.testing.assert_allclose(t.loc["2026-10-31T10:00Z", "precipitation"], 0.4)
    np.testing.assert_allclose(t.loc["2026-10-31T11:00Z", "precipitation"], 0.6)
    assert np.isnan(t.loc["2026-10-31T13:00Z", "precipitation"])


def test_midnatt_og_nullstilt_teller_er_ukjent():
    m = pd.DataFrame([
        _maling("2026-10-31T22:05:00Z", 5.0, "2026-10-31"),  # 23:05 norsk tid
        _maling("2026-10-31T23:05:00Z", 0.2, "2026-11-01"),  # 00:05: nytt døgn, telleren startet på nytt
        _maling("2026-11-01T00:05:00Z", 0.1, "2026-11-01"),  # telleren gikk ned: feil, ikke negativt regn
    ])
    t = bones.hourly(m)
    np.testing.assert_allclose(t.loc["2026-10-31T22:00Z", "air_temperature"], 8.0)
    assert t["precipitation"].isna().all()


def test_regn_byttes_bare_der_det_er_malt_og_varmt():
    idx = pd.date_range("2026-10-31T08:00Z", periods=6, freq="h")
    w = pd.DataFrame({"precipitation": 2.0, "air_temperature": 5.0, "snow_water_mm": 0.5,
                      "weather_source": "metnordic"}, index=idx)
    m = pd.DataFrame([
        _maling("2026-10-31T08:05:00Z", 0.0, "2026-10-31"),
        _maling("2026-10-31T09:05:00Z", 0.0, "2026-10-31"),  # Bønes tørt, modellen 2 mm
        _maling("2026-10-31T10:05:00Z", 0.6, "2026-10-31", temp=1.0),  # for kaldt: kan være snø
        _maling("2026-10-31T11:05:00Z", 1.1, "2026-10-31"),
    ])
    out = bones.with_rain(w, bones.hourly(m), now=pd.Timestamp("2026-10-31T11:10Z"))
    np.testing.assert_allclose(out["precipitation"], [2.0, 0.0, 2.0, 0.5, 2.0, 2.0])
    assert list(out["precipitation_source"]) == ["metnordic", "bones", "metnordic", "bones", "metnordic", "metnordic"]
    assert np.isnan(out.loc["2026-10-31T09:00Z", "snow_water_mm"]) and out.loc["2026-10-31T10:00Z", "snow_water_mm"] == 0.5
    assert out.attrs["bones_timer"] == 2 and w["precipitation"].eq(2.0).all()  # originalen er urørt


def test_uten_malinger_er_varet_uendret():
    w = pd.DataFrame({"precipitation": [1.0], "air_temperature": [5.0]},
                     index=pd.DatetimeIndex(["2026-10-31T08:00Z"]))
    assert bones.with_rain(w, pd.DataFrame()) is w and bones.with_rain(w, None) is w


def test_signaturen_endres_bare_nar_regnet_erstattes():
    crag, params = load_crag("ekstraveggen")
    uten = replace(crag, regnmaler=None, regnmaler_bruk="av")
    assert config_hash(replace(crag, regnmaler="bones", regnmaler_bruk="av"), params) == config_hash(uten, params)
    assert config_hash(replace(crag, regnmaler="bones", regnmaler_bruk="erstatt"), params) != config_hash(uten, params)


def test_lagring():
    assert CsvStorage().save_bones([{"tid": "x"}]) == 0 and CsvStorage().bones_readings("2026-10-31T00:00Z").empty
    st = SupabaseStorage("https://abc.supabase.co", "key")
    kall = []

    class Svar:
        def __init__(self, data=None):
            self.data = data

        def raise_for_status(self):
            pass

        def json(self):
            return self.data

    st.s.post = lambda url, **kw: kall.append((url, kw)) or Svar()
    st.s.get = lambda url, **kw: kall.append((url, kw)) or Svar([{"tid": "2026-10-31T10:05:00+00:00"}])
    assert st.save_bones([{"tid": "2026-10-31T10:05:00+00:00"}]) == 1
    assert kall[-1][0].endswith("/rest/v1/bones_maling") and kall[-1][1]["params"]["on_conflict"] == "tid"
    assert len(st.bones_readings(pd.Timestamp("2026-10-31T00:00Z"))) == 1
    assert kall[-1][1]["params"]["tid"] == "gte.2026-10-31T00:00:00+00:00"


def test_timesjobben_taaler_at_bones_feiler(monkeypatch):
    from klatreforhold import publish

    class Lager:
        def __init__(self):
            self.lagret = []

        def save_bones(self, rows):
            self.lagret += rows
            return len(rows)

        def bones_readings(self, since):
            raise RuntimeError("nede")

    lager = Lager()
    now = pd.Timestamp("2026-10-31T11:03Z")
    raw = bones.parse_raw_csv(_csv(n=36, regn=0.254))  # 08:05–11:00
    crag, params = load_crag("ekstraveggen")
    monkeypatch.setattr(publish, "load_crag",
                        lambda slug: (replace(crag, regnmaler="bones", regnmaler_bruk="av"), params))
    monkeypatch.setattr(bones, "fetch_raw", lambda hours: raw)
    status, timer = publish.collect_bones(lager, now)
    assert status == {"lagret": 1} and timer is None and len(lager.lagret) == 1  # "av": samler bare inn

    def feil(hours):
        raise ConnectionError("API-et svarer ikke")
    monkeypatch.setattr(bones, "fetch_raw", feil)
    status, _ = publish.collect_bones(lager, now)
    assert "ConnectionError" in status["advarsel"]

    monkeypatch.setattr(publish, "load_crag",
                        lambda slug: (replace(crag, regnmaler="bones", regnmaler_bruk="erstatt"), params))
    status, timer = publish.collect_bones(lager, now)  # API nede og reserven nede: ingen timer, varselet går videre
    assert "ConnectionError" in status["advarsel"] and "RuntimeError" in status["advarsel_lesing"] and timer is None

    monkeypatch.setattr(bones, "fetch_raw", lambda hours: raw)
    status, timer = publish.collect_bones(lager, now + pd.Timedelta(minutes=30))  # siste måling 33 min gammel
    assert status["advarsel"] == "målingen er ikke fersk" and status["lagret"] == 0 and status["timer"] == 3
    np.testing.assert_allclose(timer["precipitation"], 12 * 0.254)
