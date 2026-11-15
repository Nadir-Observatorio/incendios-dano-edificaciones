# Protocolo: daño a edificaciones en los incendios de Penco y Lirquén, enero de 2026

Nadir, línea Incendios. Segundo caso del método de OBS-0004 (Viña del Mar, 2024). Diseño: OBS-0006,
decisiones D1a, D2a y D3a del 2026-11-14.

Estado: SELLADO el 2026-11-14, antes de pedir productos a HyP3, antes de bajar cualquier insumo del
caso (EMSR859, Sentinel-2) y antes de leer cualquier señal. Su sha256 queda registrado en
`PROTOCOLO_dano-edificaciones_penco-2026_sellado_2026-11-14.sha256` y en OBS-0006. Todo cambio
posterior es una enmienda fechada con su motivo, escrita antes de ver el resultado que afecta, en un
archivo aparte; este archivo no se edita.

## 0. Qué se replica y qué cambia

Se replica sin cambios de método el protocolo sellado de Viña
(`PROTOCOLO_dano-edificaciones_sellado_2026-11-11.md`, sha256
`de1993790a4e7485aeef3d64749a490dd735679feb5575263bc61ca727387f5d`) con sus enmiendas 01
(`8ff741dde5bb5b2bbf391fe7652e5088640c2c02b0ac4c28818d0419a122bc1e`) y 02
(`82f1000d908f662e9e24596232a0832b493aa767d117af95012dd724d4341b27`): preguntas P1 a P5, señal `z`
de coherencia, valor por huella, partición por bloques H3 estratificada, umbral en el percentil 90 de
los negativos de ajuste, evaluación única en prueba e intervalos por remuestreo de bloques. Rigen
también las precisiones de la Enmienda 02 (sin amplitud, grilla, desviación muestral, máscaras).

| Elemento | Viña 2024 | Penco 2026 |
|---|---|---|
| Referencia de daño | EMSN188 P08, evaluación detallada (Risk and Recovery) | EMSR859, área 4, producto de grado (Rapid Mapping) sobre SPOT-6/7 del 25-01-2026 |
| Zona de negativos | `P00_aoi` de EMSN188 | Área 4 a 1 km o menos del área quemada del producto de grado (D1a) |
| Control lejano | Área de EMSR715 a más de 2 km de su área quemada | Área 4 a más de 2 km del área quemada del producto de grado |
| Satélites y órbitas | 1A; ascendente 18 y descendente 156 | 1C en ascendentes 91 y 164; 1A en descendente 156 |
| Combinada | Media de ascendente y descendente | Media de la ascendente (promedio de 91 y 164) y la descendente (D2a) |
| Óptico | `clases.tif` de la Etapa 1 | Se calcula con el mismo código y la misma regla (sección 7) |
| Huellas | Google Open Buildings, teselas `967` y `969` | Google Open Buildings, tesela `967` |
| Sistema de coordenadas | EPSG:32719 | EPSG:32718 |
| Semilla | 20240202 | 20260117 (D3a) |
| HyP3 | `INSAR_ISCE_BURST`, hyp3_isce2 3.0.2 | El mismo tipo de trabajo si aún se acepta; si no, sección 4 |

## 1. Preguntas

Descriptivas o de validación; no hay hipótesis confirmatorias.

- **P1.** Sensibilidad del radar: fracción de edificaciones con punto de daño de EMSR859 (área 4) cuya
  `z` combinada supera el umbral fijado en ajuste, medida en prueba, total y por grado.
- **P2.** Complementariedad: sensibilidad de Sentinel-2, de Sentinel-1 y de la unión en las mismas
  edificaciones de prueba; sensibilidad de Sentinel-1 entre las que Sentinel-2 no detectó.
- **P3.** Falsa alarma en negativos de prueba y en el control lejano.
- **P4.** Rendimiento por geometría (ascendente, descendente, combinada; y cada ascendente por
  separado, como descripción), por tercil de pendiente, de área de huella y de coherencia previa.
- **P5.** (Estimación de modelo) Celdas H3 de resolución 10 y 9 de la caja, fuera de la zona de
  negativos, con mediana de la `z` combinada sobre el umbral.

## 2. Lectura fijada de antemano

El valor del caso está en la comparación con Viña. Las cifras de Viña se leen de
`nadir-dano\derivados\t06\metricas.json` (sha256
`70960bb68a8f85c5427f7a21e063a3e2fc9362e8803a1559e4b99f35970686e0`, conjunto `principal`); el
código se detiene si la huella no calza. Las de Penco, de su propio `metricas.json` de prueba.

- **C1, detección:** el límite inferior del IC95 de la sensibilidad del radar (`z_comb.sensibilidad`)
  en Penco es al menos 0,50, y su límite superior alcanza o supera el límite inferior del IC95 de Viña.
