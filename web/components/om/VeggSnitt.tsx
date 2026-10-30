// Tverrsnitt av en klatrevegg: hvor vannet kommer fra og hvor det blir av.
// Tallene i tegningen viser til lista under (de er referanser, ikke en rekkefølge).
const BLÅ = 'var(--color-accent-blue-400)'
const BLÅ_LYS = 'var(--color-accent-blue-200)'
const RØD = 'var(--color-accent-red-400)'
const GUL = 'var(--color-accent-yellow-400)'
const BLEKK = 'var(--color-dark-400)'
const DEMPET = 'var(--color-dark-200)'

function Merke({ x, y, n }: { x: number; y: number; n: number }) {
  return (
    <g>
      <circle cx={x} cy={y} r={16} fill="var(--color-surface-default)" stroke={BLEKK} strokeWidth={2} />
      <text x={x} y={y} textAnchor="middle" dominantBaseline="central" fontSize={19} fontWeight={600} fill={BLEKK}>{n}</text>
    </g>
  )
}

export default function VeggSnitt() {
  // regndråper drevet inn mot veggen fra venstre (vest)
  const drops = Array.from({ length: 14 }, (_, i) => ({ x: 40 + (i % 7) * 46, y: 70 + Math.floor(i / 7) * 70 + (i % 3) * 14 }))
  return (
    <figure className="flex flex-col gap-sm">
      <svg viewBox="0 0 720 400" className="w-full" role="img"
           aria-label="Tverrsnitt av en klatrevegg som viser regn som blåser inn på veggen, sol, vind, vannfilm, vann i sprekker, siging og kondens">
        <defs>
          <linearGradient id="berg" x1="0" x2="1">
            <stop offset="0" stopColor="var(--color-light-800)" />
            <stop offset="1" stopColor="var(--color-light-700)" />
          </linearGradient>
          <marker id="pil" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M0,0 L10,5 L0,10 z" fill={DEMPET} />
          </marker>
          <marker id="pilblå" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M0,0 L10,5 L0,10 z" fill={BLÅ} />
          </marker>
        </defs>

        {/* bakke og jord/vegetasjon over veggen */}
        <path d="M0,372 L720,372 L720,400 L0,400 Z" fill="var(--color-light-700)" />
        <path d="M482,44 C530,24 610,32 720,20 L720,64 L500,64 Z" fill="var(--color-accent-green-50)" stroke="var(--color-accent-green-400)" strokeOpacity={0.5} />

        {/* veggen: hylle øverst, tak midt på, svakt overhengende nederst */}
        <path d="M720,64 L500,64 L494,146 L452,132 L450,150 L446,230 L506,238 L488,300 L470,372 L720,372 Z" fill="url(#berg)" stroke={BLEKK} strokeWidth={1.5} strokeLinejoin="round" />
        {/* vannfilm langs fronten */}
        <path d="M497,66 L491,142 M449,135 L447,150 L443,228 M502,241 L485,300 L467,370" fill="none" stroke={BLÅ} strokeWidth={3} strokeOpacity={0.55} strokeLinecap="round" />
        {/* vann som blir liggende på hylla */}
        <path d="M467,137 L494,137 L494,146 Z" fill={BLÅ} fillOpacity={0.8} />
        {/* vått under taket, med dråper */}
        <path d="M449,232.5 L504,240" stroke={BLÅ} strokeWidth={3} strokeOpacity={0.55} strokeLinecap="round" />
        {[462, 478, 494].map((x, i) => (
          <path key={x} d={`M${x},${235 + i * 2.2} q-4.5,8 0,11 q4.5,-3 0,-11 Z`} fill={BLÅ} />
        ))}
        {/* sprekk fra jorda ned til hylla, med siging */}
        <path d="M562,64 L556,84 L560,96 L540,112 L532,128 L514,134 L494,146" fill="none" stroke={BLEKK} strokeWidth={1.5} strokeLinejoin="round" />
        <path d="M567,68 L561,86 L565,99 L545,115 L537,131 L519,138 L500,148" fill="none" stroke={BLÅ} strokeWidth={2} strokeDasharray="2 5" strokeLinejoin="round" />

        {/* sol */}
        <circle cx={70} cy={40} r={20} fill={GUL} />
        {[[488, 90], [486, 114], [466, 132]].map(([x2, y2], i) => (
          <line key={i} x1={96 + i * 10} y1={52 + i * 10} x2={x2} y2={y2} stroke={GUL} strokeWidth={2} strokeDasharray="6 6" />
        ))}

        {/* vind og slagregn fra vest */}
        {drops.map((d, i) => (
          <line key={i} x1={d.x} y1={d.y} x2={d.x + 16} y2={d.y + 12} stroke={BLÅ} strokeWidth={2} strokeLinecap="round" />
        ))}
        <path d="M30,272 C140,258 260,280 468,266" fill="none" stroke={DEMPET} strokeWidth={1.5} markerEnd="url(#pil)" />
        <path d="M30,304 C150,292 280,312 462,300" fill="none" stroke={DEMPET} strokeWidth={1.5} markerEnd="url(#pil)" />

        {/* fordampning og kondens ved veggen */}
        <path d="M476,336 C458,330 460,318 444,318" fill="none" stroke={BLÅ} strokeWidth={1.5} strokeDasharray="3 3" markerEnd="url(#pilblå)" />
        <path d="M438,356 C452,358 458,363 468,362" fill="none" stroke={BLÅ} strokeWidth={1.5} markerEnd="url(#pilblå)" />

        {/* temperatur i berget */}
        <path d="M600,300 L600,250" stroke={RØD} strokeWidth={4} strokeLinecap="round" />
        <circle cx={600} cy={308} r={8} fill={RØD} />

        {/* 3 peker på både hylla og taket */}
        <path d="M423,176 L466,141 M424,197 L462,236" stroke={DEMPET} strokeWidth={1} strokeDasharray="2 3" />

        <Merke x={170} y={110} n={1} />
        <Merke x={440} y={60} n={2} />
        <Merke x={410} y={186} n={3} />
        <Merke x={604} y={104} n={4} />
        <Merke x={300} y={44} n={5} />
        <Merke x={300} y={250} n={6} />
        <Merke x={414} y={338} n={7} />
        <Merke x={628} y={276} n={8} />
      </svg>
      <figcaption className="sr-only">Tverrsnitt av veggen. Forklaring i lista under.</figcaption>
    </figure>
  )
}

