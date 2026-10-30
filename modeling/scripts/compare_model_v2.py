"""Ablasjon på samme værår: gammel modell, geometri, stråling, vind og ny vann/vinterbalanse.

Leser v1 fra Git (ingen checkout eller nett) og lager en etterprøvbar tabell.
"""
import argparse
import json
import subprocess
import sys
import types
from dataclasses import fields
from pathlib import Path
import warnings
import pandas as pd
import yaml
from _common import ROOT
from train import load_weather
from klatreforhold.config import Crag, load_config, rh_correction_for_station
from klatreforhold.physics.solar import face_irradiance, sky_view_factor
from klatreforhold.physics.wetness import run_model


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline", default="9db616c")
    a = ap.parse_args()
    warnings.filterwarnings("ignore", category=FutureWarning)
    def old(path):
        return subprocess.check_output(['git', '-c', 'safe.directory='+str(ROOT.parent), 'show', a.baseline+':'+path],
                                       cwd=ROOT.parent, encoding='utf-8')
    for name, filename in [('solar', 'solar.py'), ('wetness', 'wetness.py')]:
        module_name = 'klatreforhold.physics._baseline_' + name
        module = types.ModuleType(module_name)
        sys.modules[module_name] = module
        code = old('modeling/src/klatreforhold/physics/'+filename)
        if name == 'wetness':
            code = code.replace('from .solar import', 'from ._baseline_solar import')
        exec(compile(code, 'git:'+a.baseline+':'+filename, 'exec'), module.__dict__)
    legacy = sys.modules['klatreforhold.physics._baseline_wetness']
    old_solar = sys.modules['klatreforhold.physics._baseline_solar'].face_irradiance
    rows = []
    for slug in ['ekstraveggen', 'helleneset', 'sandviken']:
        cfg, params = load_config(ROOT / 'config' / (slug+'.yaml'))
        raw = yaml.safe_load(old('modeling/config/'+slug+'.yaml'))
        accepted = {f.name for f in fields(Crag)}
        previous = Crag(**{k: v for k, v in raw['crag'].items() if k in accepted})
        old_params = {k: float(v) if isinstance(v, str) and v.replace('.','',1).replace('e','',1).isdigit() else v for k, v in raw['model'].items()}
        old_params.update(rh_correction_for_station(previous.frost_station, ROOT / 'config'))
        file = sorted((ROOT / 'data/raw').glob(slug+'_openmeteo_metno_*.csv'))[-1]
        weather = load_weather(file).loc['2024-09-01':'2025-09-30']
        irradiance_params = {**old_params, 'sky_view_factor': sky_view_factor(cfg)}
        wind_params = {**irradiance_params, 'wind_exposure': params['wind_exposure']}
        experiments = [('v1', previous, old_params, old_solar, legacy.run_model),
            ('geometri', cfg, old_params, old_solar, legacy.run_model),
            ('straling', cfg, irradiance_params, face_irradiance, legacy.run_model),
            ('vind', cfg, wind_params, face_irradiance, legacy.run_model),
            ('vann_og_vinter', cfg, params, face_irradiance, run_model)]
        for label, crag, p, solar, engine in experiments:
            legacy.face_irradiance = solar
            result = engine(weather, crag, p).loc['2024-10-01':]
            local = result.index.tz_convert('Europe/Oslo')
            daytime = (local.hour >= 8) & (local.hour <= 20)
            summer = local.month.isin([4,5,6,7,8,9])
            row = {'felt': slug, 'trinn': label,
                'vate_dagtimer_sommer_prosent': round(float(result.wet[daytime & summer].mean()*100), 2),
                'vate_dagtimer_vinter_prosent': round(float(result.wet[daytime & ~summer].mean()*100), 2)}
            rows.append(row)
            print(row, flush=True)
    out = ROOT / 'outputs/model_v2_ablation.json'
    out.write_text(json.dumps({'baseline': a.baseline, 'periode': ['2024-10-01','2025-09-30'], 'rader': rows}, indent=2), encoding='utf-8')
    doc = ROOT.parent / 'docs/MODELL_V2_RESULTATER.md'
    lines = ['# Ablasjon av modell v2', '', 'Samme lokale vær per felt, 2024-10-01–2025-09-30, etter 30 døgn oppvarming.',
        'Tallene er simulert andel dagtimer (kl. 08–20) som ikke er tørre, ikke målte forhold.',
        'Dette inkluderer fuktig/vått og modellert is/snø; v1 har ingen egne is-/snølagre.',
        'Trinnene er kumulative; siste trinn inkluderer både ny vannbalanse, initialisering og vinterfysikk.', '',
        '| Felt | Trinn | Sommer, % vått | Vinter, % vått |', '|---|---|---:|---:|']
    lines += [f"| {r['felt']} | {r['trinn']} | {r['vate_dagtimer_sommer_prosent']} | {r['vate_dagtimer_vinter_prosent']} |" for r in rows]
    lines += ['', 'Reproduser: `python scripts/compare_model_v2.py --baseline '+a.baseline+'` fra `modeling/`.',
        'V1-koden og konfigurasjonen leses fra Git. Ingen lagrede prognoser eller observasjoner endres.']
    doc.write_text('\n'.join(lines)+'\n', encoding='utf-8')


if __name__ == '__main__':
    main()
