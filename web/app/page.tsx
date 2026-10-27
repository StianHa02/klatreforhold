import { hentFelt } from '@/lib/kilde'

export const dynamic = 'force-dynamic'

export default async function Home() {
  const felt = await hentFelt()
  if (!felt) {
    return <p>Fant ingen varsler. Har timesjobben kjørt, og er SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY satt (eller kjører Python-API-et lokalt)?</p>
  }
  return (
    <div className="flex flex-col gap-md">
      <h1 className="text-xl font-medium">Felt</h1>
      <ul className="flex flex-col gap-sm">
        {felt.map((f) => (
          <li key={f.slug}>
            <a
              href={`/felt/${f.slug}`}
              className="block rounded-lg bg-surface-default p-md shadow-sm hover:bg-surface-hover"
            >
              <span className="font-medium">{f.navn}</span>
              <span className="ml-sm text-sm text-text-subtle">vender mot {f.orientering}°</span>
            </a>
          </li>
        ))}
      </ul>
    </div>
  )
}
