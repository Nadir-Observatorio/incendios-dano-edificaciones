# Protocolo: daño a edificaciones en el incendio de Viña del Mar, febrero de 2024

Nadir, línea Incendios. Diseño: OBS-0004, decisiones DE-1a a DE-5a del 2026-11-11.

Estado: SELLADO el 2026-11-11, antes de pedir cualquier producto a HyP3 y antes de leer cualquier
señal. Su sha256 queda registrado en `PROTOCOLO_dano-edificaciones_sellado_2026-11-11.sha256` y en
OBS-0004. Todo cambio posterior es una enmienda fechada con su motivo, escrita antes de ver el
resultado que afecta, en un archivo aparte; este archivo no se edita.

## 1. Preguntas

Descriptivas o de validación; no hay hipótesis confirmatorias.

- **P1.** Sensibilidad del radar: fracción de edificaciones con punto de daño de EMSN188 cuya señal
  de coherencia supera el umbral fijado en ajuste, medida en prueba, total y por grado.
- **P2.** Complementariedad: sensibilidad de Sentinel-2 (Etapa 1), de Sentinel-1 y de la unión en
  las mismas edificaciones de prueba; sensibilidad de Sentinel-1 entre las que Sentinel-2 no detectó.
- **P3.** Falsa alarma en negativos de prueba y en el control lejano.
- **P4.** Rendimiento por geometría (ascendente, descendente, combinada), por señal (coherencia,
  amplitud), por tercil de pendiente, de área de huella y de coherencia previa.
- **P5.** (Estimación de modelo) Celdas H3 de resolución 10 fuera de `P00_aoi` con mediana de la
  señal combinada sobre el umbral.

## 2. Insumos y versiones

