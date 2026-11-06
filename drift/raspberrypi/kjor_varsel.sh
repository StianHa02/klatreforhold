#!/usr/bin/env bash
# Timesjobben på Raspberry Pi (erstatter GitHub Actions). Startes av klatreforhold-varsel.timer.
#   1. henter siste kode fra GitHub (fortsetter med gjeldende versjon hvis det feiler)
#   2. installerer avhengigheter på nytt bare når modeling/requirements.txt er endret
#   3. kjører modeling/scripts/publish_forecast.py, som leser .env i repo-roten selv
#   4. pinger valgfri helsesjekk (KLATREFORHOLD_HEALTHCHECK_URL i .env, f.eks. https://hc-ping.com/<uuid>)
# Testmodus: med KLATREFORHOLD_PI_TESTFELT=<slug>[,<slug>...] i .env publiserer Pi-en bare de feltene, ved :15,
# mens Actions fortsatt publiserer alle (se «Testmodus» i README.md).
set -uo pipefail

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
VENV="$REPO/.venv"
cd "$REPO" || exit 1

# Bare helsesjekk-adressen og testfeltet leses her; resten av .env leser Python selv.
les_env() { grep -E "^$1=" .env 2>/dev/null | tail -n1 | cut -d= -f2- | tr -d '"'"'"' '; }
HC="$(les_env KLATREFORHOLD_HEALTHCHECK_URL)"
TESTFELT="$(les_env KLATREFORHOLD_PI_TESTFELT | tr ',' ' ')"
ping_hc() { [ -n "$HC" ] && curl -fsS -m 10 --retry 3 -o /dev/null "$HC$1" || true; }

ping_hc /start

if ! git pull -q --ff-only; then
    echo "Advarsel: klarte ikke å hente ny kode (nett eller lokale endringer). Kjører gjeldende versjon $(git rev-parse --short HEAD)."
fi

HASH="$(sha256sum modeling/requirements.txt | cut -d' ' -f1)"
if [ "$(cat "$VENV/.krav" 2>/dev/null)" != "$HASH" ]; then
    echo "requirements.txt er endret, installerer avhengigheter"
    if "$VENV/bin/pip" install -q --prefer-binary -r modeling/requirements.txt; then
        echo "$HASH" > "$VENV/.krav"
    else
        echo "Advarsel: pip install feilet, prøver med installerte pakker"
    fi
fi

cd modeling || exit 1
start=$SECONDS
if [ -n "$TESTFELT" ]; then
    echo "Testmodus: publiserer bare $TESTFELT"
    ARGS=()
    for felt in $TESTFELT; do ARGS+=(--felt "$felt"); done
    "$VENV/bin/python" scripts/publish_forecast.py "${ARGS[@]}"
else
    "$VENV/bin/python" scripts/publish_forecast.py
fi
status=$?
echo "Ferdig med status $status etter $((SECONDS - start)) s (kode $(git rev-parse --short HEAD))"

if [ "$status" -eq 0 ]; then ping_hc ""; else ping_hc /fail; fi
exit "$status"
