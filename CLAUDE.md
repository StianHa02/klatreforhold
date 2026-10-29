# CLAUDE.md

Guidance for Claude (and other agents) working in this repo. Read `docs/OVERLEVERING.md` for the full
handover: what has been built, what has been found, the decisions and why, and what is left.

## What this is

**klatreforhold** predicts whether the rock at a Bergen climbing crag is dry, damp, wet or icy, hour by hour
(5 h back, now, 19 h ahead on the site; 48 h ahead in the data), from public weather data only. It is a
standalone project for Bergen Klatreklubb (BKK). It will eventually feed BKK's nettfører (digital climbing
guide), but **for now it must not touch the nettfører repo or its database**.

Crags: Ekstraveggen (felt_id 137), Sandviken (33), Helleneset (5), Neseveggen (11), Bolstadøyri (64),
Trollkona (114), Loddefjord (2), Bymuren (1), Fabrikkveggen (77). One crag = one YAML file in `modeling/config/`.

## Architecture (no dedicated API in production)

```
GitHub Actions, hourly at :07  ->  modeling/scripts/publish_forecast.py
  MET Nordic 1 km via Open-Meteo -> physics model (+ optional ML) -> Supabase (service role key)
Vercel (Next.js, root directory web/)  ->  reads Supabase server-side, stores user feedback
```

- Supabase project `nmiydpcmfxkhtztzgzfx` (org "klatreforhold", eu-north-1). Tables: `varsel_siste`
  (latest forecast per crag, jsonb), `varsel` (archive, one row per hour and lead time), `observasjoner`
  (user feedback = training labels), `stasjon_varsel` + `stasjon_maling` (Frost control). RPC functions
  `treffsikkerhet(text)` and `statistikk()`. RLS is on with **no policies**: only the service role can read/write.
- FastAPI (`modeling/app.py`, `src/klatreforhold/api.py`) exists for local development / Docker only.
- Development points at the **same** Supabase database as production. Local observations are tagged
  `kilde = 'dev'` (env `KLATREFORHOLD_KILDE=dev`) and excluded from training unless `--med-dev`.

## Layout

```
modeling/                 Python 3.12. Run every Python command from here (cd modeling)
  config/<crag>.yaml      geometry, horizon (from Kartverket DOM1), model parameters
  config/kalibrert/       calibrated parameters (written by calibrate.py --write), override the above
  config/stasjoner/       per Frost station settings (rh_korreksjon.yaml). NOT crag files
  src/klatreforhold/
    physics/wetness.py    hourly water + surface energy balance (run_model, rh_correction, hours_until_dry)
    physics/solar.py      pvlib irradiance on the tilted face, horizon mask, longwave
    data/                 openmeteo.py, metno.py, frost.py, metnordic_thredds.py, station_csv.py
    ml/                   features, evaluate (fair strata), calibrate (MAP), train (sklearn), torch_model (GRU)
    predict.py            forecast for one crag (now + N hours, summary, reasons)
    publish.py            the hourly job (writes Supabase); also Frost control collection
    storage.py            CsvStorage / SupabaseStorage (PostgREST over requests)
    verify.py             forecast vs Frost stations: hourly, windows, season/year, humidity correction fit
  scripts/                CLI tools (see docs/OVERLEVERING.md for the list)
  tests/test_*.py         plain scripts with asserts; run with `python tests/test_x.py` (or pytest)
web/                      Next.js 16 app (React 19, Tailwind 4). See web/CLAUDE.md -> web/AGENTS.md
  lib/kilde.ts            data source: Supabase mode (prod) or Python API mode (local)
  app/felt/[slug]/        crag page; app/om/ about page; app/api/felt/[slug]/observasjoner/ feedback route
supabase/migrations/      applied schema. supabase/valgfritt/ = optional SQL, NOT applied
docs/                     MODEL.md (model + results), RESEARCH.md, DEPLOY.md, OVERLEVERING.md (handover),
                          LEGG_TIL_FELT.md (how to add a crag)
.github/workflows/varsel.yml   hourly job
```

