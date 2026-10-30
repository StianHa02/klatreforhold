import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from klatreforhold.data import metnordic_thredds as met, pipeline
from klatreforhold.config import Crag
from klatreforhold.physics.forcing import REQUIRED, prepare_weather


def test_native_forecast_accumulated_radiation_and_first_rain(monkeypatch):
    meta = {'x': np.array([-897442.2, -896442.2]), 'y': np.array([-1104322., -1103322.]),
            'time': np.array([0., 3600., 7200.]), 'forecast_reference_time': np.array([0.])}
    variables = list(met.VARS)
    data = {'time': meta['time']}
    for v in variables:
        data[v+'.'+v] = np.ones(3)
    data['air_temperature_2m.air_temperature_2m'] = np.array([280., 281., 282.])
    data['relative_humidity_2m.relative_humidity_2m'] = np.full(3, .8)
    data['integral_of_surface_downwelling_longwave_flux_in_air_wrt_time.integral_of_surface_downwelling_longwave_flux_in_air_wrt_time'] = np.array([0., 300., 610.])*3600
    data['integral_of_surface_downwelling_shortwave_flux_in_air_wrt_time.integral_of_surface_downwelling_shortwave_flux_in_air_wrt_time'] = np.array([0., 100., 300.])*3600
    monkeypatch.setattr(met, '_metadata', lambda *args: (meta, variables))
    monkeypatch.setattr(met, '_read', lambda *args: data)
    frame = met._point('test', 60.33, 5.31, 'forecast')
    np.testing.assert_allclose(frame.longwave_down.iloc[1:], [300., 310.])
    np.testing.assert_allclose(frame.ghi.iloc[1:], [100., 200.])
    assert np.isnan(frame.precipitation.iloc[0])
    assert frame.relative_humidity.iloc[0] == 80.


def test_provider_failure_keeps_full_reserve_and_reports_it(monkeypatch):
    now = pd.Timestamp('2026-10-30T10:30Z')
    index = pd.date_range('2026-09-01', '2026-11-05', freq='h', tz='UTC')
    base = pd.DataFrame({'air_temperature': 10., 'relative_humidity': 80., 'precipitation': 0.,
        'wind_speed': 3., 'wind_direction': 270., 'weather_source': 'openmeteo'}, index=index)
    monkeypatch.setattr(pipeline.openmeteo, 'fetch_forecast', lambda *a, **k: base.copy())
    def fail(*args, **kwargs):
        raise TimeoutError('public API unavailable')
    monkeypatch.setattr(met, 'fetch_forecast', fail)
    monkeypatch.setattr(pipeline, 'fetch_nowcast', fail)
    result = pipeline.fetch_weather(Crag('test', 60, 5, 270), now=now)
    assert result.precipitation.notna().all()
    assert set(result.attrs['fallback_sources']) == {'metnordic', 'nowcast'}


def test_cold_bootstrap_with_shorter_provider_archive_keeps_real_rain_and_internal_gaps(monkeypatch):
    # Bolstadøyri: API-et lover opptil 92 døgn, men har bare data fra 10. september.
    now = pd.Timestamp('2026-10-30T10:30Z')
    index = pd.date_range('2026-07-30', '2026-11-05', freq='h', tz='UTC')
    base = pd.DataFrame({'air_temperature': 0., 'relative_humidity': 80., 'precipitation': 1.,
        'wind_speed': 3., 'wind_direction': 270., 'weather_source': 'openmeteo'}, index=index)
    first = pd.Timestamp('2026-09-10T00:00Z')
    base.loc[base.index < first, REQUIRED] = np.nan
    monkeypatch.setattr(pipeline.openmeteo, 'fetch_forecast', lambda *a, **k: base.copy())
    crag = Crag('test', 60, 5, 270)
    result = pipeline.fetch_weather(crag, source='openmeteo', now=now, history_hours=168)
    assert result.index.min() == first
    assert 30 < result.attrs['bootstrap_days'] < 90
    assert prepare_weather(result).precipitation.eq(1.).all()
    # Et hull inne i historikken, eller tett på visningen, skal fortsatt stoppe modellen.
    base.loc[now.floor('h') - pd.Timedelta(days=5), 'precipitation'] = np.nan
    with pytest.raises(ValueError, match='Ufullstendig'):
        prepare_weather(pipeline.fetch_weather(crag, source='openmeteo', now=now, history_hours=168))
    base.loc[base.index < now - pd.Timedelta(days=20), REQUIRED] = np.nan
    with pytest.raises(ValueError, match='Ufullstendig'):
        prepare_weather(pipeline.fetch_weather(crag, source='openmeteo', now=now, history_hours=168))
