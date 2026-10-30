// Diagrammer til "Om modellen". Ren SVG, ingen avhengigheter. Hvert diagram tegnes i et smalt
// (mobil) og et bredt format, så tekstene holder lesbar størrelse.
import type { ReactNode } from 'react'

export type Format = { W: number; H: number; font: number; pad: { l: number; r: number; t: number; b: number } }
const SMAL: Format = { W: 360, H: 230, font: 11, pad: { l: 40, r: 10, t: 14, b: 26 } }
const BRED: Format = { W: 720, H: 260, font: 12, pad: { l: 48, r: 110, t: 14, b: 28 } }

export const FELTFARGE: Record<string, { farge: string; strek?: string }> = {
  ekstraveggen: { farge: 'var(--color-dark-400)' },
  helleneset: { farge: 'var(--color-accent-red-400)', strek: '6 4' },
  sandviken: { farge: 'var(--color-accent-blue-400)', strek: '2 3' },
  bolstadoyri: { farge: '#c2378f', strek: '8 3' },
  bymuren: { farge: '#7b45d1', strek: '3 3' },
  fabrikkveggen: { farge: '#0d8076', strek: '8 3 2 3' },
  loddefjord: { farge: '#c26500', strek: '10 3' },
  neseveggen: { farge: '#2f8a1c', strek: '2 2' },
  trollkona: { farge: '#0780a0', strek: '5 2 1 2' },
}
const MND = ['jan', 'feb', 'mar', 'apr', 'mai', 'jun', 'jul', 'aug', 'sep', 'okt', 'nov', 'des']
const RUTE = 'var(--color-light-700)'
const TEKST = 'var(--color-dark-200)'

export function Responsiv({ tegn, label }: { tegn: (f: Format) => ReactNode; label: string }) {
  return (
    <>
      <svg viewBox={`0 0 ${SMAL.W} ${SMAL.H}`} className="w-full sm:hidden" role="img" aria-label={label}>{tegn(SMAL)}</svg>
      <svg viewBox={`0 0 ${BRED.W} ${BRED.H}`} className="hidden w-full sm:block" role="img" aria-label={label}>{tegn(BRED)}</svg>
    </>
  )
}

function YAkse({ f, maks, steg, enhet }: { f: Format; maks: number; steg: number; enhet: (v: number) => string }) {
  const y = (v: number) => f.H - f.pad.b - (v / maks) * (f.H - f.pad.t - f.pad.b)
  const ticks = []
  for (let v = 0; v <= maks + 1e-9; v += steg) ticks.push(v)
  return (
    <>
      {ticks.map((v) => (
        <g key={v}>
          <line x1={f.pad.l} x2={f.W - f.pad.r} y1={y(v)} y2={y(v)} stroke={RUTE} strokeWidth={v === 0 ? 1.2 : 0.6} />
          <text x={f.pad.l - 6} y={y(v) + f.font * 0.35} textAnchor="end" fontSize={f.font} fill={TEKST}>{enhet(v)}</text>
        </g>
      ))}
    </>
  )
}

function MndAkse({ f }: { f: Format }) {
  const x = (i: number) => f.pad.l + ((i + 0.5) / 12) * (f.W - f.pad.l - f.pad.r)
  return (
    <>
      {MND.map((m, i) => (
        <text key={m} x={x(i)} y={f.H - 8} textAnchor="middle" fontSize={f.font} fill={TEKST}>
          {f.W < 500 ? m[0].toUpperCase() : m}
        </text>
      ))}
    </>
  )
}

export type Serie = { slug: string; navn: string; verdier: (number | null)[] }

