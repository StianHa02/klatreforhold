# Timesjobben på Raspberry Pi

Pi-en kjører `modeling/scripts/publish_forecast.py` hver time ved :07 med en systemd-timer, i stedet for
GitHub Actions. Hver kjøring henter siste kode fra `main`, installerer avhengigheter på nytt bare når
`modeling/requirements.txt` er endret, og skriver til Supabase som før. Nettsiden på Vercel merker ingen forskjell.
Actions-workflowen er beholdt som reserve og startes bare for hånd.

Laget for Raspberry Pi 3B (1 GB), Raspberry Pi OS Lite **64-bit** (Debian 13 «Trixie», Python 3.13).
32-bit fungerer dårlig: numpy, scipy og scikit-learn kan måtte kompileres på Pi-en.

## 1. Flash SD-kortet

Bruk Raspberry Pi Imager → *Raspberry Pi 3* → *Raspberry Pi OS (other)* → *Raspberry Pi OS Lite (64-bit)*.
Under *Rediger innstillinger*: vertsnavn (f.eks. `klatreforhold`), bruker og passord, Wi-Fi med land `NO`
(eller kabel), tidssone `Europe/Oslo`, og slå på SSH (helst med offentlig nøkkel).
Bruk et A1/A2-kort på minst 32 GB og den offisielle strømforsyningen (2.5 A).

## 2. Installer

```sh
ssh <bruker>@klatreforhold.local
sudo apt update && sudo apt full-upgrade -y && sudo apt install -y git
git clone https://github.com/StianHa02/klatreforhold.git
cd klatreforhold
bash drift/raspberrypi/installer.sh      # første gang: lager .env og stopper
nano .env                                # fyll inn samme verdier som GitHub-secretsene
bash drift/raspberrypi/installer.sh      # installerer, prøvekjører (--dry-run) og starter timeren
```

Første installasjon av Python-pakkene tar en stund på en 3B. Prøvekjøringen henter ekte vær, men skriver ingenting.

`.env` (ikke i git, `chmod 600`):

| Navn | Bruk |
|---|---|
| `SUPABASE_URL` | Prosjektets URL (fylt inn) |
| `SUPABASE_SERVICE_ROLE_KEY` | Servernøkkel for lagring |
| `KLATREFORHOLD_CONTACT` | Kontaktadresse/nettside i MET User-Agent |
| `FROST_CLIENT_ID` | Valgfri: stasjonskontroll |
| `KLATREFORHOLD_HEALTHCHECK_URL` | Valgfri: f.eks. `https://hc-ping.com/<uuid>` fra healthchecks.io (gratis). Gir e-post når jobben feiler eller uteblir |

## 3. Bytt over fra Actions

Workflowen har ikke lenger `schedule`, så den kjører ikke av seg selv når denne endringen er pushet.
Kjører begge samtidig, publiseres hver time to ganger. Hvis Supabase Cron er satt opp til å starte
workflowen (`supabase/valgfritt/cron_starter_github_jobb.sql`), slå av den jobben:
`select cron.unschedule('<jobbnavn>');`.

## Daglig drift

```sh
systemctl list-timers klatreforhold-varsel.timer        # neste og forrige kjøring
sudo systemctl start klatreforhold-varsel.service       # kjør nå
journalctl -u klatreforhold-varsel -n 100 --no-pager    # siste logg
journalctl -u klatreforhold-varsel --since today | grep -i -E "feil|advarsel"
```

Kontroller i Supabase at `select felt, generert from public.varsel_siste;` er fersk.
Banneret om gammelt varsel på nettsiden (over 3 timer) er også et tegn på at Pi-en har stoppet.

- **Strømbrudd:** `Persistent=true` kjører en tapt kjøring rett etter oppstart.
- **Kodeendringer:** push til `main`, så bruker neste kjøring ny kode. Endringer i `.service`/`.timer`
  krever at `installer.sh` kjøres på nytt.
- **Lokale endringer på Pi-en** stopper `git pull`; jobben kjører da gjeldende versjon og skriver en advarsel.
  Ikke rediger sporede filer på Pi-en.
- **Logg** er begrenset til 50 MB (journald), og vær-cachen ligger i `modeling/data/cache/`.
- **Minne:** 3B har 1 GB. Minnebruken med ni felt og ekte vær er ikke målt på Pi-en ennå. Hvis loggen viser
  `Killed`/OOM, øk swap (se Raspberry Pi-dokumentasjonen for gjeldende OS).
- **Sikkerhet:** service role-nøkkelen gir full tilgang til databasen. Hold Pi-en oppdatert
  (`sudo apt full-upgrade`), bruk SSH-nøkkel og ikke åpne porter mot internett. Pi-en trenger bare utgående trafikk.

## Avinstaller

```sh
sudo systemctl disable --now klatreforhold-varsel.timer
sudo rm /etc/systemd/system/klatreforhold-varsel.{service,timer} /etc/systemd/journald.conf.d/klatreforhold.conf
sudo systemctl daemon-reload
```

Legg deretter `schedule` tilbake i `.github/workflows/varsel.yml` hvis Actions skal overta igjen.
