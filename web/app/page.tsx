import { cookies } from 'next/headers'
import DagBokser from '@/components/DagBokser'
import VisningsBryter from '@/components/VisningsBryter'
import { dag, klokke } from '@/lib/api'
import { dagBokser, kompass } from '@/lib/dager'
import { hentOversikt } from '@/lib/kilde'

export const dynamic = 'force-dynamic'

export default async function Home() {
  const varsler = await hentOversikt()
  if (!varsler) {
    return (
      <p className="rounded-xl border border-border-subtle bg-surface-default p-md text-sm">
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
        <p className="byline">Er fjellet tørt? Varsel for nå og fire dager fram for klatrefelt i Bergen.</p>
      </div>
      <VisningsBryter
        start={visning}
        varsel={
          <ul className="flex flex-col gap-sm">
            {varsler.map((v) => (
              <li key={v.felt.slug}>
                <a
                  href={`/felt/${v.felt.slug}`}
                  className="focus flex flex-col gap-sm rounded-xl border border-border-subtle bg-surface-default p-md transition hover:bg-surface-tinted hover:shadow-sm"
                >
                  <span className="flex items-center justify-between gap-md">
                    <span>
                      <span className="h3">{v.felt.navn}</span>
                      <span className="ml-sm text-sm text-text-subtle">
                        vender mot {kompass(v.felt.orientering)} ({v.felt.orientering}°)
                      </span>
                    </span>
                    <span aria-hidden className="text-text-subtle">→</span>
                  </span>
                  <DagBokser bokser={dagBokser(v, naMs)} />
                  {v.utdatert && (
                    <span className="text-xs text-text-subtle">
                      Varselet ble sist oppdatert {dag(v.generert)} kl {klokke(v.generert)}.
                    </span>
                  )}
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
                  className="focus flex items-center justify-between gap-md rounded-xl border border-border-subtle bg-surface-default px-md py-sm transition hover:bg-surface-tinted hover:shadow-sm"
                >
                  <span>
                    <span className="font-medium">{v.felt.navn}</span>
                    <span className="ml-sm text-sm text-text-subtle">vender mot {v.felt.orientering}°</span>
                  </span>
                  <span aria-hidden className="text-text-subtle">→</span>
                </a>
              </li>
            ))}
          </ul>
        }
      />
    </div>
  )
}
