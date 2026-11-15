*Leer en español: [README.md](README.md)*

# Closed case: Penco and Lirquén, January 2026 wildfires

Part of the [incendios-dano-edificaciones](../../README.en.md) repository of [Nadir](https://nadir-observatorio.github.io/), Wildfires line.

This case was meant to repeat in Penco and Lirquén (Biobío region, Chile) the Viña del Mar 2024 method
of this repository: measure with the Sentinel-1 radar coherence loss how much of the damaged buildings
is detected, and validate it against the Copernicus EMS damage points. The protocol was sealed on
14 November 2026, before any radar product was requested from ASF HyP3
([`PROTOCOLO_dano-edificaciones_penco-2026_sellado_2026-11-14.md`](PROTOCOLO_dano-edificaciones_penco-2026_sellado_2026-11-14.md),
sha256 `ec6a3cd5651314d6d4ea40149a0e29795103d0802c0d1229d8fa4b6445a43f44`).

<!-- The figures in this file are written by scripts/escribir_readme_caso.py from the case reports; do not edit them by hand. -->

## What the reference showed

The planned reference was the grading product of Copernicus EMS activation EMSR859 for area
4 "Conception", made on a SPOT-6/7 image of 25 January 2026.

- Its 6,765 building points carry a single grade,
  "Possibly damaged". There is no "Destroyed" and no "Damaged".
- Of the 4,423 Google Open Buildings
  footprints (confidence ≥ 0.75) centred in the product's burnt area
  (12,781.3 ha), 4,420
  have a damage point (99.93%).
  Outside that area, within 1 km, 49
  of 23,708 have one.
- In Viña, the EMSN188 reference separates three grades (5,694
  "Destroyed", 570 "Damaged" and 1,011
  "Possible damage") and gives a point to 66.4%
  of the footprints centred in the EMSR715 burnt area. It is a building-by-building assessment.

Copernicus EMS describes activation EMSR859 as mapping of the fire extent
([activation notice](https://mapping.emergency.copernicus.eu/news/wildfires-in-the-biobio-and-nuble-regions-chile-emsr859/)).
In area 4, the grade almost fully coincides with lying inside the burnt area, so it does not
distinguish the damage to each building. Against that reference, a radar sensitivity in Penco would
measure the share of buildings in the burnt area with a signal and could not be compared with Viña's.

## Decision

The case was closed by [amendment 01](ENMIENDA_01_penco-2026_2026-11-14.md) (stop condition 1 of the
protocol, because grades "Damaged" and
"Destroyed" are missing). No HyP3 jobs were requested, no
Sentinel-2 optical detection was computed and no partition was written. That is why there are no radar
figures for Penco.

The case reopens only with a building-level reference with damage grades for Penco and Lirquén, and with
a new amendment written before any radar data is requested.

## The two reports

| File | What it answers | Bytes | sha256 |
|---|---|---|---|
| [`derivados/t03b/inspeccion_emsr859.json`](derivados/t03b/inspeccion_emsr859.json) | Area 4 products in the zip, layers, fields and stop conditions 1 and 2 | 6,442 | `a9a05f90d180bfb75199508c0133de7dfc9186134dc0347abcba6e2f75e9de2b` |
| [`derivados/t03c/referencias.json`](derivados/t03c/referencias.json) | What the grade marks in Penco and in Viña, with the same measures | 6,740 | `937c827fa7f226ee69005f8efab6799fa1b91755112497feaee5ad025a87b5b6` |

These are the 14 November 2026 reports cited by the amendment. They reproduce in content, not in hash:

- `referencias.json` stores its run time in the `generado` field (2026-11-14T13:50:52-03:00).
- `inspeccion_emsr859.json` came from the first version of `t03b_emsr859.py`, which applied stop
  condition 1 only when none of the fixed grades appeared; that is why its `deteccion_1` field does not
  stop. The version in this repository applies the protocol's strict reading and would stop, as
  `deteccion_1_lectura_estricta` in `referencias.json` does. Amendment 01 records that correction.

## Rebuilding the reports

Inputs, not redistributed here:

- `EMSR859_products.zip`, from the `productsPath` of the public Copernicus EMS API
  (https://rapidmapping.emergency.copernicus.eu/backend/dashboard-api/public-activations/?code=EMSR859). On 14 November 2026 it was 740,725,752 bytes, sha256
  `d8c07cfdff3724a7cc2ce0f659ef464b24cf9dd9eb6fe5dea018a79a39958601`, server modification date Fri, 30 Jan 2026 15:45:23 GMT.
  If Copernicus regenerates the zip, the hash changes.
- Google Open Buildings, tile `967_buildings.csv.gz` (CC BY 4.0).
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
Conception (AOI04): Grading Map. Licences and notices in
[`LICENSE-DATA.md`](../../LICENSE-DATA.md).

Made by Camilo López Barra, geographer.
