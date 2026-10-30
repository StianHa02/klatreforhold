'use client'

import { useRouter } from 'next/navigation'
import { type ButtonHTMLAttributes, useMemo, useState } from 'react'
import { type Status, type Time, statusFarge } from '@/lib/api'
import { STATUS_TEKST } from '@/lib/dager'

// Tre valg: is og snø regnes som vått (ingen drar for å klatre på is uansett)
type Valg = Status
const VALG: { verdi: Valg; tekst: string; farge: string }[] = [
  { verdi: 'tort', tekst: 'Tørt', farge: 'bg-forhold-tort' },
  { verdi: 'fuktig', tekst: 'Fuktig', farge: 'bg-forhold-fuktig' },
  { verdi: 'vatt', tekst: 'Vått', farge: 'bg-forhold-vatt' },
]
const TIMER = Array.from({ length: 18 }, (_, i) => i + 6) // kl 06–23

// Dato og time i Oslo, uavhengig av hvilken tidssone nettleseren står i
function osloNa() {
  const p = Object.fromEntries(
    new Intl.DateTimeFormat('en-CA', {
      timeZone: 'Europe/Oslo', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', hourCycle: 'h23',
    }).formatToParts(new Date()).map((x) => [x.type, x.value]),
  )
  return { dato: `${p.year}-${p.month}-${p.day}`, time: Number(p.hour) }
}

const MAKS_DAGER_BAKOVER = 13 // serveren tar imot inntil 14 dager gamle observasjoner

function datoMinusDager(iso: string, dager: number) {
  return new Date(new Date(`${iso}T12:00:00Z`).getTime() - dager * 864e5).toISOString().slice(0, 10)
}

const pad = (h: number) => String(h).padStart(2, '0')

