#!/usr/bin/env bash
# Nattlig Parquet-eksport av varselarkivet (docs/ARKIV.md). Startes av klatreforhold-arkiv.timer.
# Koden hentes av timesjobben (kjor_varsel.sh) hver time, så her kjøres bare gjeldende versjon.
# Pinger valgfri helsesjekk (KLATREFORHOLD_ARKIV_HEALTHCHECK_URL i .env), med daglig periode.
set -uo pipefail

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
VENV="$REPO/.venv"
cd "$REPO" || exit 1

HC="$(grep -E '^KLATREFORHOLD_ARKIV_HEALTHCHECK_URL=' .env 2>/dev/null | tail -n1 | cut -d= -f2- | tr -d '"'"'"' ')"
ping_hc() { [ -n "$HC" ] && curl -fsS -m 10 --retry 3 -o /dev/null "$HC$1" || true; }

ping_hc /start
cd modeling || exit 1
"$VENV/bin/python" scripts/eksporter_arkiv.py
status=$?

if [ "$status" -eq 0 ]; then ping_hc ""; else ping_hc /fail; fi
exit "$status"
