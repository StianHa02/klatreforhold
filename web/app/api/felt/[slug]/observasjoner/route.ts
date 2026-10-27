// Tar imot tilbakemeldinger fra nettleseren. Lagrer i Supabase (produksjon) eller via Python-API-et (lokalt).
import { hentObservasjoner, lagreObservasjon } from '@/lib/kilde'

export async function POST(req: Request, { params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params
  let body: unknown
  try {
    body = await req.json()
  } catch {
    return Response.json({ detail: 'Ugyldig JSON' }, { status: 400 })
  }
  try {
    const [status, svar] = await lagreObservasjon(slug, body as Parameters<typeof lagreObservasjon>[1])
    return Response.json(svar, { status })
  } catch (e) {
    console.log(e)
    return Response.json({ detail: 'Klarte ikke å lagre' }, { status: 502 })
  }
}

export async function GET(_req: Request, { params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params
  const obs = await hentObservasjoner(slug)
  return obs ? Response.json(obs) : Response.json({ detail: 'Feil' }, { status: 502 })
}
