'use client'

import { useRouter } from 'next/navigation'
import { useMemo, useState } from 'react'
import { type Status, type Time } from '@/lib/api'

type Valg = Exclude<Status, 'is'>
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

// Brukeren forteller hvordan det faktisk var, for nå eller et tidspunkt de siste dagene.
// Vi viser IKKE hva varselet sa her, for ikke å påvirke svaret. Serveren slår opp varselet
// for samme time i varselarkivet og regner ut om det stemte.
export default function Feedback({ slug, na }: { slug: string; na: Time }) {
  const router = useRouter()
  const iDagIso = useMemo(() => osloNa().dato, [])
  const tidligst = datoMinusDager(iDagIso, MAKS_DAGER_BAKOVER)
  const [dag, setDag] = useState(iDagIso)
  const [time, setTime] = useState<'na' | number>('na')
  const [kommentar, setKommentar] = useState('')
  const [sender, setSender] = useState(false)
  const [svar, setSvar] = useState<{ ok: boolean; tekst: string } | null>(null)
  const iDag = dag === iDagIso
  const naTime = osloNa().time

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
        tekst: riktig === 1 ? 'Takk! Varselet stemte.' : riktig === 0 ? 'Takk! Varselet bommet, det hjelper oss å forbedre det.' : 'Takk!',
      })
      setKommentar('')
      router.refresh()
    } catch (error) {
      console.log(error)
      setSvar({ ok: false, tekst: 'Noe gikk galt. Prøv igjen.' })
    } finally {
      setSender(false)
    }
  }

  return (
    <section className="rounded-xl bg-surface-default p-md shadow-sm">
      <h2 className="font-medium">Har du vært på feltet?</h2>
      <p className="mt-xs text-sm text-text-subtle">
        Si hvordan fjellet faktisk var, også om det var tørt. Det er dette modellen lærer av.
      </p>
      <div className="mt-md grid grid-cols-1 gap-sm sm:grid-cols-2">
        <label className="flex flex-col gap-xs text-sm">
          Dato
          <input
            type="date"
            className="rounded-md border border-border-default bg-surface-default p-sm"
            value={dag}
            min={tidligst}
            max={iDagIso}
            required
            onChange={(e) => {
              const v = e.target.value
              if (!v || v < tidligst || v > iDagIso) return // utenfor tillatt periode
              setDag(v)
              if (v !== iDagIso && time === 'na') setTime(14)
            }}
          />
        </label>
        <label className="flex flex-col gap-xs text-sm">
          Når
          <select
            className="rounded-md border border-border-default bg-surface-default p-sm"
            value={String(time)}
            onChange={(e) => setTime(e.target.value === 'na' ? 'na' : Number(e.target.value))}
          >
            {iDag && <option value="na">Akkurat nå</option>}
            {TIMER.filter((h) => !iDag || h <= naTime).map((h) => (
              <option key={h} value={h}>
                kl {String(h).padStart(2, '0')}–{String(h + 1).padStart(2, '0')}
              </option>
            ))}
          </select>
        </label>
      </div>
      <label className="mt-sm flex flex-col gap-xs text-sm">
        Kommentar (valgfritt)
        <input
          className="rounded-md border border-border-default bg-surface-default p-sm"
          value={kommentar}
          maxLength={500}
          placeholder="F.eks. tørt nederst, fuktig i toppen"
          onChange={(e) => setKommentar(e.target.value)}
        />
      </label>
      <p className="mt-md text-sm">Hvordan var fjellet?</p>
      <div className="mt-xs grid grid-cols-3 gap-sm">
        {VALG.map((v) => (
          <button
            key={v.verdi}
            type="button"
            disabled={sender}
            onClick={() => send(v.verdi)}
            className="flex items-center justify-center gap-sm rounded-lg border border-border-default p-sm font-medium hover:bg-surface-hover focus-visible:outline-2 focus-visible:outline-focus disabled:opacity-50"
          >
            <span className={`inline-block h-md w-md rounded-full ${v.farge}`} aria-hidden />
            {v.tekst}
          </button>
        ))}
      </div>
      {svar && <p className={`mt-sm text-sm ${svar.ok ? 'text-text-tinted' : 'text-focus'}`}>{svar.tekst}</p>}
    </section>
  )
}