- **C2, complemento:** el límite inferior del IC95 de la diferencia unión menos óptico
  (`p2.A.diferencia_union_menos_s2`) es mayor que 0.
- **C3, falsa alarma:** la falsa alarma en el control lejano (`z_comb.falsa_alarma_control`) es a lo
  más 0,05.

**Se sostiene:** se cumplen C1, C2 y C3. **No se sostiene:** falla C2, o el IC95 de la sensibilidad
del radar queda entero bajo el IC95 de Viña, o la falsa alarma en el control lejano supera 0,10.
**Se sostiene en parte:** cualquier otro caso; el informe dice qué criterio falló.

Lectura obligatoria en cualquier caso: la referencia de Penco es un grado rápido sobre imagen de
1,5 m y la de Viña una evaluación detallada; una diferencia de sensibilidad no se atribuye solo al
radar. Como apoyo descriptivo, sin peso en el veredicto, se compara la sensibilidad por grado,
empezando por "Destroyed", el grado menos ambiguo en ambas referencias.

## 3. Insumos y versiones

| Insumo | Versión fijada | Huella |
|---|---|---|
| EMSR859, `EMSR859_products.zip` (`productsPath` de la API pública de Copernicus EMS) | Área 4 "Conception", producto de grado, capa de puntos `builtUpP` versión 2 (la que lista la API el 14-11-2026) | sha256 al bajarlo, en `procedencia.toml` |
| Google Open Buildings, tesela S2 de nivel 4 `967` (banco, ya bajada para Viña) | Inferencia de mayo de 2023; última modificación 23-06-2023 | sha256 `b3b108abb4b711c3ff8c3fa4e96989172a6df227465578f20cd4f8494d8c1ed7` |
| Sentinel-1A y 1C, ráfagas IW VV (catálogo ASF del 14-11-2026) | Sección 4 | Nombres de ráfaga y fecha |
| Productos HyP3 | Versión del plugin que informe cada producto | sha256 al bajarlos |
| Sentinel-2 L2A, Earth Search, tesela 18HXE, bandas `nir08`, `swir22`, `scl` | Escenas según la regla de la sección 7 | sha256 por banda |
| Código óptico: paquete `severidad` de `Nadir-Observatorio/incendios-severidad` | Commit `81a4f54c43187c9709d645d91c3dfc0489a85d48`, sin modificar | El del commit |

Grados de EMSR859 a códigos de Viña: "Destroyed" 3, "Damaged" 2, "Possibly damaged" 1. "No visible
damage", "Not analysed" y cualquier otro valor no son puntos de daño.

## 4. Pares de imágenes

Hora del incendio: los focos que formaron el incendio de Penco y Lirquén se iniciaron en la mañana del
sábado 17-01-2026 y alcanzaron sectores poblados esa noche. Corte: es previa toda pasada que empieza
antes de 2026-01-17T03:00 UTC (00:00 del 17-01, hora de Chile).

Regla por órbita: el par del evento es la última pasada previa y la del mismo satélite 12 días
después; si esa no existe en el catálogo, se usa la pasada previa anterior del otro satélite que sí
tenga su par. La pila previa son los 6 pares consecutivos de 12 días del mismo satélite que terminan
en la referencia del evento; el posterior es el par de 12 días que empieza en la secundaria del evento.

**Ascendente**, órbita relativa 91, Sentinel-1C, 23:34 UTC (20:34 hora de Chile). Ráfagas
`195234_IW1`, `195235_IW1`, `195236_IW1`.

| Rol | Referencia | Secundaria |
|---|---|---|
| Previo 1 | 2025-10-31 | 2025-11-12 |
| Previo 2 | 2025-11-12 | 2025-11-24 |
| Previo 3 | 2025-11-24 | 2025-12-06 |
| Previo 4 | 2025-12-06 | 2025-12-18 |
| Previo 5 | 2025-12-18 | 2025-12-30 |
| Previo 6 | 2025-12-30 | 2026-01-11 |
| Evento | 2026-01-11 | 2026-01-23 |
| Posterior | 2026-01-23 | 2026-02-04 |

La pasada del 1A del 17-01-2026 (23:35 UTC, 20:35 hora de Chile) no se usa: el fuego ya avanzaba
hacia sectores poblados esa tarde.

**Ascendente**, órbita relativa 164, Sentinel-1C, 23:42 UTC (20:42 hora de Chile). Ráfagas
`352029_IW3`, `352030_IW3`, `352031_IW3`.

