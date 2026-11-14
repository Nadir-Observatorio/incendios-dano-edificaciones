"""Tarea 07 del caso de dano a edificaciones (etapa E6): contrato de datos para el sitio.

Escribe todo en `sitio.nuevo\\`, verifica (huellas, cifras contra metricas.json, tamano de figuras,
archivos sin registro) y solo entonces reemplaza `sitio\\`. Ninguna cifra se escribe a mano: todas se
leen de metricas.json (tarea 06) o de los resumenes de las tareas 04 y 05. Incluye el cruce de P5 con
la delineacion oficial de EMSR715.

Uso: python t07_sitio.py <carpeta_caso> <zip_emsn188> <zip_emsr715>
"""

from __future__ import annotations

import datetime as dt
import hashlib
import io
import json
import shutil
import sys
import zipfile
from pathlib import Path
from typing import Any

import geopandas as gpd
import h3
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pyogrio
import rasterio
import shapely
from matplotlib.axes import Axes
from matplotlib.collections import PatchCollection
from matplotlib.figure import Figure
from matplotlib.patches import Polygon as MplPolygon
from PIL import Image

CRS = "EPSG:32719"
METRICAS_SHA256 = "70960bb68a8f85c5427f7a21e063a3e2fc9362e8803a1559e4b99f35970686e0"
GDB = "Geospatial_data/GDB/EMSN188_STD_UTM19S_r02_v01.gdb"
PESO_MAX_FIG = 450 * 1024
PESO_MAX_TOTAL = 25 * 1024 * 1024

LICENCIA = "CC BY 4.0"
AVISOS = [
    "Contains modified Copernicus Sentinel data 2023-2024, processed by ESA.",
    "Sentinel-1 Burst InSAR products processed by ASF DAAC HyP3 2026 using ISCE software "
    "(hyp3_isce2 3.0.2, ISCE 2.6.5).",
    "Copernicus Emergency Management Service (© 2024 European Union), EMSN188 P08 Detailed damage "
    "assessment, y EMSR715 AOI01 Delineation Map v2.",
    "Google Open Buildings (CC BY 4.0).",
    "Severidad de Sentinel-2: Nadir, incendio de Viña del Mar 2024 (CC BY 4.0).",
]
LINEA_FUENTE = (
    "Fuente: Nadir. Sentinel-1 (Copernicus, procesado por ASF HyP3), Copernicus EMS EMSN188 y "
    "EMSR715, Google Open Buildings. CC BY 4.0. No validado por Copernicus EMS, SENAPRED ni MINVU."
)

# Cifras publicadas: identificador -> (conjunto, clave en metricas_prueba, definicion)
CIFRAS = {
    "p1_sensibilidad_radar": (
        "principal",
        "z_comb.sensibilidad",
        "Fraccion de edificaciones con dano segun EMSN188 detectadas por el radar (prueba)",
    ),
    "p1_sensibilidad_destruidas": ("principal", "z_comb.sensibilidad.Destroyed", "Idem, grado Destroyed"),
    "p1_sensibilidad_danadas": ("principal", "z_comb.sensibilidad.Damaged", "Idem, grado Damaged"),
    "p1_sensibilidad_posible_dano": ("principal", "z_comb.sensibilidad.Possible damage", "Idem, grado Possible damage"),
    "p2_sensibilidad_optico": (
        "principal",
        "p2.A.sensibilidad_s2",
        "Fraccion detectada por Sentinel-2 (Etapa 1, umbral A) en las mismas edificaciones",
    ),
    "p2_sensibilidad_union": ("principal", "p2.A.sensibilidad_union", "Fraccion detectada por optico o radar"),
    "p2_suma_del_radar": ("principal", "p2.A.diferencia_union_menos_s2", "Union menos optico solo"),
    "p2_rescate_radar": (
        "principal",
        "p2.A.s1_entre_no_detectadas_s2",
        "Fraccion detectada por el radar entre las que el optico no detecto",
    ),
    "p3_falsa_alarma_negativos": (
        "principal",
        "z_comb.falsa_alarma_negativos",
        "Edificaciones sin dano registrado en el area de EMSN188 marcadas por el radar",
    ),
    "p3_falsa_alarma_control": (
        "principal",
        "z_comb.falsa_alarma_control",
        "Edificaciones a mas de 2 km del area quemada de EMSR715 marcadas por el radar",
    ),
    "p3_precision": ("principal", "z_comb.precision", "Fraccion de marcas del radar con dano registrado"),
    "auc_roc": ("principal", "z_comb.auc_roc", "Area bajo la curva ROC de la senal combinada"),
    "p4_sensibilidad_ascendente": ("principal", "z_asc.sensibilidad", "Sensibilidad solo con la orbita ascendente"),
    "p4_sensibilidad_descendente": ("principal", "z_des.sensibilidad", "Sensibilidad solo con la orbita descendente"),
    "robustez_sensibilidad_radar_065": (
        "sensibilidad",
        "z_comb.sensibilidad",
        "Sensibilidad del radar con huellas de confianza >= 0,65",
    ),
}


