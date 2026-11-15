*Read in English: [README.en.md](README.en.md)*

# Daño a edificaciones en el incendio de Viña del Mar, febrero de 2024

El incendio del 2 y 3 de febrero de 2024 destruyó miles de viviendas en Viña del Mar y Quilpué. El
satélite óptico Sentinel-2 mide bien la vegetación quemada, pero en los cerros poblados se le escapa
buena parte de las casas dañadas: techos sin vegetación, píxeles de 20 m que mezclan casa, calle y
patio. Este repositorio responde una pregunta concreta: **¿cuánto de ese daño ve el radar de
Sentinel-1, que no depende de la vegetación ni de las nubes, y cuánto suma al óptico?**

La señal es la **pérdida de coherencia interferométrica**: cuando una casa colapsa o pierde su techo,
deja de devolver al radar la misma señal entre dos pasadas. Todo se calcula con datos abiertos y
gratuitos, y se valida contra la referencia oficial del Servicio de Gestión de Emergencias de
Copernicus.

Parte de [Nadir](https://nadir-observatorio.github.io/), línea Incendios. Caso hermano:
[severidad del incendio con Sentinel-2](https://github.com/Nadir-Observatorio/incendios-severidad).

<!-- Las cifras de este archivo las escribe scripts/escribir_readme.py desde resultados/resumen_sitio.json; no se editan a mano. -->

## Resultados

Partición de prueba, evaluada **una sola vez** con el umbral fijado en la partición de ajuste.
Intervalos al 95 % por remuestreo de bloques espaciales. Referencia: puntos de daño de Copernicus
EMSN188 asignados a huellas de edificios de Google Open Buildings.

| Pregunta | Resultado |
|---|---|
| ¿Qué parte de las edificaciones dañadas detecta el radar? | **{p1_sensibilidad_radar}** {p1_sensibilidad_radar_ic} |
| ... destruidas | {p1_sensibilidad_destruidas} {p1_sensibilidad_destruidas_ic} |
| ... dañadas | {p1_sensibilidad_danadas} {p1_sensibilidad_danadas_ic} |
| ... con posible daño | {p1_sensibilidad_posible_dano} {p1_sensibilidad_posible_dano_ic} |
| ¿Y el óptico (Sentinel-2) en las mismas edificaciones? | {p2_sensibilidad_optico} {p2_sensibilidad_optico_ic} |
| ¿Y los dos juntos? | **{p2_sensibilidad_union}** {p2_sensibilidad_union_ic} |
| ¿Cuánto suma el radar al óptico? | {p2_suma_del_radar} puntos porcentuales {p2_suma_del_radar_ic} |
| De lo que el óptico no vio, ¿cuánto recupera el radar? | {p2_rescate_radar} {p2_rescate_radar_ic} |
| Falsa alarma en edificaciones sin daño registrado (área de EMSN188) | {p3_falsa_alarma_negativos} {p3_falsa_alarma_negativos_ic} |
| Falsa alarma lejos del fuego (a más de 2 km del área quemada de EMSR715) | {p3_falsa_alarma_control} {p3_falsa_alarma_control_ic} |
| Precisión de las marcas del radar | {p3_precision} {p3_precision_ic} |
| Área bajo la curva ROC | {auc_roc} {auc_roc_ic} |
| Solo órbita ascendente / solo descendente | {p4_sensibilidad_ascendente} / {p4_sensibilidad_descendente} |
| Con huellas de confianza ≥ 0,65 (robustez) | {robustez_sensibilidad_radar_065} {robustez_sensibilidad_radar_065_ic} |

**Fuera de la zona afectada, el radar no inventa un área de daño.** Fuera del área analizada por
EMSN188, {p5_r10_celdas_sobre_umbral} de {p5_r10_celdas} celdas H3 de resolución 10 superan el umbral; de ellas,
las que tocan el área quemada oficial de EMSR715 son {verificacion_p5_sobre_umbral_que_tocan_area_quemada_emsr715}. Son celdas sueltas en la ciudad (obras,
cambios urbanos), no una zona de daño omitida.

**Relación con el caso de severidad.** La cifra óptica de esta tabla usa la regla más amplia del caso
de severidad (todas las clases quemadas), la misma con que ese caso midió su omisión en la interfaz
urbana con EMSN188, sobre una muestra de puntos: las dos mediciones concuerdan. Con el umbral
calibrado de ese caso, el óptico vería todavía menos daño urbano, así que la comparación favorece al
óptico.

![Fracción de edificaciones dañadas detectada por el óptico y por la unión](figuras/fig_optico_vs_union.png)

![Sensibilidad con intervalos](figuras/fig_sensibilidad.png)

## Cómo se lee

- **"Daño probable según radar"**, no "casa destruida". El radar mide que algo cambió, no qué cambió:
  remoción de escombros y obras de emergencia también bajan la coherencia.
- La señal es de 20 m: por edificación es una señal de su entorno. Los resultados públicos se dan por
  celda H3, nunca por vivienda.
- EMSN188 es una fotointerpretación oficial sobre una imagen posterior, no verdad de terreno; las
  edificaciones sin punto son "sin daño registrado", no "sin daño".
- **Copernicus EMS, SENAPRED y MINVU no validaron estos resultados.**

## Método

1. **Pares de Sentinel-1A** (en febrero de 2024 solo operaba ese satélite): por órbita, seis pares
   previos de 12 días, el par del evento y un par posterior. Ascendente, órbita 18, 20:28 hora de
   Chile, evento del 23-01 al 04-02-2024. Descendente, órbita 156, 07:04 hora de Chile, evento del
   02-02 al 14-02-2024 (la pasada del 2 de febrero es anterior al fuego). 56 productos de coherencia
   a 20 m pedidos a [ASF HyP3](https://hyp3-docs.asf.alaska.edu/) (`INSAR_ISCE_BURST`, 5x1 looks).
2. **Señal por píxel:** `z = (m − c_evento) / max(s, 0,05)`, con `m` y `s` la media y la desviación de
   la coherencia de los pares previos; grilla común de 20 m en UTM 19S; máscara de inversión y sombra
   con la geometría de cada producto.
3. **Por edificación:** media ponderada por área exacta de la huella ampliada 10 m; señal combinada =
   media de las dos órbitas.
4. **Referencia:** cada punto de daño de EMSN188 P08 se asigna a la huella que lo contiene o a la más
   cercana a 10 m o menos ({fraccion_puntos_sin_huella} de los {puntos_emsn188} puntos quedó sin huella).
5. **Partición:** bloques H3 de resolución 8, estratificados, mitad ajuste y mitad prueba, escrita a
   disco con su huella antes de leer cualquier señal.
6. **Umbral:** percentil 90 de la señal en los edificios sin daño registrado de ajuste
   (z = {umbral_z}).

Protocolo sellado antes de pedir datos y dos enmiendas escritas antes de leer señales, en
[`protocolo/`](protocolo/), con sus huellas sha256.

## Reproducir

Requisitos: Python 3.12, una cuenta gratuita de [Earthdata Login](https://urs.earthdata.nasa.gov/) y
unos 15 GB libres.

```text
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
python scripts/t01_catalogo.py <salida_catalogo> <EMSN188_GeospatialData.zip>
python scripts/t02_hyp3.py <carpeta_caso> <banco_hyp3> <registro.txt>
python scripts/t03_open_buildings.py <banco_open_buildings>
copy casos\vina-2024\rutas.ejemplo.toml casos\vina-2024\rutas.toml
python scripts/t04_huellas_particion.py casos/vina-2024 <carpeta_trabajo>
python scripts/t05_senales.py casos/vina-2024 <carpeta_trabajo>
python scripts/t06_evaluacion.py casos/vina-2024 <carpeta_trabajo>
python scripts/t07_sitio.py casos/vina-2024 <carpeta_trabajo>
```

Para `t02_hyp3.py`, `<carpeta_caso>` contiene los archivos de `protocolo/`. Desde `t04`, los parámetros
del caso salen de [`casos/vina-2024/caso.toml`](casos/vina-2024/caso.toml) y las rutas a los insumos de
`casos/vina-2024/rutas.toml`, que se copia de `rutas.ejemplo.toml` y se completa (no se sube). `t04` a
`t07` escriben en `<carpeta_trabajo>/derivados/` y `<carpeta_trabajo>/sitio/`, y cada una se detiene si
la huella de la etapa anterior registrada en `[fijadas]` de `caso.toml` falta o no calza. Las tareas
comprueban las huellas sha256 del protocolo, de las enmiendas, de las referencias y de cada producto
antes de calcular. Los pares
exactos están en [`resultados/pares_hyp3.json`](resultados/pares_hyp3.json); `clases.tif` es el
mapa de severidad del [caso hermano](https://github.com/Nadir-Observatorio/incendios-severidad).
Las referencias de Copernicus EMS se bajan de sus páginas
([EMSN188](https://riskandrecovery.emergency.copernicus.eu/EMSN188),
[EMSR715](https://rapidmapping.emergency.copernicus.eu/EMSR715)); no se redistribuyen aquí.

Pruebas y calidad: `pytest`, `ruff check scripts tests`, `mypy`.

## Límites

- Un solo satélite: el par del evento abarca 12 días e incluye las primeras obras.
- Una casa quemada con la estructura en pie puede conservar la coherencia.
- El daño se concentra en pocos bloques, por eso el intervalo de la sensibilidad es ancho; la ventaja
  de la unión sobre el óptico es más firme.
- El umbral se fijó para 10 % de falsa alarma en ajuste y dio menos en prueba: los edificios sin daño
  de las dos particiones difieren en el espacio.
- Sin amplitud del radar: los productos no la traen por fecha (enmienda 02).

## Otros casos

- [Penco y Lirquén, incendios de enero de 2026](casos/penco-2026/): caso cerrado sin cifras de radar.
  El producto de grado de Copernicus EMS EMSR859 para esa zona marca con un solo grado, "Possibly
  damaged", casi todas las edificaciones dentro del área quemada. Como no distingue el daño de cada una,
  el caso no se puede comparar con Viña.

## Datos y licencias

Código: MIT ([`LICENSE`](LICENSE)). Resultados y figuras: CC BY 4.0, con los avisos de
[`LICENSE-DATA.md`](LICENSE-DATA.md).

Hecho por Camilo López Barra, geógrafo.
