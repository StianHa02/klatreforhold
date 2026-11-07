// Nettførerens områder i nettførerens rekkefølge (tabellen `omraade`, kolonnen sorteringsindex).
// Felt uten kjent område havner sist under «Andre», så et nytt område ikke forsvinner før lista er oppdatert.
export const OMRAADER = [
  'Bergen nord',
  'Bergen vest',
  'Bergen sør',
  'Øygarden nord',
  'Øygarden vest',
  'Øygarden sør',
  'Tellnes/Haganes',
  'Askøy/Lillesotra',
  'Nord for Bergen',
  'Øst for Bergen',
]
export const ANDRE = 'Andre'

export type Gruppe<T> = { omraade: string; felt: T[] }

/** Deler feltene inn etter område, i nettførerens rekkefølge, og sorterer feltene på navn. */
export function grupperFelt<T extends { navn: string; omraade?: string | null }>(felt: T[]): Gruppe<T>[] {
  const grupper = new Map<string, T[]>()
  for (const f of felt) {
    const o = f.omraade && OMRAADER.includes(f.omraade) ? f.omraade : ANDRE
    grupper.set(o, [...(grupper.get(o) ?? []), f])
  }
  return [...OMRAADER, ANDRE]
    .filter((o) => grupper.has(o))
    .map((o) => ({ omraade: o, felt: grupper.get(o)!.sort((a, b) => a.navn.localeCompare(b.navn, 'nb')) }))
}

/** Søk uten hensyn til store bokstaver og aksenter (ø/o, å/a, é/e), så «lovasen» finner Løvåsen. */
export function normaliser(s: string): string {
  return s
    .toLowerCase()
    .replace(/ø/g, 'o')
    .replace(/æ/g, 'ae')
    .replace(/å/g, 'a')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
}
