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
      <text x={x} y={y + 6.5} textAnchor="middle" fontSize={19} fontWeight={600} fill={BLEKK}>{n}</text>
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
        <path d="M470,40 C520,22 600,30 720,18 L720,64 L488,64 Z" fill="var(--color-accent-green-50)" stroke="var(--color-accent-green-400)" strokeOpacity={0.5} />

        {/* veggen: ujevn front med tak og en sprekk */}
        <path d="M720,64 L488,64 L478,120 L494,124 L470,190 L488,196 L466,262 L482,268 L462,372 L720,372 Z" fill="url(#berg)" stroke={BLEKK} strokeWidth={1.5} />
        {/* vannfilm langs fronten */}
        <path d="M484,66 L474,120 L490,124 L466,190 L484,196 L462,262 L478,268 L458,370" fill="none" stroke={BLÅ} strokeWidth={3} strokeOpacity={0.55} />
        {/* tak/hylle med vann */}
        <path d="M470,190 L488,196 L520,196 L520,186 Z" fill={BLÅ_LYS} />
        <path d="M494,124 L478,120 L478,124 Z" fill={BLÅ_LYS} />
        {/* sprekk med siging */}
        <path d="M560,64 C552,110 560,150 548,200 C540,232 548,250 540,262" fill="none" stroke={BLEKK} strokeWidth={1.2} />
        <path d="M556,70 C548,116 556,152 544,202 C536,234 544,250 536,262" fill="none" stroke={BLÅ} strokeWidth={2} strokeDasharray="2 5" />

        {/* sol */}
        <circle cx={70} cy={40} r={20} fill={GUL} />
        {[0, 1, 2].map((i) => (
          <line key={i} x1={96 + i * 10} y1={52 + i * 10} x2={440 - i * 30} y2={196 + i * 50} stroke={GUL} strokeWidth={2} strokeDasharray="6 6" />
        ))}

        {/* vind og slagregn fra vest */}
        {drops.map((d, i) => (
          <line key={i} x1={d.x} y1={d.y} x2={d.x + 16} y2={d.y + 12} stroke={BLÅ} strokeWidth={2} strokeLinecap="round" />
        ))}
        <path d="M30,250 C130,236 250,252 430,238" fill="none" stroke={DEMPET} strokeWidth={1.5} markerEnd="url(#pil)" />
        <path d="M30,282 C150,270 260,290 420,276" fill="none" stroke={DEMPET} strokeWidth={1.5} markerEnd="url(#pil)" />

        {/* fordampning og kondens ved veggen */}
        <path d="M452,330 C432,320 440,306 420,298" fill="none" stroke={BLÅ} strokeWidth={1.5} strokeDasharray="3 3" markerEnd="url(#pilblå)" />
        <path d="M420,348 C436,350 440,358 452,356" fill="none" stroke={BLÅ} strokeWidth={1.5} markerEnd="url(#pilblå)" />

        {/* temperatur i berget */}
        <path d="M600,300 L600,250" stroke={RØD} strokeWidth={4} strokeLinecap="round" />
        <circle cx={600} cy={308} r={8} fill={RØD} />

        <Merke x={170} y={110} n={1} />
        <Merke x={500} y={92} n={2} />
        <Merke x={538} y={180} n={3} />
        <Merke x={590} y={50} n={4} />
        <Merke x={250} y={170} n={5} />
        <Merke x={300} y={262} n={6} />
        <Merke x={402} y={322} n={7} />
        <Merke x={628} y={276} n={8} />
      </svg>
      <figcaption className="sr-only">Tverrsnitt av veggen. Forklaring i lista under.</figcaption>
    </figure>
  )
}

export const FORKLARING: { n: number; tittel: string; tekst: string }[] = [
  { n: 1, tittel: 'Slagregn', tekst: 'Regn faller ikke rett ned på en loddrett vegg. Det er vinden som driver det inn, så det som teller er hvor hardt det blåser rett mot veggen.' },
  { n: 2, tittel: 'Vannfilm', tekst: 'En tynn film på overflaten, rundt en tiendedels millimeter. Det er den du kjenner på fingrene. Den tørker fort når forholdene er gode.' },
  { n: 3, tittel: 'Tak og hyller', tekst: 'Vann blir liggende i tak, hyller og sprekker. Det tørker saktere enn filmen, og er grunnen til at det kan være vått i tak selv om veggen ser tørr ut.' },
  { n: 4, tittel: 'Siging', tekst: 'Etter mye regn over flere dager renner det vann ut fra jord og sprekker over veggen. Det kan holde på i dager etter at det har sluttet å regne.' },
  { n: 5, tittel: 'Sol på veggen', tekst: 'Sola varmer berget, og varmt berg tørker raskere. Vi regner ut når sola faktisk treffer hver vegg ut fra retningen og terrenget rundt.' },
  { n: 6, tittel: 'Vind og tørr luft', tekst: 'Vind og lav luftfuktighet tar med seg fuktigheten fra overflaten. I fuktig Bergensluft kan det samme vannet bruke et døgn på å forsvinne.' },
  { n: 7, tittel: 'Fordampning og kondens', tekst: 'Er berget kaldere enn duggpunktet, kondenserer det vann på det: fjellet «svetter». Ellers fordamper vannet.' },
  { n: 8, tittel: 'Bergtemperatur', tekst: 'Berget henger etter lufta. Kommer det varm, fuktig luft etter en kald periode, er fjellet fortsatt kaldt, og det blir vått uten at det regner.' },
]
