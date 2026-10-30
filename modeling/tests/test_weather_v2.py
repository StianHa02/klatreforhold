import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from klatreforhold.data.metnordic_thredds import parse_ascii
from klatreforhold.data.nowcast import apply_nowcast
from klatreforhold.data.pipeline import overlay


def test_dap_point_and_fill_values():
    text = 'Dataset {}\n---------------------------------------------\ntime[2]\n1000, 4600\n\nair.air[2][1][1]\n[0][0], 280\n[1][0], 9.96921e36\n\n'
    d = parse_ascii(text)
    np.testing.assert_array_equal(d['time'], [1000, 4600])
    assert d['air.air'][0] == 280 and np.isnan(d['air.air'][1])
    scalar = parse_ascii('Dataset {}\n---------------------------------------------\nforecast_reference_time, 1000\n')
    assert scalar['forecast_reference_time'][0] == 1000


def test_partial_hour_nowcast_and_stale_rejection():
    now = pd.Timestamp('2026-10-30T12:30Z')
    index = pd.date_range('2026-10-30T13:00Z', periods=3, freq='h')
    w = pd.DataFrame({'precipitation': 1., 'weather_source': 'openmeteo'}, index=index)
    payload = {'properties': {'meta': {'updated_at': now.isoformat(), 'radar_coverage': 'ok'}, 'timeseries': [
        {'time': t.isoformat(), 'data': {'instant': {'details': {'precipitation_rate': 2.}}}}
        for t in pd.date_range(now, periods=25, freq='5min')]}}
    out = apply_nowcast(w, payload, now)
    np.testing.assert_allclose(out.precipitation, [1.5, 2., 1.5])
    assert apply_nowcast(w, payload, now+pd.Timedelta(minutes=21)) is w


def test_native_overlay_keeps_reserve_for_missing_rain():
    idx = pd.date_range('2026-10-30', periods=2, freq='h', tz='UTC')
    base = pd.DataFrame({'air_temperature': 10., 'relative_humidity': 80., 'precipitation': 1.,
        'wind_speed': 2., 'wind_direction': 270., 'ghi': 100., 'dni': 50., 'dhi': 60., 'weather_source': 'openmeteo'}, index=idx)
    preferred = base.drop(columns=['dni','dhi']).copy()
    preferred['weather_source'] = 'metnordic'
    preferred.loc[idx[1], 'precipitation'] = np.nan
    out = overlay(base, preferred)
    assert out.weather_source.tolist() == ['metnordic', 'openmeteo']
    assert np.isnan(out.dni.iloc[0]) and out.dni.iloc[1] == 50.
    base['relative_humidity'] = 80  # JSON-reserven leverer ofte heltall; direkte MET har desimaler
    preferred['relative_humidity'] = 80.25
    assert overlay(base, preferred).relative_humidity.iloc[0] == 80.25
