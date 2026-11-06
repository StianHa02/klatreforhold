# Parquet-arkivet

Varselarkivet (`varsel`, `stasjon_varsel`) eksporteres hver natt til Parquet, med alle rader og alle ledetider.
Databasen kan da ryddes for å holde seg innenfor gratisnivået uten at data til analyse og trening går tapt.

## Hvorfor

`varsel` vokser med om lag 10 000 rader (ca. 2,2 MB) per døgn: ni felt × 24 kjøringer × 49 ledetider.
Det er ca. 800 MB i året, mot 500 MB på Supabases gratisnivå. `rydd_arkiv()` tynner derfor ut rader
eldre enn 30 dager til ledetid 0, 3, 6, 12, 24 og 48 (pluss alle ledetider ±3 t rundt ekte observasjoner).

Uten arkiv ville de mellomliggende ledetidene vært borte for godt. Varslene kan ikke regnes ut på nytt:
`vaer` lagrer været som faktisk kom, ikke prognosene MET ga da varselet ble laget. Med Parquet-arkivet
beholdes alt, slik at treffsikkerhet kan måles time for time i ledetid, og nye modellversjoner kan
sammenlignes med gamle varsler.

## Slik virker det

```
klatreforhold-arkiv.timer (Pi, 03:37)
  └─ drift/raspberrypi/kjor_arkiv.sh
       └─ modeling/scripts/eksporter_arkiv.py
            for hvert UTC-døgn (etter `generert`) til og med i går uten kvittering:
              1. hent alle rader fra Supabase (PostgREST, 1000 per side)
              2. skriv Parquet til modeling/data/arkiv/<sti>       (kopi 1, SD-kortet på Pi-en)
              3. last opp til Storage-bøtta `arkiv`/<sti>           (kopi 2, Supabase)
              4. last ned igjen, sjekk sha256 og antall rader
              5. skriv kvittering i public.arkiv_eksport
rydd-arkiv (pg_cron, søndager 04:00 UTC)
  └─ rydd_arkiv(): sletter bare rader fra døgn som har kvittering
```

**Garantien:** en rad slettes aldri fra databasen hvis døgnet dens ikke finnes i Storage, kontrollert byte
for byte. Feiler eksporten, eller er Pi-en nede, slettes ingenting. Databasen vokser da bare litt til
eksporten tar igjen det som mangler (neste kjøring tar med alle døgn uten kvittering).

Koden ligger i `modeling/src/klatreforhold/arkiv.py`, og tabellen, bøtta og den nye `rydd_arkiv()` i
`supabase/migrations/20261105150000_parquet_arkiv.sql`.

### Hva som ikke arkiveres

- **`modelltilstand`** ryddes som før (midnattstilstander i 30 dager). Den er et omstartspunkt for modellen,
  ikke måledata, og kan regnes ut på nytt fra `vaer`.
- **`vaer`, `observasjoner`, `stasjon_maling`, `bones_maling`** ryddes aldri, og trengs derfor ikke i arkivet.
- **`varsel_siste`** er bare det siste varselet per felt og overskrives hver time; historikken er `varsel`.

## Filformat

Én fil per tabell og UTC-døgn, etter når varselet ble laget (`generert`), ikke tidspunktet det gjelder (`tid`):

```
varsel/2026-11/varsel_2026-11-04.parquet
stasjon_varsel/2026-11/stasjon_varsel_2026-11-04.parquet
```

Samme sti brukes i bøtta `arkiv` og under `modeling/data/arkiv/` (ikke i git). Filene har zstd-komprimering,
er sortert etter primærnøkkelen (`felt`/`stasjon`, `generert`, `tid`) og har samme kolonner som tabellen,
med typer som i Postgres:

| Postgres | Parquet / pandas |
|---|---|
| `timestamptz` | `timestamp[us, UTC]` |
| `smallint` (`ledetid_timer`) | `Int16` |
| `real` | `float32` |
| `boolean` (`sol_pa_veggen`) | `boolean` |
| `text` | `string` |

