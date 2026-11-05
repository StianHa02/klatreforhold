# Timesjobben på Raspberry Pi

Pi-en kjører `modeling/scripts/publish_forecast.py` hver time ved :07 med en systemd-timer, i stedet for
GitHub Actions. Hver kjøring henter siste kode fra `main`, installerer avhengigheter på nytt bare når
`modeling/requirements.txt` er endret, og skriver til Supabase som før. Nettsiden på Vercel merker ingen forskjell.
Actions-workflowen er reserve: Supabase Cron starter den bare når Pi-en har stoppet (se under).
Hver natt ved 03:37 eksporterer Pi-en også varselarkivet til Parquet ([Parquet-arkivet](../../docs/ARKIV.md)).

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
bash drift/raspberrypi/installer.sh      # installerer, prøvekjører (--dry-run) og starter timerne
```

Første installasjon av Python-pakkene tar en stund på en 3B. Prøvekjøringen henter ekte vær, men skriver ingenting.
Prøvekjøringen av arkivet skriver bare Parquet-filer i `modeling/data/arkiv/` og krever migrasjonen
`20261105150000_parquet_arkiv.sql` i Supabase.

`.env` (ikke i git, `chmod 600`):

| Navn | Bruk |
|---|---|
| `SUPABASE_URL` | Prosjektets URL (fylt inn) |
| `SUPABASE_SERVICE_ROLE_KEY` | Servernøkkel for lagring |
| `KLATREFORHOLD_CONTACT` | Kontaktadresse/nettside i MET User-Agent |
| `FROST_CLIENT_ID` | Valgfri: stasjonskontroll |
| `KLATREFORHOLD_HEALTHCHECK_URL` | Valgfri: f.eks. `https://hc-ping.com/<uuid>` fra healthchecks.io (gratis). Gir e-post når jobben feiler eller uteblir |
| `KLATREFORHOLD_ARKIV_HEALTHCHECK_URL` | Valgfri: egen sjekk med daglig periode for den nattlige Parquet-eksporten |

## 3. Reserve i GitHub Actions

Workflowen har ikke `schedule`. Supabase Cron-jobben `start-varsel-jobb`
([`supabase/valgfritt/cron_starter_github_jobb.sql`](../../supabase/valgfritt/cron_starter_github_jobb.sql))
sjekker hver time ved :05 om varselet er ferskt. Er det nyeste varselet eldre enn 90 minutter, har Pi-en hoppet
over en kjøring, og jobben starter workflowen. Mens Pi-en går, gjør jobben ingenting, så hver time publiseres
bare én gang. Ikke slå av jobben; den er reserven.

**Overgang:** fram til Pi-en kjører, står jobben i overgangsmodus og starter Actions hver time uansett
(`start_varsel_jobb(interval '0 minutes')`). Ellers ville reserven hoppet over annenhver time, siden varselet
fra forrige Actions-kjøring bare er en time gammelt.

### Bytt til reservemodus når Pi-en kjører

Vent til Pi-en har publisert et par timer på rad (`journalctl -u klatreforhold-varsel`), og kjør i
Supabase SQL Editor:

```sql
select cron.schedule('start-varsel-jobb', '5 * * * *', 'select public.start_varsel_jobb()');
```

Fram til da publiseres hver time to ganger (Actions ved :05, Pi-en ved :07). Det er ufarlig: den siste
overskriver `varsel_siste`, og arkivet får bare en ekstra kjøring.

## Daglig drift

```sh
systemctl list-timers klatreforhold-varsel.timer        # neste og forrige kjøring
sudo systemctl start klatreforhold-varsel.service       # kjør nå
journalctl -u klatreforhold-varsel -n 100 --no-pager    # siste logg
journalctl -u klatreforhold-varsel --since today | grep -i -E "feil|advarsel"

systemctl list-timers klatreforhold-arkiv.timer         # Parquet-eksporten, hver natt 03:37
sudo systemctl start klatreforhold-arkiv.service        # eksporter nå
journalctl -u klatreforhold-arkiv -n 100 --no-pager     # én linje per eksportert døgn
```

Kontroller i Supabase at `select felt, generert from public.varsel_siste;` er fersk.
Banneret om gammelt varsel på nettsiden (over 3 timer) er også et tegn på at Pi-en har stoppet.

- **Strømbrudd:** `Persistent=true` kjører en tapt kjøring rett etter oppstart.
- **Kodeendringer:** push til `main`, så bruker neste kjøring ny kode. Endringer i `.service`/`.timer`
  krever at `installer.sh` kjøres på nytt.
- **Lokale endringer på Pi-en** stopper `git pull`; jobben kjører da gjeldende versjon og skriver en advarsel.
  Ikke rediger sporede filer på Pi-en.
- **Logg** er begrenset til 50 MB (journald), og vær-cachen ligger i `modeling/data/cache/`.
- **Parquet-arkivet** ligger lokalt i `modeling/data/arkiv/` (ca. 70–150 MB/år, anslag) og i Storage-bøtta
  `arkiv`. Stopper eksporten, sletter ikke ryddingen noe, men databasen vokser. Se [ARKIV](../../docs/ARKIV.md).
- **Minne:** 3B har 1 GB. Minnebruken med ni felt og ekte vær er ikke målt på Pi-en ennå. Hvis loggen viser
  `Killed`/OOM, øk swap (se Raspberry Pi-dokumentasjonen for gjeldende OS).
- **Sikkerhet:** service role-nøkkelen gir full tilgang til databasen. Hold Pi-en oppdatert
  (`sudo apt full-upgrade`), bruk SSH-nøkkel og ikke åpne porter mot internett. Pi-en trenger bare utgående trafikk.

## Avinstaller

```sh
sudo systemctl disable --now klatreforhold-varsel.timer klatreforhold-arkiv.timer
sudo rm /etc/systemd/system/klatreforhold-{varsel,arkiv}.{service,timer} /etc/systemd/journald.conf.d/klatreforhold.conf
sudo systemctl daemon-reload
```

Supabase Cron-jobben starter da Actions hver time av seg selv, siden varselet blir gammelt.
Parquet-eksporten har ingen reserve i Actions: kjør den fra en annen maskin
(`python scripts/eksporter_arkiv.py`), ellers slutter ryddingen og databasen vokser.