def sha256(ruta: Path) -> str:
    h = hashlib.sha256()
    with ruta.open("rb") as f:
        for bloque in iter(lambda: f.read(1 << 22), b""):
            h.update(bloque)
    return h.hexdigest()


def emsr715(zip_ruta: Path, tmp: Path) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    with zipfile.ZipFile(zip_ruta) as externo:
        interno = externo.read("EMSR715_AOI01_DEL_PRODUCT_v2.zip")
    tmp.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(interno)) as z:
        for n in z.namelist():
            if "areaOfInterestA_v2" in n or "observedEventA_v2" in n:
                (tmp / Path(n).name).write_bytes(z.read(n))
    aoi = gpd.read_file(tmp / "EMSR715_AOI01_DEL_PRODUCT_areaOfInterestA_v2.shp").to_crs(CRS)
    ev = gpd.read_file(tmp / "EMSR715_AOI01_DEL_PRODUCT_observedEventA_v2.shp").to_crs(CRS)
    return aoi, ev


def celdas_geo(celdas: pd.Series) -> gpd.GeoSeries:
    polis = [shapely.Polygon([(lng, lat) for lat, lng in h3.cell_to_boundary(c)]) for c in celdas]
    return gpd.GeoSeries(polis, crs="EPSG:4326").to_crs(CRS)


def guardar_png(fig: Figure, ruta: Path) -> None:
    buf = io.BytesIO()
    fig.savefig(buf, dpi=150, format="png", facecolor="white")
    plt.close(fig)
    img = Image.open(io.BytesIO(buf.getvalue())).convert("RGB").quantize(colors=96, method=Image.Quantize.MEDIANCUT)
    img.save(ruta, optimize=True)


def pie(fig: Figure) -> None:
    fig.text(0.01, 0.01, LINEA_FUENTE, fontsize=6.5, color="#444444", ha="left", va="bottom", wrap=True)


def contorno(ax: Axes, geoms: gpd.GeoSeries, color: str, lw: float, etiqueta: str) -> None:
    geoms.boundary.plot(ax=ax, color=color, linewidth=lw, label=etiqueta)


def barra_escala(ax: Axes, x0: float, y0: float) -> None:
    ax.plot([x0, x0 + 2000], [y0, y0], color="black", linewidth=2)
    ax.text(x0 + 1000, y0 + 250, "2 km", ha="center", fontsize=7)


