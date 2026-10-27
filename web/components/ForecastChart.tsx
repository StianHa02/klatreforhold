import { type Time, klokke } from '@/lib/api'

// Enkel SVG-graf uten avhengigheter: vann på veggen (felt), regn mot veggen (søyler),
// og bergtemperatur mot duggpunkt (linjer). Hver graf tegnes i to formater, ett smalt for
// mobil og ett bredt for større skjermer, så teksten holder lesbar størrelse uten scrolling.
type Format = { W: number; H: number; font: number; hvert: number; pad: { l: number; r: number; t: number; b: number } }
const SMAL: Format = { W: 360, H: 180, font: 12, hvert: 6, pad: { l: 44, r: 6, t: 14, b: 24 } }
const BRED: Format = { W: 760, H: 150, font: 10, hvert: 3, pad: { l: 52, r: 8, t: 12, b: 22 } }

function geometri(timer: Time[], { W, H, pad }: Format) {
  const n = timer.length
  const x = (i: number) => pad.l + (i / Math.max(n - 1, 1)) * (W - pad.l - pad.r)
  const bunn = H - pad.b
  const skala = (min: number, max: number) => (v: number) => bunn - ((v - min) / (max - min)) * (H - pad.t - pad.b)
  const line = (f: (t: Time) => number, y: (v: number) => number) =>
    timer.map((t, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(f(t)).toFixed(1)}`).join(' ')
  return { n, x, bunn, skala, line }
}

function Akse({ timer, f, na }: { timer: Time[]; f: Format; na: number }) {
  const { x, bunn } = geometri(timer, f)
  return (
    <>
      <line x1={f.pad.l} x2={f.W - f.pad.r} y1={bunn} y2={bunn} stroke="var(--color-light-800)" />
      {na > 0 && (
        <>
          <line x1={x(na)} x2={x(na)} y1={f.pad.t} y2={bunn} stroke="var(--color-dark-200)" strokeDasharray="3 3" />
          <text x={x(na) + 3} y={f.pad.t + f.font * 0.8} fontSize={f.font} fill="var(--color-dark-200)">nå</text>
        </>
      )}
      {timer.map((t, i) =>
        (i - na) % f.hvert === 0 ? (
          <text key={t.tid} x={x(i)} y={f.H - 6} fontSize={f.font} textAnchor="middle" fill="var(--color-dark-200)">
            {klokke(t.tid).slice(0, 2)}
          </text>
        ) : null,
      )}
    </>
  )
}

function VannGraf({ timer, f, na }: { timer: Time[]; f: Format; na: number }) {
  const { n, x, bunn, skala, line } = geometri(timer, f)
  const maxWater = Math.max(0.2, ...timer.map((t) => t.vann_mm))
  const maxRain = Math.max(0.5, ...timer.map((t) => t.regn_mot_veggen_mm))
  const yW = skala(0, maxWater)
  const yR = skala(0, maxRain)
  const area = `${line((t) => t.vann_mm, yW)} L${x(n - 1)},${bunn} L${x(0)},${bunn} Z`
  const bw = Math.max(2, (f.W - f.pad.l - f.pad.r) / n - 2)
  return (
    <svg viewBox={`0 0 ${f.W} ${f.H}`} className="w-full" role="img" aria-label="Vann på veggen og regn mot veggen">
      {timer.map((t, i) => (
        <rect key={t.tid} x={x(i) - bw / 2} y={yR(t.regn_mot_veggen_mm)} width={bw}
              height={bunn - yR(t.regn_mot_veggen_mm)} fill="var(--color-accent-blue-200)" />
      ))}
      <path d={area} fill="var(--color-accent-blue-400)" fillOpacity={0.35} stroke="var(--color-accent-blue-400)" />
      <text x={2} y={f.pad.t + f.font * 0.8} fontSize={f.font} fill="var(--color-dark-200)">{maxWater.toFixed(2)} mm</text>
      <Akse timer={timer} f={f} na={na} />
    </svg>
  )
}

function TempGraf({ timer, f, na }: { timer: Time[]; f: Format; na: number }) {
  const { bunn, skala, line } = geometri(timer, f)
  const temps = timer.flatMap((t) => [t.bergtemp, t.duggpunkt])
  const tMin = Math.floor(Math.min(...temps) - 1)
  const tMax = Math.ceil(Math.max(...temps) + 1)
  const yT = skala(tMin, tMax)
  return (
    <svg viewBox={`0 0 ${f.W} ${f.H}`} className="w-full" role="img" aria-label="Bergtemperatur og duggpunkt">
      <path d={line((t) => t.bergtemp, yT)} fill="none" stroke="var(--color-accent-red-400)" strokeWidth={2} />
      <path d={line((t) => t.duggpunkt, yT)} fill="none" stroke="var(--color-accent-blue-400)" strokeWidth={2} strokeDasharray="4 3" />
      <text x={2} y={f.pad.t + f.font * 0.8} fontSize={f.font} fill="var(--color-dark-200)">{tMax}°</text>
      <text x={2} y={bunn} fontSize={f.font} fill="var(--color-dark-200)">{tMin}°</text>
      <Akse timer={timer} f={f} na={na} />
    </svg>
  )
}

// Smal graf under sm-brekkpunktet, bred over
function Responsiv({ timer, Graf, na }: { timer: Time[]; Graf: typeof VannGraf; na: number }) {
  return (
    <>
      <div className="sm:hidden"><Graf timer={timer} f={SMAL} na={na} /></div>
      <div className="hidden sm:block"><Graf timer={timer} f={BRED} na={na} /></div>
    </>
  )
}

export default function ForecastChart({ timer, naIndeks = 0 }: { timer: Time[]; naIndeks?: number }) {
  return (
    <section className="rounded-xl border border-border-subtle bg-surface-default p-md">
      <h2 className="h3 mb-sm">Vann på veggen</h2>
      <Responsiv timer={timer} Graf={VannGraf} na={naIndeks} />
      <p className="mt-xs text-xs text-text-subtle">Felt: modellert vann på flaten og i tak/sprekker. Søyler: regn som treffer veggen.</p>

      <h2 className="h3 mb-sm mt-md">Bergtemperatur og duggpunkt</h2>
      <Responsiv timer={timer} Graf={TempGraf} na={naIndeks} />
      <p className="mt-xs text-xs text-text-subtle">
        <span className="text-[color:var(--color-accent-red-400)]">━</span> berget (modell){' '}
        <span className="text-[color:var(--color-accent-blue-400)]">┅</span> duggpunkt. Er berget kaldere enn duggpunktet, kondenserer det vann på det.
      </p>
    </section>
  )
}
