// Typer og henting fra klatreforhold-API-et (Python, FastAPI).
export type Status = 'tort' | 'fuktig' | 'vatt' | 'is'

export type Time = {
  tid: string
  status: Status
  status_tekst: string
  tort: boolean
  p_vatt: number | null
  vann_mm: number
  bergtemp: number
  duggpunkt: number
  lufttemp: number
  luftfuktighet: number
  nedbor_mm: number
  regn_mot_veggen_mm: number
  vind_ms: number
  vindretning: number
  sol_pa_veggen: boolean
  timer_til_tort: number | null
  grunner: string[]
}

export type Varsel = {
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
  forbehold: string
  utdatert?: boolean
}

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
  is: 'bg-forhold-is',
}
export const statusTint: Record<Status, string> = {
  tort: 'bg-forhold-tort-tinted',
  fuktig: 'bg-forhold-fuktig-tinted',
  vatt: 'bg-forhold-vatt-tinted',
  is: 'bg-forhold-is-tinted',
}
