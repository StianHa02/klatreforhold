"""Tester Bønes-regnet uten nett: timeverdier fra lagrede målinger, bytte av regn og konfigsignaturen."""
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


def _maling(tid, mm, dato, temp=8.0):
    return {"tid": tid, "lufttemp": temp, "nedbor_i_dag_mm": mm, "nedbor_dato": dato}


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
    out = bones.with_rain(w, m, now=pd.Timestamp("2026-10-31T11:10Z"))
    np.testing.assert_allclose(out["precipitation"], [2.0, 0.0, 2.0, 0.5, 2.0, 2.0])
    assert list(out["precipitation_source"]) == ["metnordic", "bones", "metnordic", "bones", "metnordic", "metnordic"]
    assert np.isnan(out.loc["2026-10-31T09:00Z", "snow_water_mm"]) and out.loc["2026-10-31T10:00Z", "snow_water_mm"] == 0.5
    assert out.attrs["bones_timer"] == 2 and w["precipitation"].eq(2.0).all()  # originalen er urørt


def test_uten_malinger_er_varet_uendret():
    w = pd.DataFrame({"precipitation": [1.0], "air_temperature": [5.0]},
                     index=pd.DatetimeIndex(["2026-10-31T08:00Z"]))
    assert bones.with_rain(w, pd.DataFrame()) is w


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
    monkeypatch.setattr(bones, "fetch_latest", lambda: {"tid": "2026-10-31T10:05:00+00:00"})
    status, malinger = publish.collect_bones(lager)
    assert status == {"lagret": 1} and malinger is None and len(lager.lagret) == 1  # "av": samler bare inn

    def feil():
        raise ConnectionError("API-et svarer ikke")
    monkeypatch.setattr(bones, "fetch_latest", feil)
    status, _ = publish.collect_bones(lager)
    assert "ConnectionError" in status["advarsel"]

    crag, params = load_crag("ekstraveggen")
    monkeypatch.setattr(publish, "load_crag",
                        lambda slug: (replace(crag, regnmaler="bones", regnmaler_bruk="erstatt"), params))
    monkeypatch.setattr(bones, "fetch_latest", lambda: None)
    status, malinger = publish.collect_bones(lager)
    assert status["advarsel"] == "målingen er ikke fersk" and "RuntimeError" in status["advarsel_lesing"]
    assert malinger is None