## Commands

Windows / PowerShell on the owner's machine. `.env` lives in the repo root and is auto-loaded by
`klatreforhold.config` (also `modeling/.env`).

```powershell
cd modeling
python tests\test_physics.py                     # each test file runs standalone; or: python -m pytest tests
python scripts\predict_now.py --config config\ekstraveggen.yaml
python scripts\publish_forecast.py --dry-run     # hourly job without writing
python scripts\verify_forecast.py                # forecast archive vs Frost
python scripts\verify_forecast.py --historikk --skriv-rh   # 2023 -> yesterday, season/year, writes RH correction
python scripts\export_site_stats.py              # regenerates web/data/modellstatistikk.json (about page)
python scripts\calibrate.py --config config\ekstraveggen.yaml --weather data\raw\<csv> --labels supabase --write
python scripts\train.py --weather data\raw\<csv> --labels supabase --torch --save

cd ..\web; npm install; npm run dev; npm test     # npm test = node tests for lib/kilde.ts
docker compose up --build                          # api :8000 + web :3000
```

## Conventions

- **Norwegian (bokmål)** for UI text, docs, identifiers in the domain and commit messages. Code comments
  are Norwegian too. ASCII in identifiers and status values: `tort`, `fuktig`, `vatt`, `is`.
- Domain words: `felt` crag, `varsel` forecast, `observasjon` user report, `ledetid` lead time,
  `generert` run time, `stasjon` weather station, `kilde` source, `tørketid` drying time.
- Timestamps: UTC, tz-aware, hourly. Precipitation and radiation are for the hour **before** the timestamp
  (Open-Meteo / MET convention). In the web app, naive times from users are read as Europe/Oslo.
- Azimuth is compass degrees (pvlib). Open-Meteo GTI uses 0 = south, so do not mix them.
- Coordinates max 4 decimals (api.met.no requirement). MET requires an identifying User-Agent:
  `KLATREFORHOLD_CONTACT` (defaults to the club site). Never put a personal email in code.
- The owner commits and pushes himself. Do not commit/push unless asked; give the commands instead.
  Another Claude session may be working on the frontend styling: keep your changes to your own files and
  say which files you touched.

## Invariants (do not break)

- `SUPABASE_SERVICE_ROLE_KEY` is server-only. Never `NEXT_PUBLIC_`, never in client components, never committed.
- Never train with `--save` on synthetic labels (e.g. made from a rain rule): the model just learns the rule.
- Dev/test observations (`kilde in ('dev','test')`) never go into training by default.
- `frost_bruk: kontroll` is the default. Station data checks the forecast; it does not replace crag weather
  (Bergen weather is very local). Only use `erstatt` for a station 1-2 km from the crag.
- The forecast must keep working without Frost, ML models or calibration files (all optional, all fall back).
- Every `*.yaml` directly in `modeling/config/` is treated as a crag. Put other YAML in a subfolder.
- Humidity correction is fitted on **all** hours. Never fit a bias correction on hours selected by the
  forecast value (regression to the mean makes the forecast look biased; see docs/MODEL.md).

## Gotchas

- `.vercelignore` patterns must be root-anchored (`/modeling`, not `modeling`): an unanchored `data` once
  removed `web/data` and broke the Vercel build.
- `next/font/google` needs network at build time. Offline builds fail; use `npx tsc --noEmit` to typecheck.
- PyYAML reads `2.2e6` as a string; `config._num()` converts it. Keep using `load_config`.
- GitHub's hourly schedule has been unreliable (runs so far were manual). `supabase/valgfritt/` has an
  optional Supabase Cron -> workflow_dispatch trigger for the owner to apply himself.
- Open-Meteo and Frost are rate limited / need `FROST_CLIENT_ID`. `verify_forecast.py --historikk` caches
  downloads in `modeling/data/raw/` (gitignored, like `outputs/` and the 1.2 GB DOM tiles).
