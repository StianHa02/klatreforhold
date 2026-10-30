import { cookies } from 'next/headers'
import DagBokser from '@/components/DagBokser'
import VisningsBryter from '@/components/VisningsBryter'
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
  return (
    <div className="flex flex-col gap-md">
      <div>
        <h1 className="font-mabry text-[32px] leading-tight">Felt</h1>
        <p className="byline">Er fjellet tørt? Varsel for nå og fire dager fram.</p>
      </div>
      <VisningsBryter
        start={visning}
        varsel={
          <ul className="flex flex-col gap-sm">
            {varsler.map((v) => (
              <li key={v.felt.slug}>
                <a href={`/felt/${v.felt.slug}`} className="group kort focus flex flex-col transition hover:border-border-tinted">
                  <span className="flex flex-col gap-sm p-sm sm:p-md">
                    <span className="flex items-baseline justify-between gap-md">
                      <span className="font-mabry text-xl leading-tight">{v.felt.navn}</span>
                      <span className="text-sm text-text-subtle">vender mot {v.felt.orientering}°</span>
                    </span>
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
                </a>
              </li>
            ))}
          </ul>
        }
        liste={
          <ul className="flex flex-col gap-sm">
            {varsler.map((v) => (
              <li key={v.felt.slug}>
                <a
                  href={`/felt/${v.felt.slug}`}
                  className="group kort focus flex items-center justify-between gap-md p-md transition hover:border-border-tinted"
                >
                  <span>
                    <span className="h3">{v.felt.navn}</span>
                    <span className="ml-sm text-sm text-text-subtle">vender mot {v.felt.orientering}°</span>
                  </span>
                  <span aria-hidden className="text-text-subtle transition group-hover:translate-x-xs motion-reduce:transition-none">›</span>
                </a>
              </li>
            ))}
          </ul>
        }
      />
    </div>
  )
}
