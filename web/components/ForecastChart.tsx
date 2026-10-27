import { type Time, klokke } from '@/lib/api'

// Enkel SVG-graf uten avhengigheter: vann på veggen (felt), regn mot veggen (søyler),
// og bergtemperatur mot duggpunkt (linjer).
export default function ForecastChart({ timer }: { timer: Time[] }) {
  const W = 760
  const H = 150
  const pad = { l: 52, r: 8, t: 12, b: 22 }
  const n = timer.length
  const x = (i: number) => pad.l + (i / Math.max(n - 1, 1)) * (W - pad.l - pad.r)
  const maxWater = Math.max(0.2, ...timer.map((t) => t.vann_mm))
  const maxRain = Math.max(0.5, ...timer.map((t) => t.regn_mot_veggen_mm))
  const yW = (v: number) => H - pad.b - (v / maxWater) * (H - pad.t - pad.b)
  const yR = (v: number) => H - pad.b - (v / maxRain) * (H - pad.t - pad.b)
  const temps = timer.flatMap((t) => [t.bergtemp, t.duggpunkt])
  const tMin = Math.floor(Math.min(...temps) - 1)
  const tMax = Math.ceil(Math.max(...temps) + 1)
  const yT = (v: number) => H - pad.b - ((v - tMin) / (tMax - tMin)) * (H - pad.t - pad.b)
  const line = (f: (t: Time) => number, y: (v: number) => number) =>
    timer.map((t, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(f(t)).toFixed(1)}`).join(' ')
  const area = `${line((t) => t.vann_mm, yW)} L${x(n - 1)},${H - pad.b} L${x(0)},${H - pad.b} Z`
  const bw = Math.max(2, (W - pad.l - pad.r) / n - 3)
  const ticks = timer.map((t, i) => ({ i, t })).filter(({ i }) => i % 3 === 0)

  return (
    <section className="rounded-xl bg-surface-default p-md shadow-sm">
      <h2 className="mb-sm font-medium">Vann på veggen</h2>
      <div className="overflow-x-auto"><svg viewBox={`0 0 ${W} ${H}`} className="w-full min-w-[36rem]" role="img" aria-label="Vann på veggen og regn mot veggen">
        {timer.map((t, i) => (
          <rect key={t.tid} x={x(i) - bw / 2} y={yR(t.regn_mot_veggen_mm)} width={bw}
                height={H - pad.b - yR(t.regn_mot_veggen_mm)} fill="var(--color-accent-blue-200)" />
        ))}
        <path d={area} fill="var(--color-accent-blue-400)" fillOpacity={0.35} stroke="var(--color-accent-blue-400)" />
        <line x1={pad.l} x2={W - pad.r} y1={H - pad.b} y2={H - pad.b} stroke="var(--color-light-800)" />
        <text x={2} y={pad.t + 8} fontSize={10} fill="var(--color-dark-200)">{maxWater.toFixed(2)} mm</text>
        {ticks.map(({ i, t }) => (
          <text key={t.tid} x={x(i)} y={H - 6} fontSize={10} textAnchor="middle" fill="var(--color-dark-200)">
            {klokke(t.tid).slice(0, 2)}
          </text>
        ))}
      </svg></div>
      <p className="mt-xs text-xs text-text-subtle">Felt: modellert vann på flaten og i tak/sprekker. Søyler: regn som treffer veggen.</p>

      <h2 className="mb-sm mt-md font-medium">Bergtemperatur og duggpunkt</h2>
      <div className="overflow-x-auto"><svg viewBox={`0 0 ${W} ${H}`} className="w-full min-w-[36rem]" role="img" aria-label="Bergtemperatur og duggpunkt">
        <path d={line((t) => t.bergtemp, yT)} fill="none" stroke="var(--color-accent-red-400)" strokeWidth={2} />
        <path d={line((t) => t.duggpunkt, yT)} fill="none" stroke="var(--color-accent-blue-400)" strokeWidth={2} strokeDasharray="4 3" />
        <line x1={pad.l} x2={W - pad.r} y1={H - pad.b} y2={H - pad.b} stroke="var(--color-light-800)" />
        <text x={2} y={pad.t + 8} fontSize={10} fill="var(--color-dark-200)">{tMax}°</text>
        <text x={2} y={H - pad.b} fontSize={10} fill="var(--color-dark-200)">{tMin}°</text>
        {ticks.map(({ i, t }) => (
          <text key={t.tid} x={x(i)} y={H - 6} fontSize={10} textAnchor="middle" fill="var(--color-dark-200)">
            {klokke(t.tid).slice(0, 2)}
          </text>
        ))}
      </svg></div>
      <p className="mt-xs text-xs text-text-subtle">
        <span className="text-[color:var(--color-accent-red-400)]">━</span> berget (modell){' '}
        <span className="text-[color:var(--color-accent-blue-400)]">┅</span> duggpunkt. Er berget kaldere enn duggpunktet, kondenserer det vann på det.
      </p>
    </section>
  )
}
