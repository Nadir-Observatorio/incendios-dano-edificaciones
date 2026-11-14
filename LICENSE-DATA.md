# Licencia de los datos y avisos

El código de este repositorio está bajo licencia MIT (`LICENSE`). Este archivo cubre los resultados.

## Resultados derivados

`resultados/*.json` y `figuras/*.png` se publican bajo
[Creative Commons Atribución 4.0 Internacional (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/deed.es).

Atribución: **Camilo López Barra, geógrafo. Daño a edificaciones en el incendio de Viña del Mar,
febrero de 2024 (Nadir).**

Contienen información derivada de:

| Fuente | Uso | Aviso |
|---|---|---|
| Copernicus Sentinel-1A, ráfagas IW SLC VV (noviembre de 2023 a febrero de 2024) | Coherencia interferométrica | Contains modified Copernicus Sentinel data 2023-2024, processed by ESA |
| ASF DAAC HyP3, plugin hyp3_isce2 3.0.2 con ISCE 2.6.5 | Procesamiento de los 56 pares | Sentinel-1 Burst InSAR product processed by ASF DAAC HyP3 2026 using ISCE software |
| Copernicus DEM GLO-30 (dentro de cada producto de HyP3) | Pendiente, inversión y sombra | Produced using Copernicus WorldDEM-30 © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA; all rights reserved |
| Google Open Buildings (inferencia de mayo de 2023), usado bajo CC BY 4.0 | Huellas de edificios | Google Open Buildings, CC BY 4.0 |
| Copernicus EMS, EMSN188 P08 Detailed damage assessment | Referencia de daño | Copernicus Emergency Management Service (© 2024 European Union), [EMSN188] |
| Copernicus EMS, EMSR715 AOI01 Delineation Map v2 | Control lejano y verificación | Copernicus Emergency Management Service (© 2024 European Union), [EMSR715] |
| Severidad de Sentinel-2 (Nadir, caso hermano), CC BY 4.0 | Detección óptica | Contains modified Copernicus Sentinel data 2024 |

Los productos de Copernicus EMS, los productos de HyP3 y las huellas no se redistribuyen aquí: se
bajan de sus fuentes con los scripts. Los datos de Copernicus EMS se pueden reproducir, distribuir,
adaptar y combinar con otros datos de forma gratuita, informando la fuente, y se entregan tal cual
([términos de CEMS](https://mapping.emergency.copernicus.eu/terms-and-conditions/)). La imagen de
muy alta resolución de esas activaciones no se usa ni se redistribuye.

## Sin garantía ni respaldo

Los resultados se entregan tal cual. Son un análisis independiente: ni la Unión Europea, ni la ESA,
ni Copernicus, ni la NASA, ni Google, ni el Estado de Chile (SENAPRED, MINVU) los revisaron ni los
respaldan. Muestran "daño probable según radar", no un dictamen sobre cada vivienda.