| Insumo | Versión fijada | Huella |
|---|---|---|
| EMSN188, `EMSN188_GeospatialData.zip` (en `incendio-vina-2024\datos_crudos\referencias\`, solo lectura) | Geodatabase `EMSN188_STD_UTM19S_r02_v01` | sha256 `443e7c353f392c56124004a9ae3b2dfc1dbb1af26d9fd0fef31f610cb5dafed3` |
| Etapa 1, `datos/clases.tif` del repositorio publicado | La publicada | La de `datos/huellas.json` de la Etapa 1 |
| Google Open Buildings, teselas S2 de nivel 4 `967` y `969` de `polygons_s2_level_4_gzip` | Última modificación 23-06-2023 (cabecera HTTP) | sha256 al bajarlas, en `procedencia.toml` |
| Sentinel-1A, ráfagas IW VV (catálogo ASF del 2026-11-11, `nadir-dano\catalogo\`) | Ver sección 3 | Nombres de ráfaga y fecha |
| Productos HyP3 `INSAR_ISCE_BURST` | Versión del plugin que informe cada producto | sha256 al bajarlos |
| Copernicus DEM GLO-30 | Teselas del banco | Las de su `procedencia.toml` |

Grados de EMSN188 (`damage_gra`), según el informe técnico y el código de la Etapa 1: 3 Destroyed,
2 Damaged, 1 Possible damage.

## 3. Pares de imágenes

Hora del incendio: el foco del Complejo Las Tablas comenzó en la tarde del 02-02-2024 y el fuego
llegó a la zona urbana de Viña del Mar y Quilpué en la noche del 02-02 y el 03-02. La pasada
descendente del 02-02-2024 es a las 10:04 UTC (07:04 hora de Chile) y por eso es **previa**. El foco
de Camino Las Docas de esa madrugada queda fuera del área.

**Ascendente**, órbita relativa 18, 23:28 UTC (20:28 hora de Chile). Ráfagas `018_038457_IW1`,
`018_038457_IW2`, `018_038458_IW1`, `018_038458_IW2` (las cuatro; el área cae cerca del borde entre
IW1 e IW2).

| Rol | Referencia | Secundaria |
|---|---|---|
| Previo 1 | 2023-11-12 | 2023-11-24 |
| Previo 2 | 2023-11-24 | 2023-12-06 |
| Previo 3 | 2023-12-06 | 2023-12-18 |
| Previo 4 | 2023-12-18 | 2023-12-30 |
| Previo 5 | 2023-12-30 | 2024-01-11 |
| Previo 6 | 2024-01-11 | 2024-01-23 |
| Evento | 2024-01-23 | 2024-02-04 |
| Posterior | 2024-02-04 | 2024-02-16 |

**Descendente**, órbita relativa 156, 10:04 UTC (07:04 hora de Chile). Ráfagas `156_334205_IW2`,
`156_334206_IW2`, `156_334207_IW2`.

| Rol | Referencia | Secundaria |
|---|---|---|
| Previo 1 | 2023-11-22 | 2023-12-04 |
| Previo 2 | 2023-12-04 | 2023-12-16 |
| Previo 3 | 2023-12-16 | 2023-12-28 |
| Previo 4 | 2023-12-28 | 2024-01-09 |
| Previo 5 | 2024-01-09 | 2024-01-21 |
| Previo 6 | 2024-01-21 | 2024-02-02 |
| Evento | 2024-02-02 | 2024-02-14 |
| Posterior | 2024-02-14 | 2024-02-26 |

Pedido: 8 pares por ráfaga, 56 trabajos `INSAR_ISCE_BURST`, polarización VV, 5x1 *looks* (20 m), sin
máscara de agua en el pedido. Si alguna ráfaga no tiene una fecha en el momento del pedido, el par se
omite y se informa; no se reemplaza por otra fecha.

## 4. Huellas y referencia

1. **Área de trabajo:** caja −71,60 a −71,38 de longitud y −33,13 a −32,94 de latitud, en UTM 19S
   (EPSG:32719).
2. **Huellas:** Google Open Buildings bajo CC BY 4.0, confianza ≥ 0,75 (principal) y ≥ 0,65
   (sensibilidad), recortadas a la caja.
3. **Emparejamiento:** cada punto de P08 va a la huella que lo contiene; si no hay, a la más cercana
   a 10 m o menos; si no, queda "sin huella" y se informa. Una huella con varios puntos toma el grado
   mayor.
4. **Positivos:** huellas con punto. **Negativos:** huellas dentro de `P00_aoi` sin punto a 10 m o
   menos. **Control lejano:** huellas fuera de `P00_aoi` a más de 2 km de todo píxel de la Etapa 1
   con clase ≥ 4 (umbral A).
5. **Completitud:** fracción de puntos de P08 sin huella, y fracción del área de
   `P18HUST_HumanSettlements` cubierta por huellas; también con OSM y Microsoft como contraste (solo
   cifras de texto, por su licencia ODbL).

## 5. Señales

1. **Coherencia por píxel y geometría.** `z = (m − c_evento) / max(s, 0,05)`, con `m` y `s` la media y
   la desviación estándar de los 6 pares previos (mínimo 4 válidos; si no, el píxel queda sin dato).
2. **Mosaico de ráfagas:** en la superposición se usa la media de los valores válidos.
3. **Combinada:** por huella, la media de `z` de las geometrías con dato válido.
4. **Amplitud:** `|log10(a_post / a_pre)|`, con `a_pre` la media de la amplitud de las referencias de
   los 6 pares previos y `a_post` la amplitud de la referencia del par posterior; de los mismos
   productos de ráfaga (ver sección 10, punto 1).
5. **Persistencia (descriptiva):** `z` del par posterior, para informar si la pérdida se mantiene.
6. **Máscaras:** inversión y sombra calculadas con GLO-30 y la geometría de visión de cada producto;
   agua según la máscara del producto o, si no la trae, la de la Etapa 1.

## 6. Valor por huella

La huella se amplía 10 m; el valor es la media ponderada por área de los píxeles válidos que toca. La
huella es válida si al menos la mitad de su área ampliada cae en píxeles válidos. Se guardan el área,
el número de píxeles y la fracción válida.

**Detección óptica (Etapa 1):** la huella es detectada si el píxel de `clases.tif` que contiene su
centroide tiene clase ≥ 4 (umbral A, como la cifra publicada); sensibilidad con clase ≥ 5 (umbral B).

## 7. Partición

- Bloques H3 de resolución 8 con al menos una huella válida dentro de la caja.
- Estratos: bloques con al menos un positivo, y el resto.
- En cada estrato, mitad de los bloques a ajuste y mitad a prueba, al azar con `numpy.random`
  `default_rng(20240202)` sobre los identificadores H3 ordenados.
- La partición se escribe a disco y se registra su sha256 **antes** de leer cualquier señal.

## 8. Regla y métricas

1. **Umbral principal:** percentil 90 de la `z` combinada entre los negativos de ajuste (falsa
   alarma del 10 % en ajuste). Igual regla para cada geometría por separado y para la amplitud.
2. **Detección radar:** `z` combinada ≥ umbral. **Unión:** detección óptica o radar.
3. **En prueba, una sola evaluación:** sensibilidad total y por grado; falsa alarma en negativos y en
   el control lejano; precisión, F1, exactitud balanceada; AUC de ROC y de precisión-sensibilidad de
   `z` combinada; sensibilidad de Sentinel-2, de Sentinel-1 y de la unión, y de Sentinel-1 entre las
   no detectadas por Sentinel-2.
4. **Intervalos:** 95 % por remuestreo de bloques de prueba, 2.000 repeticiones, semilla 20240202,
   percentiles 2,5 y 97,5.
5. **Exploratorio, rotulado así:** regresión logística con `z` ascendente, `z` descendente, amplitud,
   pendiente y área de huella, ajustada en ajuste y evaluada en prueba (AUC y Brier).
6. **P5:** mediana de la `z` combinada por celda H3 de resolución 10 y 9 fuera de `P00_aoi`, con el
   umbral principal; rotulada "estimación de modelo".

## 9. Salidas y comunicación

- Contrato del sitio según OBS-0004, sección 7. La tabla por edificación queda en el repositorio, no
  en el sitio.
- "Daño probable según radar"; nunca "casa destruida". La vista dice que Copernicus EMS, SENAPRED y
  MINVU no validaron estos resultados.
- La cifra óptica se recalcula sobre las mismas huellas; la publicada de la Etapa 1 (muestra de 300
  puntos) se cita con su definición y no se modifica.

## 10. Puntos fijados por el dueño antes del sello (2026-11-11)

1. **Amplitud:** desde la amplitud de los mismos productos de ráfaga, a 20 m (opción a). Reemplaza al
   RTC de escenas completas que proponía OBS-0004.
2. **Confianza de las huellas:** ≥ 0,75 principal y ≥ 0,65 como sensibilidad (opción a).
3. **Falsa alarma objetivo del umbral:** 10 % en los negativos de ajuste (opción a).