/** Linjer over årets måneder, f.eks. andel tørre timer. */
export function MaanedLinjer({ serier, maks, steg, enhet, label }: {
  serier: Serie[]; maks: number; steg: number; enhet: (v: number) => string; label: string
}) {
  return (
    <Responsiv label={label} tegn={(f) => {
      const x = (i: number) => f.pad.l + ((i + 0.5) / 12) * (f.W - f.pad.l - f.pad.r)
      const y = (v: number) => f.H - f.pad.b - (v / maks) * (f.H - f.pad.t - f.pad.b)
      const bred = f.W > 500
      // navnelapper til høyre (bredt format), flyttet fra hverandre så de ikke overlapper
      const lapper = serier.map((s) => ({ s, y: y(s.verdier[11] ?? 0) })).sort((a, b) => a.y - b.y)
      for (let i = 1; i < lapper.length; i++) lapper[i].y = Math.max(lapper[i].y, lapper[i - 1].y + f.font + 4)
      return (
        <>
          <YAkse f={f} maks={maks} steg={steg} enhet={enhet} />
          <MndAkse f={f} />
          {serier.map((s) => {
            const st = FELTFARGE[s.slug] ?? { farge: TEKST }
            const d = s.verdier.map((v, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(v ?? 0).toFixed(1)}`).join(' ')
            return (
              <g key={s.slug}>
                <path d={d} fill="none" stroke={st.farge} strokeWidth={2.5} strokeDasharray={st.strek} />
                {s.verdier.map((v, i) => <circle key={i} cx={x(i)} cy={y(v ?? 0)} r={2.5} fill={st.farge} />)}
              </g>
            )
          })}
          {bred && lapper.map(({ s, y: yy }) => (
            <text key={s.slug} x={x(11) + 12} y={yy + f.font * 0.35} fontSize={f.font} fill={FELTFARGE[s.slug]?.farge ?? TEKST}>{s.navn}</text>
          ))}
        </>
      )
    }} />
  )
}

/** Grupperte stolper per måned, én per felt. */
export function MaanedStolper({ serier, maks, steg, enhet, label }: {
  serier: Serie[]; maks: number; steg: number; enhet: (v: number) => string; label: string
}) {
  return (
    <Responsiv label={label} tegn={(f) => {
      const bredde = (f.W - f.pad.l - f.pad.r) / 12
      const bw = Math.min(14, (bredde - 6) / serier.length)
      const y = (v: number) => f.H - f.pad.b - (v / maks) * (f.H - f.pad.t - f.pad.b)
      return (
        <>
          <YAkse f={f} maks={maks} steg={steg} enhet={enhet} />
          <MndAkse f={f} />
          {serier.map((s, k) => (
            <g key={s.slug}>
              {s.verdier.map((v, i) => {
                const x0 = f.pad.l + i * bredde + (bredde - bw * serier.length) / 2 + k * bw
                return <rect key={i} x={x0} y={y(v ?? 0)} width={bw - 1} height={f.H - f.pad.b - y(v ?? 0)}
                             fill={FELTFARGE[s.slug]?.farge ?? TEKST} fillOpacity={k === 0 ? 0.85 : 0.75} />
              })}
            </g>
          ))}
        </>
      )
    }} />
  )
}

export type Spenn = { navn: string; slug: string; median: number; q25: number; q75: number; n: number }

/** Liggende spenn: median (prikk) og midterste halvdel (strek), f.eks. tørketid i timer. */
export function Spenn({ rader, maks, label }: { rader: { gruppe: string; spenn: Spenn[] }[]; maks: number; label: string }) {
  const radH = 22
  const høyde = rader.reduce((n, g) => n + 26 + g.spenn.length * radH, 0) + 30
  const tegn = (W: number, font: number, venstre: number) => {
    const x = (v: number) => venstre + (Math.min(v, maks) / maks) * (W - venstre - 16)
    let yy = 6
    const elementer: ReactNode[] = []
    for (const g of rader) {
      yy += 16
      elementer.push(<text key={`g-${g.gruppe}`} x={0} y={yy} fontSize={font + 1} fontWeight={600} fill="var(--color-dark-400)">{g.gruppe}</text>)
      yy += 10
      for (const s of g.spenn) {
        yy += radH
        const farge = FELTFARGE[s.slug]?.farge ?? TEKST
        elementer.push(
          <g key={`${g.gruppe}-${s.slug}`}>
            <text x={0} y={yy - 6} fontSize={font} fill={TEKST}>{s.navn}</text>
            <line x1={x(s.q25)} x2={x(s.q75)} y1={yy - 10} y2={yy - 10} stroke={farge} strokeWidth={6} strokeLinecap="round" strokeOpacity={0.35} />
            <circle cx={x(s.median)} cy={yy - 10} r={5} fill={farge} />
            <text x={x(s.q75) + 8} y={yy - 6} fontSize={font} fill={TEKST}>{Math.round(s.median)} t</text>
          </g>,
        )
      }
    }
    const aksY = høyde - 12
    for (let v = 0; v <= maks; v += 12) {
      elementer.push(
        <g key={`t-${v}`}>
          <line x1={x(v)} x2={x(v)} y1={10} y2={aksY - 10} stroke={RUTE} strokeWidth={0.6} />
          <text x={x(v)} y={aksY + 4} textAnchor="middle" fontSize={font} fill={TEKST}>{v} t</text>
        </g>,
      )
    }
    return elementer
  }
  return (
    <>
      <svg viewBox={`0 0 360 ${høyde}`} className="w-full sm:hidden" role="img" aria-label={label}>{tegn(360, 11, 96)}</svg>
      <svg viewBox={`0 0 720 ${høyde}`} className="hidden w-full sm:block" role="img" aria-label={label}>{tegn(720, 12, 120)}</svg>
    </>
  )
}

export type SimRad = { n: number; modell: string; snitt: number; min: number; maks: number }

/** Treff etter regn for startverdier og kalibrert modell, ved ulikt antall tilbakemeldinger. */
export function Simulering({ rader, label }: { rader: SimRad[]; label: string }) {
  const modeller = [
    { navn: 'startverdier', tekst: 'Startverdier', farge: 'var(--color-light-900)' },
    { navn: 'kalibrert', tekst: 'Kalibrert', farge: 'var(--color-dark-400)' },
  ]
  const grupper = [...new Set(rader.map((r) => r.n))].sort((a, b) => a - b)
  return (
    <Responsiv label={label} tegn={(f) => {
      const min = 0.5
      const y = (v: number) => f.H - f.pad.b - ((v - min) / (1 - min)) * (f.H - f.pad.t - f.pad.b)
      const gb = (f.W - f.pad.l - f.pad.r) / grupper.length
      const bw = Math.min(56, gb / 3)
      return (
        <>
          <YAkse f={{ ...f, H: f.H }} maks={1} steg={0.1} enhet={() => ''} />
          {[0.5, 0.6, 0.7, 0.8, 0.9, 1].map((v) => (
            <text key={v} x={f.pad.l - 6} y={y(v) + f.font * 0.35} textAnchor="end" fontSize={f.font} fill={TEKST}>{Math.round(v * 100)} %</text>
          ))}
          {grupper.map((n, gi) => (
            <g key={n}>
              <text x={f.pad.l + gi * gb + gb / 2} y={f.H - 8} textAnchor="middle" fontSize={f.font} fill={TEKST}>{n} tilbakemeldinger</text>
              {modeller.map((m, mi) => {
                const r = rader.find((rr) => rr.n === n && rr.modell === m.navn)
                if (!r) return null
                const x0 = f.pad.l + gi * gb + gb / 2 - bw + mi * bw
                return (
                  <g key={m.navn}>
                    <rect x={x0 + 2} y={y(r.snitt)} width={bw - 4} height={f.H - f.pad.b - y(r.snitt)} fill={m.farge} />
                    <line x1={x0 + bw / 2} x2={x0 + bw / 2} y1={y(r.min)} y2={y(r.maks)} stroke="var(--color-accent-red-400)" strokeWidth={1.5} />
                    <text x={x0 + bw / 2} y={y(r.maks) - 5} textAnchor="middle" fontSize={f.font} fill="var(--color-dark-400)">{Math.round(r.snitt * 100)}</text>
                  </g>
                )
              })}
            </g>
          ))}
          {f.W > 500 && modeller.map((m, i) => (
            <g key={m.navn}>
              <rect x={f.W - f.pad.r + 14} y={f.pad.t + 6 + i * 22} width={12} height={12} fill={m.farge} />
              <text x={f.W - f.pad.r + 32} y={f.pad.t + 16 + i * 22} fontSize={f.font} fill={TEKST}>{m.tekst}</text>
            </g>
          ))}
        </>
      )
    }} />
  )
}

/** Fargeforklaring for feltene (vises over diagrammene, og er eneste forklaring på mobil). */
export function FeltForklaring({ felt }: { felt: { slug: string; navn: string }[] }) {
  return (
    <div className="flex flex-wrap gap-x-md gap-y-xs text-sm text-text-subtle">
      {felt.map((f) => {
        const st = FELTFARGE[f.slug] ?? { farge: TEKST }
        return (
          <span key={f.slug} className="flex items-center gap-xs">
            <svg width="22" height="8" aria-hidden><line x1="0" x2="22" y1="4" y2="4" stroke={st.farge} strokeWidth="3" strokeDasharray={st.strek} /></svg>
            {f.navn}
          </span>
        )
      })}
    </div>
  )
}
