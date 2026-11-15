*Leer en español: [README.md](README.md)*

# Closed case: Penco and Lirquén, January 2026 wildfires

Part of the [incendios-dano-edificaciones](../../README.en.md) repository of [Nadir](https://nadir-observatorio.github.io/), Wildfires line.

This case was meant to repeat in Penco and Lirquén (Biobío region, Chile) the Viña del Mar 2024 method
of this repository: measure with the Sentinel-1 radar coherence loss how much of the damaged buildings
is detected, and validate it against the Copernicus EMS damage points. The protocol was sealed on
14 November 2026, before any radar product was requested from ASF HyP3
([`PROTOCOLO_dano-edificaciones_penco-2026_sellado_2026-11-14.md`](PROTOCOLO_dano-edificaciones_penco-2026_sellado_2026-11-14.md),
sha256 `{caso:documento/0/sha256}`).

<!-- The figures in this file are written by scripts/escribir_readme_caso.py from the case reports; do not edit them by hand. -->

## What the reference showed

The planned reference was the grading product of Copernicus EMS activation EMSR859 for area
{insp:area/numero} "{insp:area/nombre}", made on a SPOT-6/7 image of {insp:productos_api/1/imagenes/0|fecha}.

- Its {refs:penco/puntos|ent} building points carry a single grade,
  "Possibly damaged". There is no "Destroyed" and no "Damaged".
- Of the {refs:penco/conjuntos/principal/huellas_centroide_en_quemado|ent} Google Open Buildings
  footprints (confidence ≥ 0.75) centred in the product's burnt area
  ({refs:penco/area_quemada_ha|dec1} ha), {refs:penco/conjuntos/principal/huellas_en_quemado_con_punto|ent}
  have a damage point ({refs:penco/conjuntos/principal/fraccion_huellas_en_quemado_con_punto|pct2}).
  Outside that area, within 1 km, {refs:penco/conjuntos/principal/huellas_a_1km_o_menos_fuera_con_punto|ent}
  of {refs:penco/conjuntos/principal/huellas_a_1km_o_menos_fuera_del_quemado|ent} have one.
- In Viña, the EMSN188 reference separates three grades ({refs:vina/por_grado/Destroyed/puntos|ent}
  "Destroyed", {refs:vina/por_grado/Damaged/puntos|ent} "Damaged" and {refs:vina/por_grado/Possible damage/puntos|ent}
  "Possible damage") and gives a point to {refs:vina/conjuntos/principal/fraccion_huellas_en_quemado_con_punto|pct1}
  of the footprints centred in the EMSR715 burnt area. It is a building-by-building assessment.

Copernicus EMS describes activation EMSR859 as mapping of the fire extent
([activation notice](https://mapping.emergency.copernicus.eu/news/wildfires-in-the-biobio-and-nuble-regions-chile-emsr859/)).
In area {insp:area/numero}, the grade almost fully coincides with lying inside the burnt area, so it does not
distinguish the damage to each building. Against that reference, a radar sensitivity in Penco would
measure the share of buildings in the burnt area with a signal and could not be compared with Viña's.

## Decision

The case was closed by [amendment 01](ENMIENDA_01_penco-2026_2026-11-14.md) (stop condition 1 of the
protocol, because grades "{refs:deteccion_1_lectura_estricta/grados_ausentes/0}" and
"{refs:deteccion_1_lectura_estricta/grados_ausentes/1}" are missing). No HyP3 jobs were requested, no
Sentinel-2 optical detection was computed and no partition was written. That is why there are no radar
figures for Penco.

The case reopens only with a building-level reference with damage grades for Penco and Lirquén, and with
a new amendment written before any radar data is requested.

## The two reports

| File | What it answers | Bytes | sha256 |
|---|---|---|---|
| [`derivados/t03b/inspeccion_emsr859.json`](derivados/t03b/inspeccion_emsr859.json) | Area {insp:area/numero} products in the zip, layers, fields and stop conditions 1 and 2 | {insp:@bytes|ent} | `{insp:@sha256}` |
| [`derivados/t03c/referencias.json`](derivados/t03c/referencias.json) | What the grade marks in Penco and in Viña, with the same measures | {refs:@bytes|ent} | `{refs:@sha256}` |

These are the 14 November 2026 reports cited by the amendment. They reproduce in content, not in hash:

- `referencias.json` stores its run time in the `generado` field ({refs:generado}).
- `inspeccion_emsr859.json` came from the first version of `t03b_emsr859.py`, which applied stop
  condition 1 only when none of the fixed grades appeared; that is why its `deteccion_1` field does not
  stop. The version in this repository applies the protocol's strict reading and would stop, as
  `deteccion_1_lectura_estricta` in `referencias.json` does. Amendment 01 records that correction.

## Rebuilding the reports

Inputs, not redistributed here:

- `EMSR859_products.zip`, from the `productsPath` of the public Copernicus EMS API
  ({proc:archivo/0/url}). On 14 November 2026 it was {proc:archivo/1/bytes|ent} bytes, sha256
  `{proc:archivo/1/sha256}`, server modification date {proc:archivo/1/ultima_modificacion_servidor}.
  If Copernicus regenerates the zip, the hash changes.
- Google Open Buildings, tile `{caso:metodo/teselas_open_buildings/0}` (CC BY 4.0).
- Only for the Viña part of `t03c_referencias.py`: `EMSN188_GeospatialData.zip` and
  `EMSR715_products.zip`, which `referencia.leer` checks against `casos/vina-2024/caso.toml`.

Commands are in the Spanish README. Fill in both `rutas.toml` files from their `rutas.ejemplo.toml`
first. `t03b_emsr859.py` downloads the zip and the API response to the `referencia_zip` folder and
writes its own provenance there; [`procedencia_emsr859_2026-11-14.toml`](procedencia_emsr859_2026-11-14.toml)
records the 14 November 2026 download for hash comparison and is not copied to the bank. Neither task
overwrites a report that already exists in `<carpeta_trabajo>`.

`referencia.leer` does not read the `emsr859_rapid_mapping` type of Penco's [`caso.toml`](caso.toml):
only `t03b_emsr859.py` and `t03c_referencias.py` read this reference, and `t04` to `t07` do not run for
this case.

## How to read it

- Copernicus EMS is the reference, not ground truth.
- Copernicus EMS, SENAPRED and MINVU did not validate these reports.

Product citation: Copernicus Emergency Management Service (© 2026 European Union), [EMSR859]
{insp:area/nombre} (AOI0{insp:area/numero}): Grading Map. Licences and notices in
[`LICENSE-DATA.md`](../../LICENSE-DATA.md).

Made by Camilo López Barra, geographer.
