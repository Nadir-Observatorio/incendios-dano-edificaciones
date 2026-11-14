*Leer en español: [README.md](README.md)*

# Building damage in the Viña del Mar fire, February 2024

The fire of 2 and 3 February 2024 destroyed thousands of homes in Viña del Mar and Quilpué. The
Sentinel-2 optical satellite measures burnt vegetation well, but on the populated hills it misses a
large share of the damaged houses: roofs without vegetation, 20 m pixels that mix house, street and
yard. This repository answers one question: **how much of that damage does the Sentinel-1 radar see,
independently of vegetation and clouds, and how much does it add to the optical sensor?**

The signal is the **loss of interferometric coherence**: when a house collapses or loses its roof, it
stops returning the same signal to the radar between two passes. Everything is computed with free and
open data and validated against the official reference of the Copernicus Emergency Management Service.

Part of [Nadir](https://nadir-observatorio.github.io/), Wildfires line. Sister case:
[burn severity with Sentinel-2](https://github.com/Nadir-Observatorio/incendios-severidad).

<!-- The figures in this file are written by scripts/escribir_readme.py from resultados/resumen_sitio.json; do not edit them by hand. -->

## Results

Test partition, evaluated **once** with the threshold fixed on the tuning partition. 95 % intervals
by spatial block resampling. Reference: Copernicus EMSN188 damage points matched to Google Open
Buildings footprints.

| Question | Result |
|---|---|
| Share of damaged buildings detected by the radar | **{p1_sensibilidad_radar}** {p1_sensibilidad_radar_ic} |
| ... destroyed | {p1_sensibilidad_destruidas} {p1_sensibilidad_destruidas_ic} |
| ... damaged | {p1_sensibilidad_danadas} {p1_sensibilidad_danadas_ic} |
| ... possibly damaged | {p1_sensibilidad_posible_dano} {p1_sensibilidad_posible_dano_ic} |
| Optical (Sentinel-2) on the same buildings | {p2_sensibilidad_optico} {p2_sensibilidad_optico_ic} |
| Both together | **{p2_sensibilidad_union}** {p2_sensibilidad_union_ic} |
| What the radar adds to the optical sensor | {p2_suma_del_radar} percentage points {p2_suma_del_radar_ic} |
| Of what the optical sensor missed, share recovered by the radar | {p2_rescate_radar} {p2_rescate_radar_ic} |
| False alarms on buildings with no recorded damage (EMSN188 area) | {p3_falsa_alarma_negativos} {p3_falsa_alarma_negativos_ic} |
| False alarms far from the fire (over 2 km from the EMSR715 burnt area) | {p3_falsa_alarma_control} {p3_falsa_alarma_control_ic} |
| Precision of the radar detections | {p3_precision} {p3_precision_ic} |
| Area under the ROC curve | {auc_roc} {auc_roc_ic} |
| Ascending orbit only / descending only | {p4_sensibilidad_ascendente} / {p4_sensibilidad_descendente} |
| With footprints of confidence ≥ 0.65 (robustness) | {robustez_sensibilidad_radar_065} {robustez_sensibilidad_radar_065_ic} |

**Outside the affected zone, the radar does not invent a damage area.** Outside the area analysed by
EMSN188, {p5_r10_celdas_sobre_umbral} of {p5_r10_celdas} H3 resolution 10 cells exceed the threshold; of these, the
ones touching the official EMSR715 burnt area number {verificacion_p5_sobre_umbral_que_tocan_area_quemada_emsr715}. They are scattered cells in the city (works,
urban change), not an omitted damage zone.

**Relation with the severity case.** The optical figure in this table uses the broadest rule of the
severity case (all burnt classes), the same one that case used to measure its omission in the urban
interface against EMSN188, on a sample of points: both measurements agree. With that case's
calibrated threshold the optical sensor would see even less urban damage, so the comparison favours
the optical sensor.

![Share of damaged buildings detected by the optical sensor and by both](figuras/fig_optico_vs_union.png)

![Sensitivity with intervals](figuras/fig_sensibilidad.png)

## How to read it

- **"Probable damage according to radar"**, not "destroyed house". The radar measures that something
  changed, not what changed: debris removal and emergency works also lower the coherence.
- The signal is 20 m: per building it is a signal of its surroundings. Public results are given per H3
  cell, never per dwelling.
- EMSN188 is an official photo-interpretation on a post-event image, not ground truth; buildings
  without a point are "no recorded damage", not "no damage".
- **Copernicus EMS, SENAPRED and MINVU have not validated these results.**

## Method

1. **Sentinel-1A pairs** (the only satellite operating in February 2024): per orbit, six 12-day
   pre-event pairs, the event pair and one post-event pair. Ascending, orbit 18, 20:28 Chile time,
   event from 23-01 to 04-02-2024. Descending, orbit 156, 07:04 Chile time, event from 02-02 to
   14-02-2024 (the 2 February pass precedes the fire). 56 coherence products at 20 m ordered from
   [ASF HyP3](https://hyp3-docs.asf.alaska.edu/) (`INSAR_ISCE_BURST`, 5x1 looks).
2. **Per-pixel signal:** `z = (m − c_event) / max(s, 0.05)`, with `m` and `s` the mean and deviation
   of the pre-event coherence; common 20 m grid in UTM 19S; layover and shadow mask from each
   product's geometry.
3. **Per building:** mean weighted by the exact area of the footprint buffered by 10 m; combined
   signal = mean of both orbits.
4. **Reference:** each EMSN188 P08 damage point is matched to the footprint that contains it or to the
   nearest within 10 m ({fraccion_puntos_sin_huella} of the {puntos_emsn188} points had no footprint).
5. **Partition:** H3 resolution 8 blocks, stratified, half tuning and half test, written to disk with
   its hash before any signal was read.
6. **Threshold:** 90th percentile of the signal on tuning buildings with no recorded damage
   (z = {umbral_z}).

Protocol sealed before any data was ordered, and two amendments written before any signal was read,
in [`protocolo/`](protocolo/) (Spanish), with their sha256 hashes.

## Reproduce

Requirements: Python 3.12, a free [Earthdata Login](https://urs.earthdata.nasa.gov/) account and
about 15 GB of free space. Commands and arguments are listed in the Spanish README; each task checks
the sha256 hashes of the protocol, amendments, references and every product before computing. Exact
pairs: [`resultados/pares_hyp3.json`](resultados/pares_hyp3.json). The Copernicus EMS references are
downloaded from their pages ([EMSN188](https://riskandrecovery.emergency.copernicus.eu/EMSN188),
[EMSR715](https://rapidmapping.emergency.copernicus.eu/EMSR715)) and are not redistributed here.

Tests and quality: `pytest`, `ruff check scripts tests`, `mypy`.

## Limitations

- A single satellite: the event pair spans 12 days and includes the first works.
- A burnt house with its structure standing may keep its coherence.
- Damage concentrates in few blocks, so the sensitivity interval is wide; the advantage of combining
  both sensors over the optical one alone is firmer.
- The threshold was set for 10 % false alarms on tuning and gave fewer on test: buildings without
  damage differ in space between partitions.
- No radar amplitude: the products do not provide it per date (amendment 02).

## Data and licences

Code: MIT ([`LICENSE`](LICENSE)). Results and figures: CC BY 4.0, with the notices in
[`LICENSE-DATA.md`](LICENSE-DATA.md).

Made by Camilo López Barra, geographer.