| Rol | Referencia | Secundaria |
|---|---|---|
| Previo 1 | 2025-11-05 | 2025-11-17 |
| Previo 2 | 2025-11-17 | 2025-11-29 |
| Previo 3 | 2025-11-29 | 2025-12-11 |
| Previo 4 | 2025-12-11 | 2025-12-23 |
| Previo 5 | 2025-12-23 | 2026-01-04 |
| Previo 6 | 2026-01-04 | 2026-01-16 |
| Evento | 2026-01-16 | 2026-01-28 |
| Posterior | 2026-01-28 | 2026-02-09 |

**Descendente**, órbita relativa 156, Sentinel-1A, 10:05 UTC (07:05 hora de Chile). Ráfagas
`334228_IW2`, `334229_IW2`, `334230_IW2`. La última previa es del 1C (2026-01-16), pero el catálogo
no tiene pasada descendente del 1C el 2026-01-28; por la regla se usa la del 1A.

| Rol | Referencia | Secundaria |
|---|---|---|
| Previo 1 | 2025-10-30 | 2025-11-11 |
| Previo 2 | 2025-11-11 | 2025-11-23 |
| Previo 3 | 2025-11-23 | 2025-12-05 |
| Previo 4 | 2025-12-05 | 2025-12-17 |
| Previo 5 | 2025-12-17 | 2025-12-29 |
| Previo 6 | 2025-12-29 | 2026-01-10 |
| Evento | 2026-01-10 | 2026-01-22 |
| Posterior | 2026-01-22 | 2026-02-03 |

Pedido: 8 pares por ráfaga, 72 trabajos, polarización VV, 5x1 *looks* (20 m), sin máscara de agua.
Tipo de trabajo `INSAR_ISCE_BURST`; si HyP3 ya no lo acepta, `INSAR_ISCE_MULTI_BURST` con una sola
ráfaga por trabajo y las mismas opciones, y se informa. Si alguna ráfaga no tiene una fecha al
momento del pedido, el par se omite y se informa; no se reemplaza por otra fecha. Cada geometría usa
un solo satélite; P4 lo dice al comparar geometrías.

## 5. Huellas y referencia

1. **Área de trabajo:** caja −73,059 a −72,769 de longitud y −36,948 a −36,618 de latitud (la
   envolvente del área 4 de EMSR859 según la API de Copernicus EMS), en UTM 18S (EPSG:32718).
2. **Huellas:** Google Open Buildings bajo CC BY 4.0, confianza ≥ 0,75 (principal) y ≥ 0,65
   (sensibilidad), con centroide en la caja.
3. **Emparejamiento:** cada punto de daño va a la huella que lo contiene; si no hay, a la más cercana
   a 10 m o menos; si no, queda "sin huella" y se informa. Una huella con varios puntos toma el grado
   mayor.
4. **Área quemada de referencia:** `observedEventA` del producto de grado del área 4; si ese producto
   no la trae, la de la última delineación del área 4 (MONIT03, Pléiades del 24-01-2026), y se informa.
   **Área de interés:** `areaOfInterestA` del área 4.
5. **Positivos:** huellas con punto de daño. **Negativos:** huellas con centroide en el área de interés,
   a 1 km o menos del área quemada de referencia y sin punto de daño a 10 m o menos. **Control
   lejano:** huellas con centroide en el área de interés, a más de 2 km del área quemada de referencia
   y sin punto de daño asignado. Las huellas de la franja de 1 a 2 km no entran a P3; se informa
   cuántas son. Las distancias se miden desde el centroide.
6. **Completitud:** fracción de puntos de daño sin huella. Google infirió las huellas en mayo de
   2023; lo construido después no está.

## 6. Señales

1. **Coherencia por píxel y órbita:** `z = (m − c_evento) / max(s, 0,05)`, con `m` y `s` la media y la
   desviación estándar muestral de los 6 pares previos (mínimo 4 válidos; si no, el píxel queda sin
   dato).
2. **Grilla:** las capas `_corr`, `_lv_theta`, `_lv_phi` y `_dem` de cada producto se remuestrean con
   interpolación bilineal a una grilla común de 20 m en EPSG:32718, alineada a múltiplos de 20 m y que
   cubre la caja; el 0 de origen es sin dato. El mosaico entre ráfagas de una órbita y fecha es la
   media de los valores válidos.
3. **Máscaras:** inversión y sombra con la geometría y el modelo de elevación de cada producto, con
   las convenciones y comprobaciones del punto 3.2 de la Enmienda 02; ángulo horizontal esperado cerca
   de 180° en las dos ascendentes y cerca de 0° en la descendente. Los píxeles sin modelo de elevación
   quedan sin dato.
4. **Persistencia (descriptiva):** `z_post = (m − c_posterior) / max(s, 0,05)`.

## 7. Valor por huella y detección óptica

