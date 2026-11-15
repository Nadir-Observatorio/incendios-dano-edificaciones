"""Tarea 07 del caso de dano a edificaciones: contrato de datos para el sitio.

Escribe todo en `<carpeta_trabajo>/sitio.nuevo/`, verifica (huellas, cifras contra metricas.json, tamano
de figuras, archivos sin registro) y solo entonces reemplaza `<carpeta_trabajo>/sitio/`. Ninguna cifra se
escribe a mano: todas se leen de metricas.json (tarea 06) o de los resumenes de las tareas 04 y 05. Los
textos (avisos, rotulos, alt, definiciones) salen de la tabla `[sitio]` de caso.toml. Incluye el cruce de
P5 con la delineacion oficial del caso.

Uso:
  python t07_sitio.py <carpeta_caso> <carpeta_trabajo>
"""

from __future__ import annotations

import datetime as dt
import io
import json
import shutil
import sys
from pathlib import Path
from typing import Any

import geopandas as gpd
import h3
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
import shapely
from matplotlib.axes import Axes
from matplotlib.collections import PatchCollection
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.patches import Polygon as MplPolygon
from PIL import Image

import caso as caso_mod
import referencia
from caso import Caso, sha256

PESO_MAX_FIG = 450 * 1024
PESO_MAX_TOTAL = 25 * 1024 * 1024


def celdas_geo(celdas: pd.Series, crs: str) -> gpd.GeoSeries:
    polis = [shapely.Polygon([(lng, lat) for lat, lng in h3.cell_to_boundary(c)]) for c in celdas]
    return gpd.GeoSeries(polis, crs="EPSG:4326").to_crs(crs)


def guardar_png(fig: Figure, ruta: Path) -> None:
    buf = io.BytesIO()
    fig.savefig(buf, dpi=150, format="png", facecolor="white")
    plt.close(fig)
    img = Image.open(io.BytesIO(buf.getvalue())).convert("RGB").quantize(colors=96, method=Image.Quantize.MEDIANCUT)
    img.save(ruta, optimize=True)


def pie(fig: Figure, linea: str) -> None:
    fig.text(0.01, 0.01, linea, fontsize=6.5, color="#444444", ha="left", va="bottom", wrap=True)


def contorno(ax: Axes, geoms: gpd.GeoSeries, color: str, lw: float, etiqueta: str) -> None:
    geoms.boundary.plot(ax=ax, color=color, linewidth=lw, label=etiqueta)


def barra_escala(ax: Axes, x0: float, y0: float) -> None:
    ax.plot([x0, x0 + 2000], [y0, y0], color="black", linewidth=2)
    ax.text(x0 + 1000, y0 + 250, "2 km", ha="center", fontsize=7)


