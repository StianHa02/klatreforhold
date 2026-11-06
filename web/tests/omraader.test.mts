const o = await import('../lib/omraader.ts')
const assert = (c: unknown, m: string) => { if (!c) { console.log('FEIL', m); process.exit(1) } else console.log('OK', m) }

const felt = [
  { navn: 'Trollkona', omraade: 'Øst for Bergen' },
  { navn: 'Sandviken', omraade: 'Bergen nord' },
  { navn: 'Bymuren', omraade: 'Bergen nord' },
  { navn: 'Nyfeltet', omraade: 'Ukjent område' },
  { navn: 'Gammelt', omraade: null },
  { navn: 'Ålesundveggen', omraade: 'Bergen nord' },
]
const g = o.grupperFelt(felt)
assert(g.map((x) => x.omraade).join('|') === 'Bergen nord|Øst for Bergen|Andre', 'områder i nettførerens rekkefølge, ukjente sist')
assert(g[0].felt.map((f) => f.navn).join('|') === 'Bymuren|Sandviken|Ålesundveggen', 'felt sortert på norsk (Å etter S)')
assert(g[2].felt.length === 2, 'ukjent og manglende område samles under Andre')
assert(o.grupperFelt([]).length === 0, 'tom liste gir ingen grupper')

assert(o.normaliser('Løvåsen') === 'lovasen' && o.normaliser('Rævuri') === 'raevuri', 'søk tåler æøå')
assert(o.normaliser('Bolstadøyri').includes(o.normaliser('oyri')), 'delstreng uten ø treffer')