export const FORKLARING: { n: number; tittel: string; tekst: string }[] = [
  { n: 1, tittel: 'Slagregn', tekst: 'Regn som faller rett ned, treffer knapt en loddrett vegg. Det er vinden som driver det inn, så det som teller er hvor hardt det blåser mot veggen.' },
  { n: 2, tittel: 'Vannfilm', tekst: 'En tynn film på overflaten, rundt en tiendedels millimeter. Det er den du kjenner på fingrene, og den tørker fort når forholdene er gode.' },
  { n: 3, tittel: 'Tak og hyller', tekst: 'Vann blir liggende på hyller og i sprekker, og henger igjen under tak. Det tørker saktere enn filmen, og er grunnen til at det kan være vått i taket selv om resten av veggen er tørr.' },
  { n: 4, tittel: 'Siging', tekst: 'Etter flere dager med regn renner det vann ut av jorda og sprekkene over veggen. Det kan holde på i dagevis etter at det har sluttet å regne.' },
  { n: 5, tittel: 'Sol på veggen', tekst: 'Sola varmer berget, og varmt berg tørker raskere. Ut fra retningen og terrenget rundt regner vi ut når sola faktisk treffer hver vegg.' },
  { n: 6, tittel: 'Vind og tørr luft', tekst: 'Vind og tørr luft tar med seg fuktigheten fra overflaten. I rå Bergensluft kan det samme vannet bruke et døgn på å forsvinne.' },
  { n: 7, tittel: 'Fordampning og kondens', tekst: 'Er berget kaldere enn duggpunktet, kondenserer det vann på overflaten, og fjellet «svetter». Er det varmere, fordamper vannet.' },
  { n: 8, tittel: 'Bergtemperatur', tekst: 'Berget henger etter lufta. Kommer det varm, fuktig luft etter en kald periode, er fjellet fortsatt kaldt, og veggen blir våt uten at det regner.' },
]
