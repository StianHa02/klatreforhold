"""Tester at svarene fra API-ene tolkes riktig, med falske svar (krever ikke nett)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from klatreforhold.data import frost, metno, openmeteo  # noqa: E402


class Fake:
    def __init__(self, js):
        self._js = js

    def json(self):
        return self._js


def test_openmeteo_parse():
    js = {"hourly": {"time": ["2026-07-01T00:00", "2026-07-01T01:00"],
                     "temperature_2m": [12.0, 11.5], "relative_humidity_2m": [80, 85], "dew_point_2m": [8.6, 9.1],
                     "precipitation": [0.0, 1.2], "cloud_cover": [50, 100], "shortwave_radiation": [0, 0],
                     "direct_normal_irradiance": [0, 0], "diffuse_radiation": [0, 0],
                     "wind_speed_10m": [3.0, 4.0], "wind_direction_10m": [290, 300]}}
    openmeteo.get = lambda *a, **k: Fake(js)
    df = openmeteo.fetch_forecast(60.3346, 5.3122)
    assert str(df.index.tz) == "UTC"
    assert df["cloud_cover"].max() == 1.0 and "wind_direction" in df and df["precipitation"].iloc[1] == 1.2


def test_locationforecast_parse_shifts_precip():
    ts = [{"time": f"2026-07-01T0{h}:00:00Z", "data": {
        "instant": {"details": {"air_temperature": 10, "relative_humidity": 90, "wind_speed": 2,
                                "wind_from_direction": 300, "cloud_area_fraction": 100, "dew_point_temperature": 8}},
        "next_1_hours": {"details": {"precipitation_amount": float(h)}}}} for h in range(3)]
    metno.get = lambda *a, **k: Fake({"properties": {"timeseries": ts}})
    df = metno.fetch_locationforecast(60.3346, 5.3122)
    # nedbør for 01-02 skal stå på 02:00 (timen før tidsstempelet)
    assert df["precipitation"].tolist() == [0.0, 0.0, 1.0]


def test_frost_parse():
    js = {"data": [{"referenceTime": "2026-07-01T00:00:00.000Z", "observations": [
        {"elementId": "air_temperature", "value": 12.1},
        {"elementId": "sum(precipitation_amount PT1H)", "value": 0.4},
        {"elementId": "cloud_area_fraction", "value": 4}]}]}
    frost.get = lambda *a, **k: Fake(js)
    frost._auth = lambda: ("x", "")
    df = frost.fetch_observations("SN50540", "2026-07-01", "2026-07-02")
    assert df["precipitation"].iloc[0] == 0.4 and df["cloud_cover"].iloc[0] == 0.5



def test_observations_replace_history_only():
    import os
    import pandas as pd
    from klatreforhold import predict
    from klatreforhold.config import Crag
    idx = pd.date_range("2026-07-01", periods=4, freq="h", tz="UTC")
    w = pd.DataFrame({"precipitation": [0.0, 0.0, 0.0, 2.0], "air_temperature": [10.0] * 4,
                      "dew_point_2m": [5.0] * 4, "ghi": [100.0] * 4}, index=idx)
    obs = pd.DataFrame({"precipitation": [1.0, None], "air_temperature": [12.0, 13.0]}, index=idx[:2])
    frost.fetch_recent = lambda *a, **k: obs
    os.environ.setdefault("FROST_CLIENT_ID", "x")
    out = predict.with_observations(w, Crag("t", 60, 5, 270, frost_station="SN1"))
    assert out["precipitation"].tolist() == [1.0, 0.0, 0.0, 2.0]  # hull i målingene fylles fra modellen
    assert out["air_temperature"].tolist() == [12.0, 13.0, 10.0, 10.0]
    assert out["ghi"].tolist() == [100.0] * 4 and "dew_point_2m" not in out
    assert out.attrs["frost_station"] == "SN1"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("OK", name)
