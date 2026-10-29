# Drying rates, uncertainty, ground truth and history views

Follow-up to `RESEARCH.md` (October 2026). That review covered wind-driven rain, film drying versus
humidity, road- and leaf-wetness models and MET Nordic. This one covers four questions it left open:

1. How fast do real rock faces dry, and how do we calibrate drying per crag from few, biased reports?
2. How can the forecast express uncertainty (±2 h, probability of dry)?
3. What cheap measurements could give labels without selection bias?
4. How do other services show past weather and past predictions, so users can judge the forecast for themselves?

The research was done with web search on 2026-10-29. Several full texts were paywalled or blocked, so
some numbers come from abstracts. Those are marked "(abstract)". Prices are as seen on that date.

## 1. Drying of natural rock and per-crag calibration

### There are no published drying times for gneiss or granite crags

We found no field study that measures time to surface-dry on a natural crystalline outcrop after rain.
Our model's medians (about 7 h in summer and 14-20 h in winter after rain) can't be checked against
literature. The closest analogues support the model's structure:

- **Granite masonry with simulated rain.** Cracks and joints stay wet for days while the face dries much
  faster ([Fusade et al. 2019](https://www.nature.com/articles/s40494-019-0277-7)). This supports a
  separate crack store.
- **Surfaces wet often and dry fast; interiors wet slowly and dry slowly.** Shown for building sandstone
  ([McCabe et al. 2013](https://springerlink.bibliotecabuap.elogim.com/doi/10.1007/s12665-013-2278-2)).
  This supports film plus reservoir.
- **The drying rate of the first stage differs from a free-water surface and varies between stones.** It
  correlates with capillary porosity
  ([Diaz Gonçalves et al. 2012](https://repositorio.lnec.pt/handle/123456789/1003207)). So a per-site
  multiplier on the Lewis-relation evaporation is physically justified, not just a fudge.
- **Sandstone drying slows about 9× once the drying front leaves the surface** (0.9 → 0.1 mm/day)
  ([lab study](https://www.researchgate.net/publication/359866606)).
- **The ISO 15927-3 fixed 96 h "drying interval" is being replaced by façade-specific intervals**, computed
  from potential evaporation per orientation
  ([Pérez-Bella et al. 2024](https://discovery.ucl.ac.uk/id/eprint/10185970/)). This is the closest
  published version of "scale drying per site".
- **Lee faces still get wet in wind.** Aberdeen granite gables facing away from the wind got wet at
  higher wind speeds ([Aberdeen City](https://www.aberdeencity.gov.uk/media/5435), abstract). Our
  `cos(D−θ)` term gives zero on lee faces. A small floor may be worth testing.
- **Sensors don't settle the truth to better than about an hour.** Leaf-wetness sensors differ from visual
  wetness by about 1 h, and by up to 3.8 h depending on the threshold
  ([Liège study](https://orbi.uliege.be/bitstream/2268/93760/1/Performance%20of%20leaf%20wetness%20sensor%20used%20in%20winter%20wheat%20disease%20management.pdf)).

**Best quantitative analogue: forest canopy drying.** A canopy is also a thin water store on an exposed
surface. In Córdoba, pine canopies dried in about 2 h in summer and about 8 h in winter
([abstract](https://flacsoandes.edu.ec/buscador/Record/uncu-11678/Description)). Our summer/winter
ratio of 2-3× is similar.

### Calibrate one drying parameter, not three

Canopy-interception work shows that **storage capacity and evaporation rate can't be separated from
"wet or not" data**. Only direct storage measurements identify both
([Vrugt et al. 2003](https://earthref.org/ERR/79953/)). Tuning the evaporation term worked better than
raising storage ([Schellekens et al. 1999](https://czo-archive.criticalzone.org/luquillo/publications/pub/schellekens-et-al-1999-modeling-rainfall-interception-by-a-lowland-tropical/);
[HESS 2012](https://hess.copernicus.org/articles/16/4693/2012/)).

Our reports constrain roughly time-to-dry ≈ store ÷ evaporation rate. Recommendation:

- Calibrate **one per-crag log-multiplier on evaporation (log k_E)**, and keep the store capacities at
  their physical values.
- Add a second parameter only once there are many reports more than 48 h after big rain; seepage can't
  be identified otherwise.
- Keep the WDR-exposure multiplier on a tight prior, unless reports cover both onshore and offshore rain.
- Check identifiability (posterior correlation or profile likelihood) before trusting a multi-parameter fit.

### Likelihood, pooling and selection bias

- **Ordinal likelihood.** Use a cumulative-link (ordered logit) model on a latent wetness score, for
  example log modelled water, with two cut-points: dry|damp and damp|wet
  ([Bürkner & Vuorre 2019](https://vuorre.com/bibliography/files/2554/bürkner-and-vuorre_2019_advances-in-methods-and-practices-in-psychological-science.pdf)).
  People disagree on "damp"; that becomes a wide damp band and a noise scale with its own prior.
- **Partial pooling across crags.** Use log k_E,s ~ N(μ, τ), with τ ~ half-normal(0, 0.5), which allows
  roughly ±65 % between crags. With only three crags, τ is weakly identified, so use a half-t or
  half-normal prior and avoid inverse-gamma
  ([Gelman 2006](https://projecteuclid.org/euclid.ba/1354024466)). A crag with 5 reports then stays near
  the physics; a crag with 50 can move.
- **Two kinds of selection bias.**
  - *People go when the weather looks dry.* Selection then depends on the weather, not the label, so the
    conditional likelihood stays valid. The cost is few reports in clearly wet weather.
  - *People report surprises.* Selection then depends on label and forecast together (missing not at
    random), and naive fitting over-learns the surprises. This is the same as verification bias in
    diagnostic testing, and there are correction methods for it
    ([Begg & Greenes-type corrections](https://pmc.ncbi.nlm.nih.gov/articles/PMC3276270)). See also
    preferential sampling ([Diggle et al. 2010](https://eprints.lancs.ac.uk/id/eprint/51919/)).
  - **Practical fix:** make "it matched the forecast" a one-tap report, so the second kind becomes the
    first. Otherwise, model p(report | label, forecast) and down-weight surprises.
- **Sample size.** About **10-20 informative reports per crag** (2-30 h after rain) can move one parameter
  meaningfully. This is our reading of
  [Riley et al. 2019](https://ora.ox.ac.uk/objects/uuid:743761e7-58a5-4968-9195-2b266abe6ad3).
  Three free parameters need 50+. Count rain events, not reports, because reports from the same day are
  correlated. Reports from long dry spells carry almost no information.

### Fair evaluation

- **Scores.** Use the ranked probability score (3 ordered classes) and the Brier score for P(dry).
- **Reliability.** Use CORP reliability diagrams (isotonic, stable compared with binning)
  ([Dimitriadis et al.](https://pmc.ncbi.nlm.nih.gov/articles/PMC7923594)).
- **Strata.** Report by **hours since rain (0-6, 6-24, 24-72, >72 h)**, by season and by onshore wind,
  and macro-average across strata. This extends our `under_regn`/`etter_regn`/`torkeperiode` split.
- **Cross-validation.** Leave one rain event out, not random splits.
- **Baseline to beat.** "Hours since rain > X". Every public climbing tool we found uses some version of
  this rule (section 4).
- **Scheduled check-ins.** Volunteers report at fixed hours after rain, whatever their plans. Even 10-20
  of these break the selection bias and are worth more than 100 opportunistic reports.

## 2. Uncertainty

- **Open-Meteo's ensemble API has no MEPS** ([docs](https://open-meteo.com/en/docs/ensemble-api)).
  Ensembles that cover Bergen:
  - ECMWF IFS (51 members; 9 km hourly to 90 h, but only 00z/06z)
  - ICON-EU-EPS (40 members, ~6.5 km, 5 days)

  These are too coarse for Bergen showers. Use them for spread, not as the forecast. Individual members
  are kept for only about 3 days.
- **MEPS from MET directly.** 30-member lagged ensemble, 2.5 km, hourly updates, 66 h, on thredds
  (`meps_lagged_6_h_latest`) ([NWPdocs](https://github.com/metno/NWPdocs/wiki/MEPS-dataset)).
  A single point can be read over OPeNDAP.
- **Easiest option: Locationforecast `complete.json`.** For the Nordic area it already gives MEPS-based
  hourly `probability_of_precipitation`, `precipitation_amount_min/max` and wind/temperature percentiles
  ([datamodel](https://docs.api.met.no/doc/locationforecast/datamodel)). It is free and needs our
  existing User-Agent.
- **Cheapest option that matches our error.** Our rain error is mostly *timing*: 67 % hourly versus 91 %
  daily hits. So: **run the physics model on the forecast shifted −3…+3 h** and report the share of runs
  that are dry. Our own hourly archive is also a free time-lagged ensemble: the last ~6 runs valid for the
  same hour.
- **Operational precedent.** Met Office (JULES) and FMI (RoadSurf) run road-surface models on each ensemble
  member. FMI found the raw member fractions still needed calibration
  ([EMS 2022](https://meetingorganizer.copernicus.org/EMS2022/EMS2022-113.html)).
- **Calibration.** Fit logistic regression on the archive (lead time, season, rain amount, shifted-window
  maximum, MEPS rain probability). Check with reliability diagrams and fit summer and winter separately.
- **Display.** Statens vegvesen "Føreforhold" shows low/moderate/high risk up to 22 h ahead. For us:
  a three-level colour from calibrated P(dry), plus text such as "Regn trolig kl 14-17 (± 2 t)".

## 3. Cheap ground truth

**Camera (recommended).** Wet rock visibly darkens and turns glossy. Road studies classify wet/dry from
images with 87-96 % accuracy ([arXiv 2510.06440](https://arxiv.org/pdf/2510.06440)).
- Hardware: a solar 4G camera (Reolink Go Ranger PT or G450, about €200-280) taking a photo every 30 min.
  Add a Norwegian data-SIM (price not checked).
- Labelling: 2-3 members label dry/damp/wet, and we check how often they agree. Later, compare the
  brightness of a fixed rock patch with a dry-day baseline.
- Limit: the camera only sees daylight hours (about 6 h in December).

**Leaf-wetness sensor (optional add-on).** Dragino LMS01-LB, LoRaWAN, about €90
([exp-tech](https://exp-tech.de/products/dragino-lms01-lb-eu868)). The Things Network has a Bergen
community. It runs day and night, but an imitation leaf dries faster than rock and ignores seepage.
- Use it for rain and dew *onset*, and calibrate its drying lag against the camera.
- Each sensor needs its own wet/dry threshold
  ([Campbell](https://s.campbellsci.com/documents/au/manuals/237.pdf)).
- Resistance sensors on stone give only relative readings
  ([Historic England](https://historicengland.org.uk/research/results/reports/2-2022)).

**Plan.** One slow-drying wall, through at least one summer month with showers and one autumn month.
Store the labels per crag and hour in Supabase, as a separate source from the reports.

We found no paper that validates a surface-wetness model on natural crag rock against sensors or a camera.

## 4. How others show history and verification

- **Almost nobody shows past predictions next to what happened.**
  - [CountyEthics](https://county-ethics.onrender.com/about) (UK) comes closest. It shows consecutive dry
    days, 7- and 28-day rain totals, 24 h hourly history, and reports on a dry/damp/wet/seeping scale that
    "can tip the verdict".
  - theCrag hides its timeline behind a login. Mountain Project shows only climate averages.
  - Climbing Forecasts (UK) estimates recent rain from radar and gives each crag a drying speed and a
    seepage risk.
- **Hindcast versus the forecast as issued.** meteoblue's "history+" is a re-run (reanalysis), not an
  archive of what was forecast
  ([meteoblue](https://community.meteoblue.com/topic/156/downloading-comparison-data)). To show "what we
  said versus what happened", store each forecast as issued. We already do that in the `varsel` table.
- **Trust.** Inaccuracy hurts trust more than inconsistency
  ([Burgeno & Joslyn 2020](https://digital.lib.washington.edu/researchworks/items/c6442178-8dd2-4cdc-b762-20641f31800b)).
  Uncertainty information improves decisions and trust. Show misses honestly. Plain-language hit rates
  read better than skill scores (the ForecastAdvisor approach).
- **Design.**
  - yr tested sketches on people in the street and chose strong contrast and large fonts
    ([DOGA](https://doga.no/en/activities/design-and-architecture-in-norway/design-in-norway/interaction-design/yr-weather-service)).
  - meteoblue moved to hourly rain bars, because the start of rain matters most, and was criticised for
    low-contrast colours.
  - Use small multiples on a shared time axis, with labels only on the left
    ([Datawrapper](https://www.datawrapper.de/blog/what-to-consider-when-creating-small-multiple-line-charts)).
  - Colour must never be the only cue ([WCAG 1.4.1](https://kb.daisy.org/publishing/docs/wcag/use-of-color.html)).

## What we did with this

The first version (a sideways-scrolling 7-day chart with six rows) was too busy. The second version,
from 2026-10-29, follows the findings above more closely:

- **Day boxes** on the front page and at the top of each crag page: Nå, I morgen and three more days,
  coloured by status, with the dry window in climbing hours («kl 13–21»). Days 3–4 come from ECMWF and are
  marked «usikkert». This is the planning view climbers asked for.
- **«Neste 4 døgn» and «Siste 7 døgn» as week grids** (`web/components/Ukerutenett.tsx`): one row per day,
  24 hours, no sideways scrolling.
  - Each row shows a sun-on-the-wall line, status runs with letters, rain bars on a fixed scale, and day
    sums (rain, sun hours, mean wind).
  - Tapping a day opens an hour table, which is the table twin the dataviz guidance asks for.
- **History toggle.** «I etterkant» is the model re-run on the weather as it happened. «Varslet dagen før»
  is the forecast as issued about 24 h ahead, from the archive. That keeps the meteoblue distinction
  between hindcast and forecast-as-issued. Climber reports show as markers with ✓/✗ against whichever view
  is selected, and the hit rate is counted per view in plain words.
- **Summary line** with the last rain and «tørt igjen etter 9 t», so each crag's drying speed is visible.
- **Fixed 0–2 mm scale** for water and rain in the forecast chart. The area between rock temperature and
  dew point is shaded green (rock warmer) or blue (condensation), stronger with the gap (full at 4 °C).

The model recommendations above are listed as future work in `OVERLEVERING.md` §11.
