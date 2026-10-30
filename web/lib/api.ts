// Typer og henting fra klatreforhold-API-et (Python, FastAPI).
// Nettsiden viser tre tilstander. Modellen regner også ut «is» (is/snø på veggen), men det er like lite
// klatrbart som vått, så kilde.ts gjør det om til «vatt» før det når komponentene.
export type Status = 'tort' | 'fuktig' | 'vatt'

export type Time = {
  tid: string
  status: Status
  status_tekst: string
  is_sno?: boolean // modellen sa «is» (is/snø på veggen); vises som vått
  tort: boolean
  p_vatt: number | null
  vann_mm: number
  is_mm?: number
  sno_mm?: number
  sol_mulig?: boolean
  direkte_sol_wm2?: number
  vaerkilde?: string
  nedborkilde?: string
  fase_estimert?: boolean
  bergtemp: number
  duggpunkt: number
  lufttemp: number
  luftfuktighet: number
  nedbor_mm: number
  regn_mot_veggen_mm: number
  vind_ms: number
  vindretning: number
  sol_pa_veggen: boolean
  sol_wm2?: number // stråling på flaten; mangler i varsler laget før historikken kom
  timer_til_tort: number | null
  grunner: string[]
}

export type Varsel = {
  modellversjon?: string
  konfigurasjon?: string
  initialisering_usikker?: boolean
  reservekilder?: string[]
  felt: { slug: string; navn: string; felt_id: number | null; lat: number; lon: number; orientering: number }
  generert: string
  na: string
  kilde: string
  ml_modell: boolean
  sammendrag: {
    status_na: Status
    status_na_tekst: string
    tort_na: boolean
    tort_om_24t: boolean
    'tørre_timer_neste_24': number
    neste_torre_time: string | null
    neste_vate_time: string | null
    grunner_na: string[]
  }
  timer: Time[]
  siste_timer: Time[]
  historikk?: Time[] // alle timer før nå (opptil 7 døgn), modellen kjørt på været slik det ble
  framover?: Time[] // alle timer fra nå (ut dag +4); `timer` er bare neste døgn
  forbehold: string
  utdatert?: boolean
}

/** Varselet for en time slik det så ut noen timer før (fra arkivet). */
export type TidligereVarsel = { tid: string; status: Status; ledetid_timer: number }

export type Felt = { slug: string; navn: string; felt_id: number | null; lat: number; lon: number; orientering: number }

export type Observasjoner = {
  antall: number
  antall_vurdert?: number
  andel_riktig: number | null
  observasjoner: { time: string; status: Status; predikert_status: string; riktig: number | ''; kommentar: string }[]
}

export const klokke = (iso: string) =>
  new Date(iso).toLocaleTimeString('nb-NO', { hour: '2-digit', minute: '2-digit', timeZone: 'Europe/Oslo' })
export const dag = (iso: string) =>
  new Date(iso).toLocaleDateString('nb-NO', { weekday: 'short', day: 'numeric', month: 'short', timeZone: 'Europe/Oslo' })

export const statusFarge: Record<Status, string> = {
  tort: 'bg-forhold-tort',
  fuktig: 'bg-forhold-fuktig',
  vatt: 'bg-forhold-vatt',
}
export const statusTint: Record<Status, string> = {
  tort: 'bg-forhold-tort-tinted',
  fuktig: 'bg-forhold-fuktig-tinted',
  vatt: 'bg-forhold-vatt-tinted',
}
