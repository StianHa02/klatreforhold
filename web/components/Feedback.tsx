'use client'

import { useRouter } from 'next/navigation'
import { useState } from 'react'
import { type Status, type Time, klokke } from '@/lib/api'

type Valg = Exclude<Status, 'is'>
const VALG: { verdi: Valg; tekst: string; farge: string }[] = [
  { verdi: 'tort', tekst: 'Tørt', farge: 'bg-forhold-tort' },
  { verdi: 'fuktig', tekst: 'Fuktig', farge: 'bg-forhold-fuktig' },
  { verdi: 'vatt', tekst: 'Vått', farge: 'bg-forhold-vatt' },
]

// Brukeren forteller hvordan det faktisk var. Vi sender med hva varselet sa for samme time,
// så API-et kan regne ut hvor ofte varselet stemmer, og observasjonen blir treningsdata.
export default function Feedback({ slug, na, siste }: { slug: string; na: Time; siste: Time[] }) {
  const router = useRouter()
  const valgbareTimer = [na, ...[...siste].reverse()]
  const [tid, setTid] = useState(na.tid)
  const [kommentar, setKommentar] = useState('')
  const [sender, setSender] = useState(false)
  const [svar, setSvar] = useState<{ ok: boolean; tekst: string } | null>(null)
  const valgtTime = valgbareTimer.find((t) => t.tid === tid) ?? na

  async function send(status: Valg) {
    setSender(true)
    setSvar(null)
    try {
      const res = await fetch(`/api/felt/${slug}/observasjoner`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        // tidsstempelet er slutten av timen; vi lagrer midt i timen
        body: JSON.stringify({
          status,
          tid: new Date(new Date(valgtTime.tid).getTime() - 30 * 60 * 1000).toISOString(),
          predikert_status: valgtTime.status,
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
      <h2 className="font-medium">Stemmer varselet?</h2>
      <p className="mt-xs text-sm text-text-subtle">
        Er du på feltet, eller var du der nylig? Si hvordan fjellet faktisk var. Det er dette modellen lærer av.
      </p>
      <label className="mt-md flex flex-col gap-xs text-sm">
        Når var du der?
        <select
          className="rounded-md border border-border-default bg-surface-default p-sm"
          value={tid}
          onChange={(e) => setTid(e.target.value)}
        >
          {valgbareTimer.map((t, i) => (
            <option key={t.tid} value={t.tid}>
              {i === 0 ? 'Nå' : `kl ${klokke(new Date(new Date(t.tid).getTime() - 3600e3).toISOString())}–${klokke(t.tid)}`} (varsel: {t.status_tekst.toLowerCase()})
            </option>
          ))}
        </select>
      </label>
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
      <div className="mt-md grid grid-cols-3 gap-sm">
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
