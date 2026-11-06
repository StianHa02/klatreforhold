import { cookies } from 'next/headers'
import DagBokser from '@/components/DagBokser'
import FeltOversikt from '@/components/FeltOversikt'
import { dag, klokke } from '@/lib/api'
import { dagBokser } from '@/lib/dager'
import { hentOversikt } from '@/lib/kilde'

export const dynamic = 'force-dynamic'

export default async function Home() {
  const varsler = await hentOversikt()
  if (!varsler) {
    return (
      <p className="kort p-md text-sm">
        Fant ingen varsler. Har timesjobben kjørt, og er SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY satt (eller kjører Python-API-et lokalt)?
      </p>
    )
  }
  const naMs = Date.now()
  const visning = (await cookies()).get('visning')?.value === 'liste' ? 'liste' : 'varsel'
  const felt = varsler.map((v) => ({ slug: v.felt.slug, navn: v.felt.navn, omraade: v.felt.omraade ?? null }))
  const varsel = Object.fromEntries(
    varsler.map((v) => [
      v.felt.slug,
      <a key={v.felt.slug} href={`/felt/${v.felt.slug}`} className="group kort focus flex flex-col transition hover:border-border-tinted">
        <span className="flex flex-col gap-sm p-sm sm:p-md">
          <span className="font-mabry text-xl leading-tight">{v.felt.navn}</span>
          <DagBokser bokser={dagBokser(v, naMs)} />
          {v.utdatert && (
            <span className="text-xs text-text-subtle">
              Ikke oppdatert siden {dag(v.generert)} kl {klokke(v.generert)}.
            </span>
          )}
        </span>
        <span className="flex items-center gap-sm bg-surface-tinted px-md py-sm text-sm">
          <span className="underline decoration-border-strong decoration-2 underline-offset-4">Se varselet</span>
          <span aria-hidden className="transition group-hover:translate-x-sm motion-reduce:transition-none">›</span>
        </span>
      </a>,
    ]),
  )
  const liste = Object.fromEntries(
    varsler.map((v) => [
      v.felt.slug,
      <a
        key={v.felt.slug}
        href={`/felt/${v.felt.slug}`}
        className="group kort focus flex items-center justify-between gap-md p-md transition hover:border-border-tinted"
      >
        <span className="h3">{v.felt.navn}</span>
        <span aria-hidden className="text-text-subtle transition group-hover:translate-x-xs motion-reduce:transition-none">›</span>
      </a>,
    ]),
  )
  return (
    <div className="flex flex-col gap-md">
      <div>
        <h1 className="font-mabry text-[32px] leading-tight">Felt</h1>
        <p className="byline">Er fjellet tørt? Varsel for nå og fire dager fram.</p>
      </div>
      <FeltOversikt felt={felt} start={visning} varsel={varsel} liste={liste} />
    </div>
  )
}