def z_grupo(caso: Caso, t05: Path, grupo: str) -> tuple[np.ndarray, Any]:
    """Raster de `z` del grupo: el de su unica orbita o la media de sus orbitas por pixel."""
    ids = caso.grupos[grupo]
    capas = []
    limites = None
    for o in ids:
        with rasterio.open(t05 / f"z_{o}.tif") as r:
            capas.append(r.read(1))
            limites = r.bounds
    if len(capas) == 1:
        return capas[0], limites
    with np.errstate(invalid="ignore"):
        return np.nanmean(np.stack(capas), axis=0), limites


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    carpeta_caso, trabajo = map(Path, sys.argv[1:])
    caso = caso_mod.cargar(carpeta_caso)
    sitio = caso.sitio
    crs = caso.crs
    licencia = str(sitio["licencia"])
    linea_fuente = str(sitio["linea_fuente"])
    rot = sitio["rotulos"]
    etiqueta = str(caso.referencia["etiqueta"])
    ctl = str(caso.referencia["etiqueta_control"])
    t04, t05, t06 = (trabajo / "derivados" / t for t in ("t04", "t05", "t06"))
    nuevo = trabajo / "sitio.nuevo"
    final = trabajo / "sitio"
    if nuevo.exists():
        shutil.rmtree(nuevo)
    nuevo.mkdir(parents=True)
    print(f"== inicio {dt.datetime.now().isoformat(timespec='seconds')} caso {caso.nombre}")
    metricas_sha256 = caso.fijada("metricas_sha256")
    if sha256(t06 / "metricas.json") != metricas_sha256:
        print("FALLO huella de metricas.json")
        return 1
    met = json.loads((t06 / "metricas.json").read_text(encoding="utf-8"))
    r04 = json.loads((t04 / "resumen_t04.json").read_text(encoding="utf-8"))
    umbral = met["conjuntos"]["principal"]["umbrales_ajuste"]["z_comb"]

    tmp = trabajo / "derivados" / "_tmp_control"
    ref = referencia.leer(caso, tmp)
    zona_ref = ref.zona
    quemado_ref = ref.quemado

    # 1. Tablas por celda, con conteos sobre las edificaciones con dano segun la referencia
    h = pd.read_parquet(t04 / "huellas_principal.parquet", columns=["id_huella", "rol", "h3_r9", "h3_r10"])
    s = pd.read_parquet(t05 / "senales_huellas.parquet", columns=["id_huella", "z_comb", "optico_A"])
    hp = h[h["rol"] == "positivo"].merge(s, on="id_huella")
    hp = hp[np.isfinite(hp["z_comb"]) & np.isfinite(hp["optico_A"])]
    hp["s1"] = hp["z_comb"] >= umbral
    hp["s2"] = hp["optico_A"] > 0.5
    hp["union"] = hp["s1"] | hp["s2"]
    col_ambos = f"n_{etiqueta}_con_ambos_datos"
    col_s2, col_s1, col_union = f"n_{etiqueta}_det_s2", f"n_{etiqueta}_det_s1", f"n_{etiqueta}_det_union"
    archivos: dict[str, dict[str, Any]] = {}
    for res in (10, 9):
        c = pd.read_parquet(t06 / f"celdas_r{res}.parquet")
        agregados: dict[str, Any] = {
            col_ambos: ("id_huella", "size"),
            col_s2: ("s2", "sum"),
            col_s1: ("s1", "sum"),
            col_union: ("union", "sum"),
        }
        dd = hp.groupby(f"h3_r{res}").agg(**agregados).reset_index()
        c = c.merge(dd.rename(columns={f"h3_r{res}": "celda"}), on="celda", how="left")
        for col in (col_ambos, col_s2, col_s1, col_union):
            c[col] = c[col].fillna(0).astype(int)
        c.to_parquet(nuevo / f"celdas_r{res}.parquet", index=False)
        archivos[f"celdas_r{res}.parquet"] = {"filas": len(c), "licencia": licencia}

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
    archivos["validacion.parquet"] = {"filas": len(val), "licencia": licencia}

    # 2. Cruce de P5 con la delineacion oficial (verificacion independiente)
    p5 = pd.read_parquet(t06 / "p5_celdas_r10.parquet")
    g = celdas_geo(p5["celda"], crs)
    quemado = quemado_ref.geometry.union_all()
    zona_ctl = ref.area_control.geometry.union_all()
    p5[f"en_area_{ctl}"] = g.intersects(zona_ctl).to_numpy()
    p5[f"toca_quemado_{ctl}"] = g.intersects(quemado).to_numpy()
    p5["a_menos_de_500m_quemado"] = g.distance(quemado).to_numpy() <= 500
    sobre = p5[p5["sobre_umbral"]]
    resto = p5[~p5["sobre_umbral"] & p5[f"en_area_{ctl}"]]
    cruce = {
        "celdas_sobre_umbral": len(sobre),
        f"sobre_umbral_que_tocan_area_quemada_{ctl}": int(sobre[f"toca_quemado_{ctl}"].sum()),
        "sobre_umbral_a_menos_de_500m_del_area_quemada": int(sobre["a_menos_de_500m_quemado"].sum()),
        f"fraccion_que_toca_quemado_entre_las_demas_celdas_del_area_{ctl}": float(resto[f"toca_quemado_{ctl}"].mean())
        if len(resto)
        else None,
    }
    print(f"cruce P5 con {ctl}: {cruce}")

    # 3. Figuras
    za, b = z_grupo(caso, t05, "asc")
    zd, _ = z_grupo(caso, t05, "des")
    with np.errstate(invalid="ignore"):
        zc = np.nanmean(np.stack([za, zd]), axis=0)
    ext = (b.left, b.right, b.bottom, b.top)
    nombres = sitio["figuras"]

    fig, ax = plt.subplots(figsize=(8, 7.4))
    im = ax.imshow(np.clip(zc, 0, 5), extent=ext, cmap="YlOrRd", vmin=0, vmax=5, interpolation="nearest")
    contorno(ax, zona_ref.geometry, "#1f4e79", 1.0, str(rot["zona"]))
    contorno(ax, quemado_ref.geometry, "#555555", 0.4, str(rot["quemado"]))
    cb = fig.colorbar(im, ax=ax, shrink=0.7)
    cb.set_label(str(rot["barra_z"]))
    ax.set_xlim(b.left, b.right)
    ax.set_ylim(b.bottom, b.top)
    ax.set_axis_off()
    barra_escala(ax, b.left + 1500, b.bottom + 1500)
    ax.legend(loc="upper right", fontsize=7, frameon=True)
    pie(fig, linea_fuente)
    guardar_png(fig, nuevo / str(nombres["coherencia"]))

    c10 = pd.read_parquet(nuevo / "celdas_r10.parquet")
    c10 = c10[c10[col_ambos] > 0].copy()
    g10 = celdas_geo(c10["celda"], crs)
    fig, axes = plt.subplots(1, 2, figsize=(11, 6))
    paneles = [str(x) for x in rot["paneles"]]
    for ax, col, titulo in ((axes[0], col_s2, paneles[0]), (axes[1], col_union, paneles[1])):
        frac = np.clip(c10[col] / c10[col_ambos], 0, 1).to_numpy()
        parches = [MplPolygon(np.asarray(p.exterior.coords)) for p in g10]
        pc = PatchCollection(parches, cmap="YlOrRd", edgecolor="none")
        pc.set_array(frac)
        pc.set_clim(0, 1)
        ax.add_collection(pc)
        contorno(ax, zona_ref.geometry, "#1f4e79", 0.8, str(rot["zona"]))
        ax.set_xlim(*zona_ref.total_bounds[[0, 2]])
        ax.set_ylim(*zona_ref.total_bounds[[1, 3]])
        ax.set_aspect("equal")
        ax.set_axis_off()
        ax.set_title(titulo, fontsize=10)
    cb = fig.colorbar(pc, ax=axes, shrink=0.6)
    cb.set_label(str(rot["barra_fraccion"]))
    fig.suptitle(str(rot["titulo_optico_vs_union"]), fontsize=10)
    pie(fig, linea_fuente)
    guardar_png(fig, nuevo / str(nombres["optico_vs_union"]))

    mp = met["conjuntos"]["principal"]["metricas_prueba"]
    barras = [(str(n), str(k)) for n, k in sitio["barras"]]
    fig, ax = plt.subplots(figsize=(8.6, 4.8))
    vals = np.array([mp[k]["valor"] for _, k in barras])
    lo = vals - np.array([mp[k]["ic95"][0] for _, k in barras])
    hi = np.array([mp[k]["ic95"][1] for _, k in barras]) - vals
    colores = ["#9ecae1", "#fc8d59", "#d7301f", "#fdbb84", "#fdbb84", "#fdbb84"]
    ax.bar(range(len(barras)), vals, yerr=[lo, hi], color=colores[: len(barras)], capsize=4)
    ax.set_xticks(range(len(barras)))
    ax.set_xticklabels([n for n, _ in barras], fontsize=8)
    ax.set_ylim(0, 1)
    ax.set_ylabel(str(rot["eje_sensibilidad"]))
    for i, v in enumerate(vals):
        ax.text(i, v + hi[i] + 0.02, f"{v:.0%}", ha="center", fontsize=8, color="black")
    ax.spines[["top", "right"]].set_visible(False)
    fig.subplots_adjust(bottom=0.2)
    pie(fig, linea_fuente)
    guardar_png(fig, nuevo / str(nombres["sensibilidad"]))

    fig, ax = plt.subplots(figsize=(8, 7.4))
    gs = celdas_geo(sobre["celda"], crs)
    quemado_ref.plot(ax=ax, color="#fdd0a2", linewidth=0, label=str(rot["quemado"]))
    contorno(ax, zona_ref.geometry, "#1f4e79", 1.0, str(rot["zona"]))
    gs.plot(ax=ax, color="#b30000", edgecolor="#b30000", linewidth=0.6)
    ax.legend(
        handles=[
            Patch(color="#fdd0a2", label=str(rot["quemado"])),
            Line2D([0], [0], color="#1f4e79", label=str(rot["zona"])),
            Patch(color="#b30000", label=str(rot["celda_sobre_umbral"])),
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
    ax.set_title(str(rot["titulo_p5"]), fontsize=9)
    pie(fig, linea_fuente)
    guardar_png(fig, nuevo / str(nombres["p5"]))

    alt = {str(nombres[k]): str(v) for k, v in sitio["alt"].items()}
    for f in sorted(nuevo.glob("fig_*.png")):
        with Image.open(f) as im_:
            archivos[f.name] = {
                "ancho": im_.width,
                "alto": im_.height,
                "licencia": licencia,
                "alt": alt[f.name],
                "cita": linea_fuente,
            }

    # 4. resumen.json (va ultimo)
    definiciones = sitio["definiciones"]
    cifras_sitio: dict[str, tuple[str, str, str]] = {
        str(k): (str(v[0]), str(v[1]), str(v[2])) for k, v in sitio["cifras"].items()
    }
    cifras: dict[str, Any] = {}
    for ident, (conjunto, clave, definicion) in cifras_sitio.items():
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
        "definicion": str(definiciones["umbral_z"]),
        "particion": "ajuste",
        "fuente": "derivados/t06/metricas.json#principal.umbrales_ajuste.z_comb",
    }
    pr04 = r04["conjuntos"]["principal"]
    clave_puntos = str(caso.referencia["clave_puntos"])
    cifras[f"puntos_{etiqueta}"] = {
        "valor": r04[clave_puntos],
        "definicion": str(definiciones["puntos"]),
        "fuente": f"derivados/t04/resumen_t04.json#{clave_puntos}",
    }
    cifras["fraccion_puntos_sin_huella"] = {
        "valor": pr04["fraccion_puntos_sin_huella"],
        "definicion": str(definiciones["fraccion_puntos_sin_huella"]),
        "fuente": "derivados/t04/resumen_t04.json#principal.fraccion_puntos_sin_huella",
    }
    for k, v in met["conjuntos"]["principal"]["p5_r10"].items():
        if k != "rotulo":
            cifras[f"p5_r10_{k}"] = {
                "valor": v,
                "definicion": str(definiciones["p5"]).format(k=k),
                "fuente": f"derivados/t06/metricas.json#principal.p5_r10.{k}",
            }
    for k, v in cruce.items():
        cifras[f"verificacion_p5_{k}"] = {
            "valor": v,
            "definicion": str(definiciones["verificacion_p5"]),
            "fuente": "tarea 07",
        }
    for f in sorted(nuevo.iterdir()):
        archivos.setdefault(f.name, {})["sha256"] = sha256(f)
        archivos[f.name]["bytes"] = f.stat().st_size
    resumen = {
        "caso": str(sitio["caso"]),
        "protocolo_sha256": caso.documentos[0].sha256,
        "enmiendas_sha256": [d.sha256 for d in caso.documentos[1:]],
        "metricas_sha256": metricas_sha256,
        "licencia": licencia,
        "avisos": [str(a) for a in sitio["avisos"]],
        "lectura": str(sitio["lectura"]),
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
    for ident, (conjunto, clave, _) in cifras_sitio.items():
        if leido["cifras"][ident]["valor"] != met["conjuntos"][conjunto]["metricas_prueba"][clave]["valor"]:
            errores.append(f"cifra distinta {ident}")
    total = sum(f.stat().st_size for f in nuevo.iterdir())
    if total > PESO_MAX_TOTAL:
        errores.append(f"peso total {total}")
    referencia.limpiar(tmp)
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
