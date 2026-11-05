#!/usr/bin/env bash
# Setter opp timesjobben på en Raspberry Pi med Raspberry Pi OS Lite (64-bit). Kjør som vanlig bruker fra repoet:
#   bash drift/raspberrypi/installer.sh
# Trygt å kjøre på nytt. Første gang lages .env, som må fylles inn før skriptet kjøres igjen.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
BRUKER="$(id -un)"
VENV="$REPO/.venv"
HER="$REPO/drift/raspberrypi"

if [ "$(id -u)" -eq 0 ]; then
    echo "Kjør som vanlig bruker, ikke med sudo. Skriptet bruker sudo der det trengs."; exit 1
fi
if [ "$(uname -m)" != "aarch64" ]; then
    echo "Advarsel: $(uname -m), ikke aarch64. Bruk 64-bit Raspberry Pi OS, ellers kan pip måtte kompilere numpy/scipy i timevis."
fi

echo "== Systempakker"
sudo apt-get update -q
sudo apt-get install -y -q git python3-venv curl

echo "== Python-miljø i $VENV"
[ -x "$VENV/bin/python" ] || python3 -m venv "$VENV"
"$VENV/bin/pip" install -q -U pip
"$VENV/bin/pip" install --prefer-binary -r "$REPO/modeling/requirements.txt"
sha256sum "$REPO/modeling/requirements.txt" | cut -d' ' -f1 > "$VENV/.krav"

echo "== .env"
if [ ! -f "$REPO/.env" ]; then
    cat > "$REPO/.env" <<'EOF'
# Hemmeligheter for timesjobben på Pi-en. Ligger ikke i git. Samme verdier som GitHub-secretsene.
SUPABASE_URL=https://nmiydpcmfxkhtztzgzfx.supabase.co
# Supabase → Project Settings → API Keys → service role (kun server)
SUPABASE_SERVICE_ROLE_KEY=
# E-post eller nettside som kontaktinfo i MET User-Agent
KLATREFORHOLD_CONTACT=
# Valgfri: Frost-klient-ID for stasjonskontroll
FROST_CLIENT_ID=
# Valgfri: helsesjekk som varsler når jobben stopper, f.eks. https://hc-ping.com/<uuid>
KLATREFORHOLD_HEALTHCHECK_URL=
EOF
    chmod 600 "$REPO/.env"
    echo "Laget $REPO/.env. Fyll inn verdiene (nano .env) og kjør dette skriptet på nytt."
    exit 0
fi
chmod 600 "$REPO/.env"
for nokkel in SUPABASE_URL SUPABASE_SERVICE_ROLE_KEY KLATREFORHOLD_CONTACT; do
    if ! grep -qE "^$nokkel=.+" "$REPO/.env"; then
        echo "$nokkel mangler i .env. Fyll inn og kjør på nytt."; exit 1
    fi
done
if grep -qE '^KLATREFORHOLD_KILDE=dev' "$REPO/.env"; then
    echo "Advarsel: .env har KLATREFORHOLD_KILDE=dev (utviklingsoppsett). Det trengs ikke på Pi-en."
fi

echo "== Prøvekjøring (--dry-run, skriver ingenting til Supabase)"
if (cd "$REPO/modeling" && "$VENV/bin/python" scripts/publish_forecast.py --dry-run > /tmp/klatreforhold-prove.json); then
    echo "OK"
else
    echo "Prøvekjøringen feilet. Se /tmp/klatreforhold-prove.json og meldingene over."; exit 1
fi

echo "== Begrens loggstørrelsen (sparer SD-kortet)"
sudo mkdir -p /etc/systemd/journald.conf.d
printf '[Journal]\nSystemMaxUse=50M\n' | sudo tee /etc/systemd/journald.conf.d/klatreforhold.conf > /dev/null
sudo systemctl restart systemd-journald

echo "== systemd-timer"
sed -e "s|@BRUKER@|$BRUKER|g" -e "s|@REPO@|$REPO|g" "$HER/klatreforhold-varsel.service" \
    | sudo tee /etc/systemd/system/klatreforhold-varsel.service > /dev/null
sudo cp "$HER/klatreforhold-varsel.timer" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now klatreforhold-varsel.timer

cat <<EOF

Ferdig. Timesjobben kjører hver time ved :07.
  Kjør nå:        sudo systemctl start klatreforhold-varsel.service
  Se loggen:      journalctl -u klatreforhold-varsel -n 100 --no-pager
  Neste kjøring:  systemctl list-timers klatreforhold-varsel.timer
EOF
