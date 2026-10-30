# CLAUDE.md

Guidance for agents working in this repository. Current code reviewed 2026-10-30.
Read [README](README.md), [current handover](docs/OVERLEVERING.md) and [model v2](docs/MODELL_V2.md).
The handover's historical section and the research papers preserve older decisions, not current tasks.

## Architecture and layout

Standalone Bergen Klatreklubb project. Do not modify the nettfører repository or database.
Nine crags are defined by YAML files directly in `modeling/config/`; other YAML belongs in subfolders.

Actions runs hourly at :07 → `modeling/scripts/publish_forecast.py` → Supabase → Vercel Next.js (`web/`).
Production has no dedicated FastAPI server. Local API/Docker remain supported.
Direct MET Nordic is preferred, Open-Meteo supplies fallback/history, Nowcast overlays recent radar,
and optional MEPS supplies uncalibrated precipitation-only uncertainty. Model version is 2.0.0.
Latest payloads contain 120 hours ahead plus now and 168 hours behind; archive lead times stop at 48 hours.

- `modeling/src/klatreforhold/physics/`: energy/water balance, winter stores, solar geometry and drying events.
- `data/`: weather sources and pipeline. `predict.py`: forecasts; `publish.py`: hourly publishing.
- `storage.py`: CSV/Supabase; `verify.py`: Frost control; `ml/`: calibration and optional learned models.
- `modeling/scripts/`: CLI tools; `config/stasjoner/`: humidity correction; `config/kalibrert/`: validated fits.
- `web/`: Next.js 16, React 19, Tailwind 4. Read `web/AGENTS.md` before code changes.
- `web/lib/kilde.ts`: Supabase when keys exist, unless `KLATREFORHOLD_DATAKILDE=api`.
- `supabase/migrations/`: schema files, including v2 `modelltilstand`. Files alone do not prove remote application.
- `supabase/valgfritt/`: optional Actions trigger SQL, not automatically applied.

Supabase project: `nmiydpcmfxkhtztzgzfx`. Tables: `varsel_siste`, `varsel`, `observasjoner`,
`stasjon_varsel`, `stasjon_maling`, `modelltilstand`, `vaer` (model weather input per crag and past hour).
RPCs: `treffsikkerhet(text)`, `statistikk()`, `lagre_vaer(jsonb)`, `rydd_arkiv(integer)` (weekly pg_cron).
All access is server-side with service role; no public RLS policies. Grant `service_role` explicitly on new
tables: newer Supabase (including the local CLI) no longer grants it by default.
Test migrations on the local stack first (`supabase start` from repo root, ports 553xx; see README).

## Commands

Use Python 3.12 (CI version), Node 22+, and a virtual environment; setup is in README.
Run Python CLI commands from `modeling/`:

```sh
python -m pytest tests -q
python scripts/check_model_v2.py
python scripts/check_model_v2.py --live --forecast
python scripts/publish_forecast.py --dry-run
python scripts/verify_forecast.py
```

`--live` fetches public weather; dry-run does not publish but may populate local caches.
`predict_now.py` is a simple Open-Meteo/Locationforecast diagnostic, not the full production pipeline.
`export_site_stats.py` rewrites tracked web statistics and needs local historical CSVs.
`compare_model_v2.py` rewrites the results document and needs baseline Git history and weather CSVs.
Do not regenerate research artifacts for routine checks.

From `web/`: `npm ci`, `npm test`, `npm run typecheck`, `npm run build`.
From repo root: `docker compose up --build`. Build needs network for Google fonts.

## Conventions and invariants

- Norwegian bokmål for UI, new documentation, comments, domain identifiers and commit messages.
  Preserve historical research in its original language. Status identifiers are ASCII.
- Model/API statuses: `tort`, `fuktig`, `vatt`, `is`; web displays/reports three statuses, with ice mapped to wet.
- Timestamps are timezone-aware. Precipitation/radiation cover the hour before the timestamp;
  naive user times are Europe/Oslo. Wire timestamps may include Oslo offsets; storage normalizes to UTC.
- Azimuth is compass degrees; Open-Meteo GTI instead uses 0 = south. MET request coordinates use at most
  four decimals. Keep full precision in config. Set identifying `KLATREFORHOLD_CONTACT`, no personal email in code.
- `SUPABASE_SERVICE_ROLE_KEY` is server-only, never `NEXT_PUBLIC_` or committed.
- Development with shared Supabase keys uses production data. Keep `KLATREFORHOLD_KILDE=dev`;
  dev/test observations are excluded from training unless explicitly included with `--med-dev`.
- Never save models trained on synthetic labels. Calibration fits only evaporation efficiency,
  with at least 50 observations, ten rain events and held-out improvement. ML saves are unvalidated candidates.
- Model/calibration activation requires matching version, config hash and validation metadata.
- Forecasts must tolerate missing Frost, ensemble, calibration and ML. Default `frost_bruk: kontroll`;
  station replacement is only appropriate within 1–2 km. Do not hide missing rain by filling with zero.
- `rydd_arkiv()` must keep lead times 0/3/6/12/24/48 and every row near a real observation; those are training data.
- Fit humidity correction on all hours, never on a subset selected by predicted humidity.
  The current fitted correction applies to Open-Meteo, not automatically to direct MET.
- `.env` loader reads modeling then root and preserves existing environment. Put comments on separate lines.
- Use `load_config`: PyYAML may read scientific notation as text. Keep `.vercelignore` paths root-anchored.
- Weather caches, DOM tiles, local agent settings and build outputs stay outside Git.
- Do not commit/push unless requested. Respect concurrent worktrees and report changed files.
