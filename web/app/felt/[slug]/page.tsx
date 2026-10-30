import { notFound } from 'next/navigation'
import Feedback from '@/components/Feedback'
import ForecastChart from '@/components/ForecastChart'
import Historikk from '@/components/Historikk'
import HourStrip from '@/components/HourStrip'
import NesteDogn from '@/components/NesteDogn'
import StatusHero from '@/components/StatusHero'
import { dag, klokke } from '@/lib/api'
import { STATUS_TEKST, dagBokser, statusPerTime } from '@/lib/dager'
import { hentObservasjoner, hentTidligereVarsel, hentVarsel, tolkTid } from '@/lib/kilde'

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
  const naTid = na ? tolkTid(na) : new Date() // tid uten tidssone er norsk tid
  const uke = new Date(naTid.getTime() - 7 * 24 * 3600e3) // historikken: siste 7 døgn
  const [varsel, obs, obsUke, tidligere] = await Promise.all([
    hentVarsel(slug, na),
    hentObservasjoner(slug),
    hentObservasjoner(slug, uke),
    hentTidligereVarsel(slug, uke),
  ])
  if (!varsel) notFound()

  // Tidsvindu i timestripen og grafene: litt historikk (for å forklare hvorfor det er vått nå) og mest framover
  const TIMER_BAK = 5
  const TIMER_FRAM = 19
  const bak = varsel.siste_timer.slice(-TIMER_BAK)
  const vindu = [...bak, ...varsel.timer.slice(0, TIMER_FRAM + 1)]
  const historikk = varsel.historikk ?? varsel.siste_timer
  const framover = varsel.framover ?? varsel.timer

  // Øverst status nå og skjemaet for å si hvordan det var, så time for time, grafene og dagene framover.
  // Siste 7 døgn og listen over tilbakemeldinger står nederst.
  return (
    <div className="flex flex-col gap-md">
      <div>
        <h1 className="font-mabry text-[32px] leading-tight">{varsel.felt.navn}</h1>
        <p className="byline">Oppdatert {dag(varsel.generert)} kl {klokke(varsel.generert)}</p>
      </div>
      {varsel.utdatert && (
        <p className="border border-state-warning bg-state-warning-tinted p-sm text-sm">
          Varselet er ikke oppdatert siden {dag(varsel.generert)} kl {klokke(varsel.generert)}.
        </p>
      )}
      <StatusHero varsel={varsel} bokser={dagBokser(varsel, naTid.getTime())} />
      <Feedback slug={slug} na={varsel.timer[0]} statusPerTime={statusPerTime([...historikk, ...framover.slice(0, 1)])} />
      <HourStrip timer={vindu} naIndeks={bak.length} />
      <ForecastChart timer={vindu} naIndeks={bak.length} />
      <NesteDogn timer={framover} naMs={naTid.getTime()} />
      <Historikk
        timer={historikk}
        naMs={naTid.getTime()}
        tidligere={tidligere}
        obs={(obsUke?.observasjoner ?? []).filter((o) => Date.parse(o.time) <= naTid.getTime())}
      />
      <section className="kort p-sm text-sm sm:p-md">
        <h2 className="seksjon">Tilbakemeldinger</h2>
        {obs && obs.antall > 0 ? (
          <>
            <p className="mt-xs text-text-subtle">
              {obs.antall} tilbakemeldinger
              {obs.andel_riktig !== null && `, varselet stemte ${Math.round(obs.andel_riktig * 100)} % av gangene`}.
            </p>
            <ul className="mt-sm flex flex-col gap-xs">
              {obs.observasjoner.map((o) => (
                <li key={`${o.time}-${o.status}-${o.kommentar}`} className="flex flex-wrap gap-x-sm">
                  <span className="text-text-subtle">{dag(o.time)} {klokke(o.time)}</span>
                  <span>{STATUS_TEKST[o.status]}</span>
                  {o.riktig !== '' && <span>{Number(o.riktig) === 1 ? '✓' : '✗'}</span>}
                  {o.kommentar && <span className="text-text-subtle">«{o.kommentar}»</span>}
                </li>
              ))}
            </ul>
          </>
        ) : (
          <p className="mt-xs text-text-subtle">Ingen tilbakemeldinger ennå. Har du vært der, si fra over.</p>
        )}
      </section>
    </div>
  )
}