def main() -> int:
    if len(sys.argv) != 4:
        print(__doc__)
        return 2
    caso, emsn188_zip, emsr715_zip = map(Path, sys.argv[1:])
    t04, t05, t06 = (caso / "derivados" / t for t in ("t04", "t05", "t06"))
    nuevo = caso / "sitio.nuevo"
    final = caso / "sitio"
    if nuevo.exists():
        shutil.rmtree(nuevo)
    nuevo.mkdir(parents=True)
    print(f"== inicio {dt.datetime.now().isoformat(timespec='seconds')}")
    if sha256(t06 / "metricas.json") != METRICAS_SHA256:
        print("FALLO huella de metricas.json")
        return 1
    met = json.loads((t06 / "metricas.json").read_text(encoding="utf-8"))
    r04 = json.loads((t04 / "resumen_t04.json").read_text(encoding="utf-8"))
    umbral = met["conjuntos"]["principal"]["umbrales_ajuste"]["z_comb"]

    base = "/vsizip/" + str(emsn188_zip).replace("\\", "/") + "/" + GDB
    aoi188 = pyogrio.read_dataframe(base, layer="P00_aoi").to_crs(CRS)
    aoi715, ev715 = emsr715(emsr715_zip, caso / "derivados" / "_tmp_emsr715")

    # 1. Tablas por celda, con conteos sobre las edificaciones con dano segun EMSN188
    h = pd.read_parquet(t04 / "huellas_principal.parquet", columns=["id_huella", "rol", "h3_r9", "h3_r10"])
    s = pd.read_parquet(t05 / "senales_huellas.parquet", columns=["id_huella", "z_comb", "optico_A"])
    hp = h[h["rol"] == "positivo"].merge(s, on="id_huella")
    hp = hp[np.isfinite(hp["z_comb"]) & np.isfinite(hp["optico_A"])]
    hp["s1"] = hp["z_comb"] >= umbral
    hp["s2"] = hp["optico_A"] > 0.5
    hp["union"] = hp["s1"] | hp["s2"]
    archivos: dict[str, dict[str, Any]] = {}
    for res in (10, 9):
        c = pd.read_parquet(t06 / f"celdas_r{res}.parquet")
        dd = (
            hp.groupby(f"h3_r{res}")
            .agg(
                n_emsn188_con_ambos_datos=("id_huella", "size"),
                n_emsn188_det_s2=("s2", "sum"),
                n_emsn188_det_s1=("s1", "sum"),
                n_emsn188_det_union=("union", "sum"),
            )
            .reset_index()
        )
        c = c.merge(dd.rename(columns={f"h3_r{res}": "celda"}), on="celda", how="left")
        for col in ("n_emsn188_con_ambos_datos", "n_emsn188_det_s2", "n_emsn188_det_s1", "n_emsn188_det_union"):
            c[col] = c[col].fillna(0).astype(int)
        c.to_parquet(nuevo / f"celdas_r{res}.parquet", index=False)
        archivos[f"celdas_r{res}.parquet"] = {"filas": len(c), "licencia": LICENCIA}

    filas = []
    for conjunto, v in met["conjuntos"].items():
        for k, x in v["metricas_prueba"].items():
            filas.append(
                {
                    "conjunto": conjunto,
                    "metrica": k,
                    "valor": x["valor"],
                    "ic95_inf": x["ic95"][0],
                    "ic95_sup": x["ic95"][1],
                }
            )
    val = pd.DataFrame(filas)
    val.to_parquet(nuevo / "validacion.parquet", index=False)
    archivos["validacion.parquet"] = {"filas": len(val), "licencia": LICENCIA}

    # 2. Cruce de P5 con EMSR715 (verificacion independiente)
    p5 = pd.read_parquet(t06 / "p5_celdas_r10.parquet")
    g = celdas_geo(p5["celda"])
    quemado = ev715.geometry.union_all()
    zona715 = aoi715.geometry.union_all()
    p5["en_area_emsr715"] = g.intersects(zona715).to_numpy()
    p5["toca_quemado_emsr715"] = g.intersects(quemado).to_numpy()
    p5["a_menos_de_500m_quemado"] = g.distance(quemado).to_numpy() <= 500
    sobre = p5[p5["sobre_umbral"]]
    resto = p5[~p5["sobre_umbral"] & p5["en_area_emsr715"]]
    cruce = {
        "celdas_sobre_umbral": len(sobre),
        "sobre_umbral_que_tocan_area_quemada_emsr715": int(sobre["toca_quemado_emsr715"].sum()),
        "sobre_umbral_a_menos_de_500m_del_area_quemada": int(sobre["a_menos_de_500m_quemado"].sum()),
        "fraccion_que_toca_quemado_entre_las_demas_celdas_del_area_emsr715": float(resto["toca_quemado_emsr715"].mean())
        if len(resto)
        else None,
    }
    print(f"cruce P5 con EMSR715: {cruce}")

    # 3. Figuras
    with rasterio.open(t05 / "z_asc.tif") as ra, rasterio.open(t05 / "z_des.tif") as rd:
        za, zd = ra.read(1), rd.read(1)
        b = ra.bounds
    with np.errstate(invalid="ignore"):
        zc = np.nanmean(np.stack([za, zd]), axis=0)
    ext = (b.left, b.right, b.bottom, b.top)

    fig, ax = plt.subplots(figsize=(8, 7.4))
    im = ax.imshow(np.clip(zc, 0, 5), extent=ext, cmap="YlOrRd", vmin=0, vmax=5, interpolation="nearest")
    contorno(ax, aoi188.geometry, "#1f4e79", 1.0, "Área analizada por EMSN188")
    contorno(ax, ev715.geometry, "#555555", 0.4, "Área quemada EMSR715")
    cb = fig.colorbar(im, ax=ax, shrink=0.7)
    cb.set_label("Pérdida de coherencia (z), recortada a 0-5")
    ax.set_xlim(b.left, b.right)
    ax.set_ylim(b.bottom, b.top)
    ax.set_axis_off()
    barra_escala(ax, b.left + 1500, b.bottom + 1500)
    ax.legend(loc="upper right", fontsize=7, frameon=True)
    pie(fig)
    guardar_png(fig, nuevo / "fig_coherencia_z.png")

    c10 = pd.read_parquet(nuevo / "celdas_r10.parquet")
    c10 = c10[c10["n_emsn188_con_ambos_datos"] > 0].copy()
    g10 = celdas_geo(c10["celda"])
    fig, axes = plt.subplots(1, 2, figsize=(11, 6))
    for ax, col, titulo in (
        (axes[0], "n_emsn188_det_s2", "Sentinel-2 (óptico)"),
        (axes[1], "n_emsn188_det_union", "Sentinel-2 o Sentinel-1 (radar)"),
    ):
        frac = np.clip(c10[col] / c10["n_emsn188_con_ambos_datos"], 0, 1).to_numpy()
        parches = [MplPolygon(np.asarray(p.exterior.coords)) for p in g10]
        pc = PatchCollection(parches, cmap="YlOrRd", edgecolor="none")
        pc.set_array(frac)
        pc.set_clim(0, 1)
        ax.add_collection(pc)
        contorno(ax, aoi188.geometry, "#1f4e79", 0.8, "Área analizada por EMSN188")
        ax.set_xlim(*aoi188.total_bounds[[0, 2]])
        ax.set_ylim(*aoi188.total_bounds[[1, 3]])
        ax.set_aspect("equal")
        ax.set_axis_off()
        ax.set_title(titulo, fontsize=10)
    cb = fig.colorbar(pc, ax=axes, shrink=0.6)
    cb.set_label("Fracción detectada")
    fig.suptitle(
        "Edificaciones con daño según EMSN188 detectadas por cada sensor (celdas H3 res. 10)\n"
        "Mapa con todas las edificaciones dañadas; las cifras publicadas son de la partición de prueba",
        fontsize=10,
    )
    pie(fig)
    guardar_png(fig, nuevo / "fig_optico_vs_union.png")

    mp = met["conjuntos"]["principal"]["metricas_prueba"]
    barras = [
        ("Sentinel-2", "p2.A.sensibilidad_s2"),
        ("Sentinel-1", "p2.A.sensibilidad_s1"),
        ("Unión", "p2.A.sensibilidad_union"),
        ("Destroyed\n(Sentinel-1)", "z_comb.sensibilidad.Destroyed"),
        ("Damaged\n(Sentinel-1)", "z_comb.sensibilidad.Damaged"),
        ("Possible damage\n(Sentinel-1)", "z_comb.sensibilidad.Possible damage"),
    ]
    fig, ax = plt.subplots(figsize=(8.6, 4.8))
    vals = np.array([mp[k]["valor"] for _, k in barras])
    lo = vals - np.array([mp[k]["ic95"][0] for _, k in barras])
    hi = np.array([mp[k]["ic95"][1] for _, k in barras]) - vals
    colores = ["#9ecae1", "#fc8d59", "#d7301f", "#fdbb84", "#fdbb84", "#fdbb84"]
    ax.bar(range(len(barras)), vals, yerr=[lo, hi], color=colores, capsize=4)
    ax.set_xticks(range(len(barras)))
    ax.set_xticklabels([n for n, _ in barras], fontsize=8)
    ax.set_ylim(0, 1)
    ax.set_ylabel("Sensibilidad en prueba (IC 95 % por bloques)")
    for i, v in enumerate(vals):
        ax.text(i, v + hi[i] + 0.02, f"{v:.0%}", ha="center", fontsize=8, color="black")
    ax.spines[["top", "right"]].set_visible(False)
    fig.subplots_adjust(bottom=0.2)
    pie(fig)
    guardar_png(fig, nuevo / "fig_sensibilidad.png")

    fig, ax = plt.subplots(figsize=(8, 7.4))
    gs = celdas_geo(sobre["celda"])
    ev715.plot(ax=ax, color="#fdd0a2", linewidth=0, label="Área quemada EMSR715")
    contorno(ax, aoi188.geometry, "#1f4e79", 1.0, "Área analizada por EMSN188")
    gs.plot(ax=ax, color="#b30000", edgecolor="#b30000", linewidth=0.6)
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch

    ax.legend(
        handles=[
            Patch(color="#fdd0a2", label="Área quemada EMSR715"),
            Line2D([0], [0], color="#1f4e79", label="Área analizada por EMSN188"),
            Patch(color="#b30000", label="Celda con señal sobre el umbral"),
        ],
        loc="upper right",
        fontsize=7,
        frameon=True,
    )
    ax.set_xlim(b.left, b.right)
    ax.set_ylim(b.bottom, b.top)
    ax.set_aspect("equal")
    ax.set_axis_off()
    barra_escala(ax, b.left + 1500, b.bottom + 1500)
    ax.set_title("Celdas H3 res. 10 fuera de EMSN188 con señal sobre el umbral (estimación de modelo)", fontsize=9)
    pie(fig)
    guardar_png(fig, nuevo / "fig_p5_fuera_emsn188.png")

    alt = {
        "fig_coherencia_z.png": "Mapa de la pérdida de coherencia del radar Sentinel-1 entre antes y después del "
        "incendio en Viña del Mar y alrededores, con el contorno del área analizada por "
        "Copernicus EMSN188 y el área quemada de EMSR715.",
        "fig_optico_vs_union.png": "Dos mapas de celdas hexagonales comparan qué fracción de las edificaciones con "
        "daño según EMSN188 detecta Sentinel-2 solo y Sentinel-2 junto con Sentinel-1.",
        "fig_sensibilidad.png": "Gráfico de barras con intervalos que compara la fracción de edificaciones dañadas "
        "detectada por Sentinel-2, Sentinel-1 y ambos, y por Sentinel-1 según el grado de daño.",
        "fig_p5_fuera_emsn188.png": "Mapa de las pocas celdas fuera del área de EMSN188 donde la señal del radar "
        "supera el umbral, dispersas y lejos del área quemada de EMSR715.",
    }
    for f in sorted(nuevo.glob("fig_*.png")):
        with Image.open(f) as im_:
            archivos[f.name] = {
                "ancho": im_.width,
                "alto": im_.height,
                "licencia": LICENCIA,
                "alt": alt[f.name],
                "cita": LINEA_FUENTE,
            }

    # 4. resumen.json (va ultimo)
    cifras = {}
    for ident, (conjunto, clave, definicion) in CIFRAS.items():
        x = met["conjuntos"][conjunto]["metricas_prueba"][clave]
        cifras[ident] = {
            "valor": x["valor"],
            "ic95": x["ic95"],
            "definicion": definicion,
            "particion": "prueba",
            "conjunto_huellas": conjunto,
            "fuente": f"derivados/t06/metricas.json#{conjunto}.metricas_prueba.{clave}",
        }
    cifras["umbral_z"] = {
        "valor": umbral,
        "definicion": "Percentil 90 de la senal combinada en los negativos de ajuste",
        "particion": "ajuste",
        "fuente": "derivados/t06/metricas.json#principal.umbrales_ajuste.z_comb",
    }
    pr04 = r04["conjuntos"]["principal"]
    cifras["puntos_emsn188"] = {
        "valor": r04["puntos_p08"],
        "definicion": "Puntos de dano de EMSN188 P08",
        "fuente": "derivados/t04/resumen_t04.json#puntos_p08",
    }
    cifras["fraccion_puntos_sin_huella"] = {
        "valor": pr04["fraccion_puntos_sin_huella"],
        "definicion": "Puntos de EMSN188 sin huella de Google a 10 m o menos",
        "fuente": "derivados/t04/resumen_t04.json#principal.fraccion_puntos_sin_huella",
    }
    for k, v in met["conjuntos"]["principal"]["p5_r10"].items():
        if k != "rotulo":
            cifras[f"p5_r10_{k}"] = {
                "valor": v,
                "definicion": f"P5, {k} (estimacion de modelo)",
                "fuente": f"derivados/t06/metricas.json#principal.p5_r10.{k}",
            }
    for k, v in cruce.items():
        cifras[f"verificacion_p5_{k}"] = {
            "valor": v,
            "definicion": "Cruce de P5 con EMSR715 AOI01 v2",
            "fuente": "tarea 07",
        }
    for f in sorted(nuevo.iterdir()):
        archivos.setdefault(f.name, {})["sha256"] = sha256(f)
        archivos[f.name]["bytes"] = f.stat().st_size
    resumen = {
        "caso": "Daño a edificaciones en el incendio de Viña del Mar, febrero de 2024",
        "protocolo_sha256": "de1993790a4e7485aeef3d64749a490dd735679feb5575263bc61ca727387f5d",
        "enmiendas_sha256": [
            "8ff741dde5bb5b2bbf391fe7652e5088640c2c02b0ac4c28818d0419a122bc1e",
            "82f1000d908f662e9e24596232a0832b493aa767d117af95012dd724d4341b27",
        ],
        "metricas_sha256": METRICAS_SHA256,
        "licencia": LICENCIA,
        "avisos": AVISOS,
        "lectura": "Dano probable segun radar; no es un dictamen sobre cada vivienda. Copernicus EMS, SENAPRED "
        "y MINVU no validaron estos resultados.",
        "cifras": cifras,
        "archivos": archivos,
    }
    (nuevo / "resumen.json").write_text(
        json.dumps(resumen, ensure_ascii=False, indent=2, default=float), encoding="utf-8"
    )

    # 5. Verificacion
    errores = []
    leido = json.loads((nuevo / "resumen.json").read_text(encoding="utf-8"))
    presentes = {f.name for f in nuevo.iterdir()} - {"resumen.json"}
    if presentes != set(leido["archivos"]):
        errores.append(f"archivos sin registro o faltantes: {presentes ^ set(leido['archivos'])}")
    for n, info in leido["archivos"].items():
        if sha256(nuevo / n) != info["sha256"]:
            errores.append(f"huella distinta {n}")
        if n.endswith(".png") and info["bytes"] > PESO_MAX_FIG:
            errores.append(f"figura pesada {n} {info['bytes']}")
    for ident, (conjunto, clave, _) in CIFRAS.items():
        if leido["cifras"][ident]["valor"] != met["conjuntos"][conjunto]["metricas_prueba"][clave]["valor"]:
            errores.append(f"cifra distinta {ident}")
    total = sum(f.stat().st_size for f in nuevo.iterdir())
    if total > PESO_MAX_TOTAL:
        errores.append(f"peso total {total}")
    shutil.rmtree(caso / "derivados" / "_tmp_emsr715", ignore_errors=True)
    if errores:
        for e in errores:
            print(f"FALLO {e}")
        return 1
    if final.exists():
        shutil.rmtree(final)
    nuevo.rename(final)
    print(f"sitio verificado: {len(presentes) + 1} archivos, {total} bytes")
    for f in sorted(final.iterdir()):
        print(f"huella {f.name} {sha256(f)}")
    print("FIN OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