// Brukeren forteller hvordan det faktisk var, for nå eller et tidspunkt de siste dagene.
// Timeknappene har en strek i fargen modellen mener timen hadde (eierens valg fra 2026-10-29; før det
// var varselet skjult for ikke å påvirke svaret, se OVERLEVERING §8). Serveren slår opp varselet
// for samme time i varselarkivet og regner ut om det stemte.
export default function Feedback({ slug, na, statusPerTime = {} }: {
  slug: string
  na: Time
  statusPerTime?: Record<string, Status> // nøkkel «YYYY-MM-DDTHH» i norsk tid
}) {
  const router = useRouter()
  const iDagIso = useMemo(() => osloNa().dato, [])
  const tidligst = datoMinusDager(iDagIso, MAKS_DAGER_BAKOVER)
  const iGarIso = datoMinusDager(iDagIso, 1)
  const [dag, setDag] = useState(iDagIso)
  const [annenDag, setAnnenDag] = useState(false)
  const [time, setTime] = useState<'na' | number>('na')
  const [kommentar, setKommentar] = useState('')
  const [sender, setSender] = useState(false)
  const [svar, setSvar] = useState<{ ok: boolean; tekst: string } | null>(null)
  const iDag = dag === iDagIso
  const naTime = osloNa().time

  function velgDag(v: string) {
    setDag(v)
    if (v === iDagIso || v === iGarIso) setAnnenDag(false)
    if (v === iDagIso) setTime((t) => (t !== 'na' && t > naTime ? 'na' : t))
    else if (time === 'na') setTime(14)
  }

  async function send(status: Valg) {
    setSender(true)
    setSvar(null)
    const erNa = iDag && time === 'na'
    try {
      const res = await fetch(`/api/felt/${slug}/observasjoner`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          status,
          // lokal Oslo-tid midt i timen, uten tidssone; serveren tolker den som Europe/Oslo
          tid: erNa ? null : `${dag}T${String(time === 'na' ? 12 : time).padStart(2, '0')}:30:00`,
          predikert_status: erNa ? na.status : null, // reserve; serveren slår opp i arkivet
          kommentar: kommentar || null,
          kilde: 'web',
        }),
      })
      if (!res.ok) throw new Error(await res.text())
      const data = await res.json()
      const riktig = data.lagret.riktig
      setSvar({
        ok: true,
        tekst: riktig === 1 ? 'Takk! Varselet stemte.' : riktig === 0 ? 'Takk! Varselet bommet, så dette hjelper oss å forbedre det.' : 'Takk!',
      })
      setKommentar('')
      router.refresh()
    } catch (error) {
      console.log(error)
      setSvar({ ok: false, tekst: 'Tilbakemeldingen ble ikke lagret. Prøv igjen.' })
    } finally {
      setSender(false)
    }
  }

  return (
    <section className="kort p-md">
      <h2 className="seksjon">Har du vært der?</h2>
      <fieldset className="mt-sm">
        <legend className="sr-only">Dag</legend>
        <div className="flex flex-wrap border-b-2 border-border-subtle">
          <Fane valgt={iDag && !annenDag} onClick={() => velgDag(iDagIso)}>I dag</Fane>
          <Fane valgt={dag === iGarIso && !annenDag} onClick={() => velgDag(iGarIso)}>I går</Fane>
          <Fane valgt={annenDag} onClick={() => { setAnnenDag(true); if (iDag || dag === iGarIso) velgDag(datoMinusDager(iDagIso, 2)) }}>
            Tidligere
          </Fane>
        </div>
        {annenDag && (
          <label className="mt-sm flex flex-col gap-xs text-sm">
            <span className="text-text-subtle">Dato (inntil {MAKS_DAGER_BAKOVER} dager tilbake)</span>
            <input
              type="date"
              className="focus-box border-2 border-border-default bg-surface-default px-sm py-xs sm:max-w-[16rem]"
              value={dag}
              min={tidligst}
              max={iDagIso}
              required
              onChange={(e) => {
                const v = e.target.value
                if (!v || v < tidligst || v > iDagIso) return // utenfor tillatt periode
                velgDag(v)
              }}
            />
          </label>
        )}
      </fieldset>
      <fieldset className="mt-sm">
        <legend className="mb-xs text-sm">Når på dagen</legend>
        {iDag && (
          <Chip valgt={time === 'na'} onClick={() => setTime('na')} className="mb-xs w-full sm:w-auto">
            Akkurat nå
          </Chip>
        )}
        <div className="grid grid-cols-6 gap-xs sm:grid-cols-9">
          {TIMER.map((h) => {
            const modell = iDag && h > naTime ? undefined : statusPerTime[`${dag}T${pad(h)}`]
            return (
              <Chip
                key={h}
                valgt={time === h}
                disabled={iDag && h > naTime}
                onClick={() => setTime(h)}
                farge={modell}
                aria-label={`kl ${pad(h)}–${pad(h + 1)}${modell ? `, varselet: ${STATUS_TEKST[modell].toLowerCase()}` : ''}`}
              >
                {pad(h)}
              </Chip>
            )
          })}
        </div>
      </fieldset>
      <label className="mt-sm flex flex-col gap-xs text-sm">
        Kommentar (valgfritt)
        <input
          className="focus-box border-2 border-border-default bg-surface-default px-sm py-xs"
          value={kommentar}
          maxLength={500}
          placeholder="F.eks. tørt nederst, fuktig i toppen"
          onChange={(e) => setKommentar(e.target.value)}
        />
      </label>
      <div className="mt-md grid grid-cols-3 gap-sm">
        {VALG.map((v) => (
          <button key={v.verdi} type="button" disabled={sender} onClick={() => send(v.verdi)} className="knapp font-medium">
            <span className={`inline-block h-md w-md rounded-full ${v.farge}`} aria-hidden />
            {v.tekst}
          </button>
        ))}
      </div>
      {svar && <p role="status" className={`mt-sm text-sm ${svar.ok ? 'text-text-tinted' : 'text-state-error'}`}>{svar.tekst}</p>}
    </section>
  )
}

function Fane({ valgt, ...rest }: { valgt: boolean } & ButtonHTMLAttributes<HTMLButtonElement>) {
  return <button type="button" aria-pressed={valgt} className="fane" {...rest} />
}

// Timeknapp i BKK-stil: mørk når valgt, ellers lys med kant. `farge`: strek i modellens status for timen.
function Chip({ valgt, farge, className = '', children, ...rest }: { valgt: boolean; farge?: Status } & ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      type="button"
      aria-pressed={valgt}
      className={`focus cursor-pointer rounded-lg border-2 px-sm py-xs text-sm tabular-nums transition disabled:cursor-default disabled:opacity-40 ${
        valgt
          ? 'border-accent-border-default bg-accent-surface-default text-accent-text-default'
          : 'border-border-default bg-surface-default hover:bg-surface-tinted disabled:hover:bg-surface-default'
      } ${className}`}
      {...rest}
    >
      {children}
      {farge && <span aria-hidden className={`mx-auto mt-[2px] block h-[3px] w-full rounded-full ${statusFarge[farge]}`} />}
    </button>
  )
}
