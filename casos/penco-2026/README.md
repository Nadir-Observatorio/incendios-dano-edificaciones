*Read in English: [README.en.md](README.en.md)*

# Caso cerrado: Penco y Lirquén, incendios de enero de 2026

Parte del repositorio [incendios-dano-edificaciones](../../README.md) de [Nadir](https://nadir-observatorio.github.io/), línea Incendios.

Este caso iba a repetir en Penco y Lirquén (región del Biobío) el método de Viña del Mar 2024 de este
repositorio: medir con la pérdida de coherencia del radar Sentinel-1 qué parte de las edificaciones
dañadas se detecta, y validarlo contra los puntos de daño de Copernicus EMS. El protocolo se selló el
14 de noviembre de 2026, antes de pedir cualquier producto de radar a ASF HyP3
([`PROTOCOLO_dano-edificaciones_penco-2026_sellado_2026-11-14.md`](PROTOCOLO_dano-edificaciones_penco-2026_sellado_2026-11-14.md),
sha256 `ec6a3cd5651314d6d4ea40149a0e29795103d0802c0d1229d8fa4b6445a43f44`).

<!-- Las cifras de este archivo las escribe scripts/escribir_readme_caso.py desde los informes del caso; no se editan a mano. -->

## Qué mostró la referencia

La referencia prevista era el producto de grado de la activación EMSR859 de Copernicus EMS para el
área 4 "Conception", hecho sobre una imagen SPOT-6/7 del 25 de enero de 2026.

- Sus 6.765 puntos de edificación tienen un solo grado,
  "Possibly damaged". No hay ningún "Destroyed" ni "Damaged".
- De las 4.423 huellas de Google Open
  Buildings (confianza ≥ 0,75) con centro en el área quemada del producto
  (12.781,3 ha), 4.420
  tienen punto de daño (99,93 %).
  Fuera de esa área, a 1 km o menos, tienen punto 49
  de 23.708.
- En Viña, la referencia EMSN188 separa tres grados (5.694
  "Destroyed", 570 "Damaged" y 1.011
  "Possible damage") y deja con punto el 66,4 %
  de las huellas con centro en el área quemada de EMSR715. Es una evaluación edificación por edificación.

Copernicus EMS describe la activación EMSR859 como cartografía de la extensión del incendio
([aviso de la activación](https://mapping.emergency.copernicus.eu/news/wildfires-in-the-biobio-and-nuble-regions-chile-emsr859/)).
En el área 4, el grado coincide casi por completo con estar dentro del área quemada, así que
no distingue el daño de cada edificación. Contra esa referencia, una sensibilidad del radar en Penco
mediría la fracción de edificaciones del área quemada con señal y no se podría comparar con la de Viña.

## Decisión

El caso se cerró con la [enmienda 01](ENMIENDA_01_penco-2026_2026-11-14.md) (detención 1 del protocolo,
porque faltan los grados "Damaged" y
"Destroyed"). No se pidieron trabajos a HyP3, no se calculó
la detección óptica de Sentinel-2 y no se escribió la partición. Por eso no hay cifras de radar para Penco.

El caso se reabre solo con una referencia por edificación con grados de daño para Penco y Lirquén, y con
una enmienda nueva escrita antes de pedir datos de radar.

## Los dos informes

| Archivo | Qué responde | Bytes | sha256 |
|---|---|---|---|
| [`derivados/t03b/inspeccion_emsr859.json`](derivados/t03b/inspeccion_emsr859.json) | Productos del área 4 en el zip, capas, campos y detenciones 1 y 2 | 6.442 | `a9a05f90d180bfb75199508c0133de7dfc9186134dc0347abcba6e2f75e9de2b` |
| [`derivados/t03c/referencias.json`](derivados/t03c/referencias.json) | Qué marca el grado en Penco y en Viña, con las mismas medidas | 6.740 | `937c827fa7f226ee69005f8efab6799fa1b91755112497feaee5ad025a87b5b6` |

Son los informes del 14 de noviembre de 2026 que cita la enmienda. Se reproducen en contenido, no en
huella:

- `referencias.json` guarda la hora de su ejecución en el campo `generado` (2026-11-14T13:50:52-03:00).
- `inspeccion_emsr859.json` salió de la primera versión de `t03b_emsr859.py`, que aplicaba la detención
  1 solo si no aparecía ninguno de los grados fijados; por eso su campo `deteccion_1` no marca detención.
  La versión de este repositorio aplica la lectura estricta del protocolo y la marcaría, igual que
  `deteccion_1_lectura_estricta` en `referencias.json`. La enmienda 01 registra esa corrección.

## Rehacer los informes

Insumos, que no se redistribuyen aquí:

- `EMSR859_products.zip`, desde el `productsPath` de la API pública de Copernicus EMS
  (https://rapidmapping.emergency.copernicus.eu/backend/dashboard-api/public-activations/?code=EMSR859). El 14 de noviembre de 2026 pesaba 740.725.752 bytes, con sha256
  `d8c07cfdff3724a7cc2ce0f659ef464b24cf9dd9eb6fe5dea018a79a39958601` y fecha de modificación del servidor Fri, 30 Jan 2026 15:45:23 GMT.
  Si Copernicus regenera el zip, la huella cambia.
- Google Open Buildings, tesela `967_buildings.csv.gz` (CC BY 4.0).
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
Conception (AOI04): Grading Map. Licencias y avisos en
[`LICENSE-DATA.md`](../../LICENSE-DATA.md).

Hecho por Camilo López Barra, geógrafo.
