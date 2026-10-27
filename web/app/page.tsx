import { hentFelt } from '@/lib/kilde'

export const dynamic = 'force-dynamic'

export default async function Home() {
  const felt = await hentFelt()
  if (!felt) {
    return (
      <p className="rounded-xl border border-border-subtle bg-surface-default p-md text-sm">
        Fant ingen varsler. Har timesjobben kjørt, og er SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY satt (eller kjører Python-API-et lokalt)?
      </p>
    )
  }
  return (
    <div className="flex flex-col gap-md">
      <div>
        <h1 className="font-mabry text-[32px] leading-tight">Felt</h1>
        <p className="byline">Er fjellet tørt? Varsel time for time for klatrefelt i Bergen.</p>
      </div>
      <ul className="flex flex-col gap-sm">
        {felt.map((f) => (
          <li key={f.slug}>
            <a
              href={`/felt/${f.slug}`}
              className="focus flex items-center justify-between gap-md rounded-xl border border-border-subtle bg-surface-default p-md transition hover:bg-surface-tinted hover:shadow-sm"
            >
              <span>
                <span className="h3">{f.navn}</span>
                <span className="ml-sm text-sm text-text-subtle">vender mot {f.orientering}°</span>
              </span>
              <span aria-hidden className="text-text-subtle">→</span>
            </a>
          </li>
        ))}
      </ul>
    </div>
  )
}
