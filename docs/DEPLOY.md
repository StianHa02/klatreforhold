# Deploy: én Vercel-side + Supabase + GitHub Actions

Ingen egen API-server. Modellen kjøres én gang i timen av GitHub Actions og skriver til Supabase.
Nettsiden leser derfra. Alt passer i gratisnivåene (Vercel Hobby: ett prosjekt).

```
 GitHub Actions (hvert time, :07)
   python scripts/publish_forecast.py
   henter vær (MET Nordic via Open-Meteo) → kjører modellen
                │ service role key
                ▼
 ┌──────────────────────────────────────────┐
 │ Supabase: klatreforhold (eu-north-1)     │
 │  varsel_siste  siste varsel per felt     │
 │  varsel        arkiv, én rad per time    │
 │  observasjoner brukernes tilbakemeldinger│
 │  RLS på, ingen offentlig tilgang         │
 └──────────────────────────────────────────┘
                ▲ service role key (kun på serveren)
                │
 ┌──────────────────────────────────────────┐
 │ Vercel: Next.js (web/)                   │
 │  leser varsel_siste, lagrer observasjoner│
 └──────────────────────────────────────────┘
```

Supabase-prosjektet finnes allerede: `nmiydpcmfxkhtztzgzfx`, URL `https://nmiydpcmfxkhtztzgzfx.supabase.co`,
med migrasjonene i `supabase/migrations/`.

## 1. GitHub

```powershell
cd $HOME\Documents\klatreforhold
git add .
git commit -m "Første versjon av klatreforhold"
git remote add origin https://github.com/<bruker>/klatreforhold.git
git push -u origin main
```

Repo → Settings → Secrets and variables → Actions → New repository secret:

| Navn | Verdi |
|---|---|
| `SUPABASE_URL` | `https://nmiydpcmfxkhtztzgzfx.supabase.co` |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase → Project Settings → API Keys → secret (service_role) |
| `KLATREFORHOLD_CONTACT` | e-post eller nettside (MET krever kontaktinfo i User-Agent) |

Kjør jobben første gang for hånd: Actions → "Oppdater varsel" → Run workflow. Deretter går den hver time.

## 2. Vercel

1. Add New → Project → velg repoet. **Root Directory: `web`**. Framework: Next.js.
2. Environment Variables:

| Navn | Verdi |
|---|---|
| `SUPABASE_URL` | `https://nmiydpcmfxkhtztzgzfx.supabase.co` |
| `SUPABASE_SERVICE_ROLE_KEY` | samme secret som over. Brukes bare på serveren (ingen `NEXT_PUBLIC_`). |

3. Deploy. Siden viser Ekstraveggen så snart jobben i steg 1 har kjørt.

## 3. Sjekk at det virker

I Supabase SQL Editor:

```sql
select felt, generert from public.varsel_siste;                        -- siste kjøring per felt
select felt, count(*) from public.varsel group by felt;                -- arkivet vokser med ~48 rader per time
select * from public.observasjoner order by registrert desc limit 10;  -- tilbakemeldinger
```

Hvis siden viser et gult banner om at varselet er gammelt, har GitHub-jobben stoppet (se Actions-fanen).

## 4. Trene modell når det har kommet tilbakemeldinger

```powershell
# med SUPABASE_URL og SUPABASE_SERVICE_ROLE_KEY i .env i repo-roten
cd modeling
python scripts\calibrate.py --config config\ekstraveggen.yaml --weather data\raw\<vær>.csv --labels supabase --write
python scripts\export_observations.py
python scripts\train.py --weather data\raw\<vær>.csv --labels data\labels\ekstraveggen_observasjoner_supabase.csv --torch --save
git add models config\kalibrert; git commit -m "Ny modell"; git push
```

Timesjobben på GitHub bruker sklearn-modellen (PyTorch installeres ikke der, for å holde jobben rask).
Vil dere bruke torch-modellen i produksjon, legg `torch` (CPU) til i workflowen.

## Kostnad og grenser

- **Vercel Hobby:** ett prosjekt, ikke-kommersiell bruk.
- **Supabase Free:** godt innenfor (ca. 1 200 rader i varselarkivet per døgn per felt; rydd eldre enn ett år ved behov).
- **GitHub Actions:** gratis i offentlige repo. I private repo inngår 2 000 minutter/mnd; jobben tar 1–2 min,
  altså ca. 700–1 400 min/mnd. Planlagte jobber kan bli forsinket noen minutter, og i offentlige repo
  skrus de av etter 60 dager uten aktivitet i repoet.
- **Open-Meteo:** gratis for ikke-kommersiell bruk; vi bruker 24 kall per felt per døgn.

## Senere: eget API

FastAPI-appen (`app.py`, `src/klatreforhold/api.py`) er fortsatt med for lokal utvikling, og kan deployes
(Vercel, Docker) hvis dere trenger beregninger på forespørsel, f.eks. til nettføreren.