Valor por huella y órbita: media ponderada por el área exacta de intersección entre la huella
ampliada 10 m y cada píxel válido de 20 m; la huella es válida en esa órbita si el área válida es al
menos la mitad del área ampliada. Pendiente por huella desde el mismo mosaico de elevación.

**Combinada (D2a):** `z_asc` es la media de `z` de las órbitas 91 y 164 válidas en la huella; `z_des`
es la `z` de la órbita 156; la `z` combinada es la media de `z_asc` y `z_des` válidas.

**Detección óptica:** `severidad.calculo.severity` del commit fijado, sin modificar, sobre la caja de
la sección 5, con dos escenas L2A de la tesela 18HXE de Earth Search:
- previa: la de menor fracción de píxeles de la caja con `scl` en {0, 3, 8, 9, 10} entre el
  2025-12-17 y el 2026-01-16;
- posterior: la de menor fracción con la misma regla entre el 2026-01-22 y el 2026-02-21;
- empates: la más cercana al 17-01-2026; si dos ítems comparten fecha, el de menor número de
  procesamiento en su identificador. La elección lee solo la banda `scl`.

Clases de Key y Benson (2006) del código; la huella es detectada si el píxel que contiene su centroide
tiene clase ≥ 4 (umbral A, todas las clases quemadas); sensibilidad con clase ≥ 5 (umbral B). El
ráster de clases se guarda con su huella de contenido.

## 8. Partición

- **Bloques:** celdas H3 de resolución 8 que contienen el centroide de al menos una huella con
  confianza ≥ 0,65 de la caja, o al menos un punto de daño. La misma partición sirve para los dos
  conjuntos de huellas; las huellas que después resulten inválidas por máscara quedan fuera de las
  métricas, sin mover bloques.
- **Estratos:** "con daño" si el bloque contiene al menos un punto de daño (por su posición); si no,
  "sin daño".
- **Reparto:** en cada estrato, identificadores H3 ordenados, permutados con
  `numpy.random.default_rng(20260117).permutation` (un solo generador, primero "con daño" y después
  "sin daño"); la primera mitad entera (`n // 2`) a ajuste y el resto a prueba.
- Huellas y puntos se asignan por la celda de su centroide o posición. La partición se escribe a disco
  y se registra su sha256 antes de leer cualquier señal.

## 9. Regla y métricas

1. **Umbral principal:** percentil 90 de la `z` combinada entre los negativos de ajuste. Igual regla
   para `z_asc`, `z_des` y cada ascendente por separado.
2. **Detección radar:** `z` combinada ≥ umbral. **Unión:** detección óptica o radar.
3. **En prueba, una sola evaluación:** sensibilidad total y por grado; falsa alarma en negativos y en
   el control lejano; precisión, F1, exactitud balanceada; AUC de ROC y de precisión-sensibilidad; P2
   con los umbrales ópticos A y B; persistencia.
4. **Intervalos:** 95 % por remuestreo de bloques de prueba, 2.000 repeticiones, semilla 20260117,
   percentiles 2,5 y 97,5.
5. **Exploratorio, rotulado así:** regresión logística con `z_asc`, `z_des`, pendiente y área de huella,
   ajustada en ajuste y evaluada en prueba (AUC y Brier). No va al sitio.
6. **P5:** mediana de la `z` combinada por celda H3 de resolución 10 y 9 de la caja, para celdas cuyo
   centro está a más de 1 km del área quemada de referencia, con el umbral principal; verificación con
   la delineación MONIT03 (cuántas la tocan y cuántas quedan a menos de 500 m). Rotulada "estimación de
   modelo".
7. **Comparación con Viña:** una tabla con las mismas claves de `metricas.json` en los dos casos y sus
   intervalos, y el veredicto de la sección 2, calculado por el código.

## 10. Salidas y comunicación

- Contrato del sitio con la misma estructura que `nadir-dano\sitio\` (`resumen.json` con huellas de
  todo); la tabla por edificación queda en el repositorio, no en el sitio.
- "Daño probable según radar"; nunca "casa destruida". EMSR859 es referencia, no verdad: un grado
  rápido por fotointerpretación sobre una imagen posterior. La vista dice que Copernicus EMS, SENAPRED
  y MINVU no validaron estos resultados. Sin mapa por vivienda.

## 11. Detenciones previstas

La tarea se detiene, sin leer señales, y se escribe una enmienda si:
1. `EMSR859_products.zip` no trae la capa de puntos del área 4 en la versión fijada, o el campo de grado
   no tiene los valores de la sección 3;
2. la capa de áreas construidas (`builtUpA`) del producto de grado trae elementos con grado de daño;
3. ninguna escena de Sentinel-2 de una ventana tiene menos de la mitad de la caja válida, o el código
   óptico rechaza el par (agua o grilla);
4. falta la evaluación de alguna órbita completa en HyP3.
