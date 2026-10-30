# Ablasjon av modell v2

Samme lokale vær per felt, 2024-10-01–2025-09-30, etter 30 døgn oppvarming.
Tallene er simulert andel dagtimer (kl. 08–20) som ikke er tørre, ikke målte forhold.
Dette inkluderer fuktig/vått og modellert is/snø; v1 har ingen egne is-/snølagre.
Trinnene er kumulative; siste trinn inkluderer både ny vannbalanse, initialisering og vinterfysikk.

| Felt | Trinn | Sommer, % vått | Vinter, % vått |
|---|---|---:|---:|
| ekstraveggen | v1 | 30.73 | 67.88 |
| ekstraveggen | geometri | 30.77 | 68.01 |
| ekstraveggen | straling | 31.53 | 68.39 |
| ekstraveggen | vind | 33.71 | 71.94 |
| ekstraveggen | vann_og_vinter | 31.48 | 70.54 |
| helleneset | v1 | 34.72 | 67.71 |
| helleneset | geometri | 34.72 | 67.79 |
| helleneset | straling | 34.93 | 67.96 |
| helleneset | vind | 33.08 | 64.79 |
| helleneset | vann_og_vinter | 32.24 | 67.54 |
| sandviken | v1 | 29.93 | 60.14 |
| sandviken | geometri | 31.23 | 61.37 |
| sandviken | straling | 31.48 | 61.92 |
| sandviken | vind | 32.28 | 63.19 |
| sandviken | vann_og_vinter | 31.27 | 60.95 |

Reproduser: `python scripts/compare_model_v2.py --baseline 9db616c` fra `modeling/`.
V1-koden og konfigurasjonen leses fra Git. Ingen lagrede prognoser eller observasjoner endres.
