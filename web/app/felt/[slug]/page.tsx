import { notFound } from 'next/navigation'
import Feedback from '@/components/Feedback'
import ForecastChart from '@/components/ForecastChart'
import HourStrip from '@/components/HourStrip'
import StatusHero from '@/components/StatusHero'
import { dag, klokke } from '@/lib/api'
import { hentObservasjoner, hentVarsel } from '@/lib/kilde'

export const dynamic = 'force-dynamic'

export default async function FeltSide({
  params,
  searchParams,
}: {
  params: Promise<{ slug: string }>
  searchParams: Promise<{ na?: string }>
}) {
  const { slug } = await params
  const { na } = await searchParams // ?na=2026-10-03T15:00 for å se på en gammel dag (testing)
  const [varsel, obs] = await Promise.all([hentVarsel(slug, na), hentObservasjoner(slug)])
  if (!varsel) notFound()

  // Tidsvindu i timestripen og grafene: litt historikk (for å forklare hvorfor det er vått nå) og mest framover
  const TIMER_BAK = 5
  const TIMER_FRAM = 19
  const bak = varsel.siste_timer.slice(-TIMER_BAK)
  const vindu = [...bak, ...varsel.timer.slice(0, TIMER_FRAM + 1)]

  return (
    <div className="flex flex-col gap-md">
      <div>
        <h1 className="font-mabry text-[32px] leading-tight">{varsel.felt.navn}</h1>
        <p className="text-sm text-text-subtle">
          Varsel for {dag(varsel.na)} kl {klokke(varsel.na)} · {varsel.kilde}
          {varsel.ml_modell ? ' · med ML-modell' : ' · fysisk modell'}
        </p>
      </div>
      {varsel.utdatert && (
        <p className="rounded-lg border border-state-warning bg-state-warning-tinted p-sm text-sm">
          Varselet ble sist oppdatert {dag(varsel.generert)} kl {klokke(varsel.generert)}. Timesjobben har kanskje stoppet.
        </p>
      )}
      <StatusHero varsel={varsel} />
      <Feedback slug={slug} na={varsel.timer[0]} />
      <HourStrip timer={vindu} naIndeks={bak.length} />
      <ForecastChart timer={vindu} naIndeks={bak.length} />
      <section className="rounded-xl border border-border-subtle bg-surface-default p-md text-sm">
        <h2 className="h3">Tilbakemeldinger</h2>
        {obs && obs.antall > 0 ? (
          <>
            <p className="mt-xs text-text-subtle">
              {obs.antall} observasjoner
              {obs.andel_riktig !== null && `, varselet stemte ${Math.round(obs.andel_riktig * 100)} % av gangene (tørt mot ikke tørt)`}.
            </p>
            <ul className="mt-sm flex flex-col gap-xs">
              {obs.observasjoner.map((o) => (
                <li key={`${o.time}-${o.status}-${o.kommentar}`} className="flex gap-sm">
                  <span className="text-text-subtle">{dag(o.time)} {klokke(o.time)}</span>
                  <span>{o.status === 'tort' ? 'Tørt' : o.status === 'fuktig' ? 'Fuktig' : 'Vått'}</span>
                  {o.riktig !== '' && <span>{Number(o.riktig) === 1 ? '✓' : '✗'}</span>}
                  {o.kommentar && <span className="text-text-subtle">«{o.kommentar}»</span>}
                </li>
              ))}
            </ul>
          </>
        ) : (
          <p className="mt-xs text-text-subtle">Ingen tilbakemeldinger ennå. Bli den første!</p>
        )}
      </section>
      <p className="text-xs text-text-subtle">{varsel.forbehold}</p>
    </div>
  )
}