En ny kolonne i tabellen kommer automatisk med i nye filer (tall som `float32`, ellers tekst). Eldre filer
mangler den; `pd.concat` gir `NaN` der.

Et døgn uten rader (f.eks. hvis ingenting ble publisert) får verken fil eller kvittering.

## Bruke arkivet til analyse

Last ned arkivet til en annen maskin (krever `SUPABASE_URL` og `SUPABASE_SERVICE_ROLE_KEY` i `.env`):

```sh
cd modeling
python scripts/eksporter_arkiv.py --hent    # henter filer som mangler eller avviker (sha256)
```

```python
from klatreforhold.arkiv import les_arkiv
df = les_arkiv("varsel")                     # alle døgn, alle ledetider
```

Eller direkte med pandas eller DuckDB:

```python
import pandas as pd
df = pd.read_parquet("data/arkiv/varsel")    # pyarrow leser hele mappa
```

```sql
-- duckdb
select ledetid_timer, count(*) from 'data/arkiv/varsel/*/*.parquet' group by 1 order by 1;
```

Arkivet dekker alle ferdige døgn til og med i går. Dagens rader finnes bare i databasen
(`storage.forecast_archive(felt)` eller PostgREST). Bruk ikke både arkivet og databasen for samme døgn
uten å fjerne duplikater: de siste 30 dagene finnes begge steder.

## Drift

```sh
systemctl list-timers klatreforhold-arkiv.timer        # neste og forrige kjøring
sudo systemctl start klatreforhold-arkiv.service       # kjør nå
journalctl -u klatreforhold-arkiv -n 100 --no-pager    # logg: én linje per døgn, rader og kB
```

```sh
cd modeling
python scripts/eksporter_arkiv.py --dry-run            # skriver bare lokale filer, ingenting til Supabase
python scripts/eksporter_arkiv.py --til 2026-11-04     # eksporter bare til og med en dato
python scripts/eksporter_arkiv.py --tabell varsel      # bare én tabell
```

- **Helsesjekk:** sett `KLATREFORHOLD_ARKIV_HEALTHCHECK_URL` i `.env` på Pi-en (f.eks. en egen sjekk på
  healthchecks.io med daglig periode) for e-post når eksporten feiler eller uteblir.
- **Eksportere et døgn på nytt:** slett kvitteringen (`delete from public.arkiv_eksport where tabell = 'varsel'
  and dato = '2026-11-04';`). Neste kjøring lager fila på nytt og overskriver den i bøtta. Gjør det bare for
  døgn som ikke er ryddet ennå (yngre enn 30 dager), ellers blir den nye fila tynnere enn den gamle.
- **Første kjøring** tar med alle døgn siden arkivet startet (27.10.2026).
- **Ny maskin eller nytt SD-kort:** den lokale kopien kan hentes tilbake med `--hent`; bøtta er fasiten.

### Kontroller

```sql
-- døgn med varsler som mangler kvittering (bør bare være i dag)
select (generert at time zone 'UTC')::date as dato, count(*)
from public.varsel v
where not exists (select 1 from public.arkiv_eksport e
                  where e.tabell = 'varsel' and e.dato = (v.generert at time zone 'UTC')::date)
group by 1 order by 1;

-- størrelse på arkivet
select tabell, count(*) as dogn, sum(rader) as rader, pg_size_pretty(sum(bytes)::bigint) as storrelse
from public.arkiv_eksport group by 1;

-- hva rydd_arkiv ville slettet, uten å slette
begin; select public.rydd_arkiv(); rollback;
```

## Kapasitet

Storage på Supabases gratisnivå er 1 GB (se gjeldende [priser](https://supabase.com/pricing)). Hvor mye et
døgn tar i Parquet er ikke målt på ekte data ennå; syntetiske data ga ca. 10 byte per rad, og ekte tall
komprimeres dårligere. Et anslag på 20–40 byte per rad gir 0,2–0,4 MB per døgn, eller 70–150 MB i året.
Mål etter første kjøring med spørringen over. Den lokale kopien på Pi-en tar like mye på SD-kortet.
