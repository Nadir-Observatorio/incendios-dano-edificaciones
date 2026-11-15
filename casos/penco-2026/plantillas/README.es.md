*Read in English: [README.en.md](README.en.md)*

# Caso cerrado: Penco y Lirquén, incendios de enero de 2026

Parte del repositorio [incendios-dano-edificaciones](../../README.md) de [Nadir](https://nadir-observatorio.github.io/), línea Incendios.

Este caso iba a repetir en Penco y Lirquén (región del Biobío) el método de Viña del Mar 2024 de este
repositorio: medir con la pérdida de coherencia del radar Sentinel-1 qué parte de las edificaciones
dañadas se detecta, y validarlo contra los puntos de daño de Copernicus EMS. El protocolo se selló el
14 de noviembre de 2026, antes de pedir cualquier producto de radar a ASF HyP3
([`PROTOCOLO_dano-edificaciones_penco-2026_sellado_2026-11-14.md`](PROTOCOLO_dano-edificaciones_penco-2026_sellado_2026-11-14.md),
sha256 `{caso:documento/0/sha256}`).

<!-- Las cifras de este archivo las escribe scripts/escribir_readme_caso.py desde los informes del caso; no se editan a mano. -->

## Qué mostró la referencia

La referencia prevista era el producto de grado de la activación EMSR859 de Copernicus EMS para el
área {insp:area/numero} "{insp:area/nombre}", hecho sobre una imagen SPOT-6/7 del {insp:productos_api/1/imagenes/0|fecha}.

- Sus {refs:penco/puntos|ent} puntos de edificación tienen un solo grado,
  "Possibly damaged". No hay ningún "Destroyed" ni "Damaged".
- De las {refs:penco/conjuntos/principal/huellas_centroide_en_quemado|ent} huellas de Google Open
  Buildings (confianza ≥ 0,75) con centro en el área quemada del producto
  ({refs:penco/area_quemada_ha|dec1} ha), {refs:penco/conjuntos/principal/huellas_en_quemado_con_punto|ent}
  tienen punto de daño ({refs:penco/conjuntos/principal/fraccion_huellas_en_quemado_con_punto|pct2}).
  Fuera de esa área, a 1 km o menos, tienen punto {refs:penco/conjuntos/principal/huellas_a_1km_o_menos_fuera_con_punto|ent}
  de {refs:penco/conjuntos/principal/huellas_a_1km_o_menos_fuera_del_quemado|ent}.
- En Viña, la referencia EMSN188 separa tres grados ({refs:vina/por_grado/Destroyed/puntos|ent}
  "Destroyed", {refs:vina/por_grado/Damaged/puntos|ent} "Damaged" y {refs:vina/por_grado/Possible damage/puntos|ent}
  "Possible damage") y deja con punto el {refs:vina/conjuntos/principal/fraccion_huellas_en_quemado_con_punto|pct1}
  de las huellas con centro en el área quemada de EMSR715. Es una evaluación edificación por edificación.

Copernicus EMS describe la activación EMSR859 como cartografía de la extensión del incendio
([aviso de la activación](https://mapping.emergency.copernicus.eu/news/wildfires-in-the-biobio-and-nuble-regions-chile-emsr859/)).
En el área {insp:area/numero}, el grado coincide casi por completo con estar dentro del área quemada, así que
no distingue el daño de cada edificación. Contra esa referencia, una sensibilidad del radar en Penco
mediría la fracción de edificaciones del área quemada con señal y no se podría comparar con la de Viña.

## Decisión

El caso se cerró con la [enmienda 01](ENMIENDA_01_penco-2026_2026-11-14.md) (detención 1 del protocolo,
porque faltan los grados "{refs:deteccion_1_lectura_estricta/grados_ausentes/0}" y
"{refs:deteccion_1_lectura_estricta/grados_ausentes/1}"). No se pidieron trabajos a HyP3, no se calculó
la detección óptica de Sentinel-2 y no se escribió la partición. Por eso no hay cifras de radar para Penco.

El caso se reabre solo con una referencia por edificación con grados de daño para Penco y Lirquén, y con
una enmienda nueva escrita antes de pedir datos de radar.

## Los dos informes

| Archivo | Qué responde | Bytes | sha256 |
|---|---|---|---|
| [`derivados/t03b/inspeccion_emsr859.json`](derivados/t03b/inspeccion_emsr859.json) | Productos del área {insp:area/numero} en el zip, capas, campos y detenciones 1 y 2 | {insp:@bytes|ent} | `{insp:@sha256}` |
| [`derivados/t03c/referencias.json`](derivados/t03c/referencias.json) | Qué marca el grado en Penco y en Viña, con las mismas medidas | {refs:@bytes|ent} | `{refs:@sha256}` |

Son los informes del 14 de noviembre de 2026 que cita la enmienda. Se reproducen en contenido, no en
huella:

- `referencias.json` guarda la hora de su ejecución en el campo `generado` ({refs:generado}).
- `inspeccion_emsr859.json` salió de la primera versión de `t03b_emsr859.py`, que aplicaba la detención
  1 solo si no aparecía ninguno de los grados fijados; por eso su campo `deteccion_1` no marca detención.
  La versión de este repositorio aplica la lectura estricta del protocolo y la marcaría, igual que
  `deteccion_1_lectura_estricta` en `referencias.json`. La enmienda 01 registra esa corrección.

## Rehacer los informes

Insumos, que no se redistribuyen aquí:

- `EMSR859_products.zip`, desde el `productsPath` de la API pública de Copernicus EMS
  ({proc:archivo/0/url}). El 14 de noviembre de 2026 pesaba {proc:archivo/1/bytes|ent} bytes, con sha256
  `{proc:archivo/1/sha256}` y fecha de modificación del servidor {proc:archivo/1/ultima_modificacion_servidor}.
  Si Copernicus regenera el zip, la huella cambia.
- Google Open Buildings, tesela `{caso:metodo/teselas_open_buildings/0}` (CC BY 4.0).
- Solo para la parte de Viña de `t03c_referencias.py`: `EMSN188_GeospatialData.zip` y
  `EMSR715_products.zip`, que `referencia.leer` verifica contra `casos/vina-2024/caso.toml`.

```text
copy casos\penco-2026\rutas.ejemplo.toml casos\penco-2026\rutas.toml
copy casos\vina-2024\rutas.ejemplo.toml casos\vina-2024\rutas.toml
python scripts/t03b_emsr859.py casos/penco-2026 <carpeta_trabajo>
python scripts/t03c_referencias.py casos/penco-2026 casos/vina-2024 <carpeta_trabajo>
python scripts/escribir_readme_caso.py casos/penco-2026 --verificar
```

Se completan las rutas de los dos `rutas.toml` antes de correr. `t03b_emsr859.py` baja el zip y la
respuesta de la API a la carpeta de `referencia_zip` y escribe allí su propia procedencia;
[`procedencia_emsr859_2026-11-14.toml`](procedencia_emsr859_2026-11-14.toml) es el registro de la
descarga del 14 de noviembre de 2026, para comparar huellas, y no se copia al banco. Ninguna de las dos
tareas sobrescribe un informe que ya existe en `<carpeta_trabajo>`.

`referencia.leer` no lee el tipo `emsr859_rapid_mapping` del [`caso.toml`](caso.toml) de Penco: solo
`t03b_emsr859.py` y `t03c_referencias.py` leen esta referencia, y `t04` a `t07` no corren para este caso.

## Cómo se lee

- Copernicus EMS es la referencia, no la verdad de terreno.
- Copernicus EMS, SENAPRED y MINVU no validaron estos informes.

Cita del producto: Copernicus Emergency Management Service (© 2026 European Union), [EMSR859]
{insp:area/nombre} (AOI0{insp:area/numero}): Grading Map. Licencias y avisos en
[`LICENSE-DATA.md`](../../LICENSE-DATA.md).

Hecho por Camilo López Barra, geógrafo.
