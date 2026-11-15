"""Tarea 05 del caso de dano a edificaciones: senales por pixel y por huella.

Coherencia previa, `z` del evento y `z` posterior por orbita, mascara de inversion y sombra, pendiente, y
deteccion optica. Las orbitas de un mismo grupo (ascendente o descendente) se promedian por huella; la
`z` combinada es la media de los dos grupos. Con una orbita por grupo, como en Vina, es la media de la
ascendente y la descendente. No fija umbrales ni calcula metricas; eso es la tarea 06, que evalua la
particion de prueba una sola vez.

Uso:
  python t05_senales.py <carpeta_caso> <carpeta_trabajo>

Lee `<carpeta_trabajo>/derivados/t04/` y escribe en `<carpeta_trabajo>/derivados/t05/`.
"""

from __future__ import annotations

import datetime as dt
import json
import sys
import tomllib
import warnings
import zipfile
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
import shapely
from rasterio.transform import from_origin
from rasterio.warp import Resampling, reproject, transform_bounds

import caso as caso_mod
from caso import sha256

# Valores del caso de origen (Vina 2024). Solo los usan las pruebas; las tareas leen caso.toml.
CAJA = (-71.60, -33.13, -71.38, -32.94)
CRS = "EPSG:32719"

RES = 20.0
PREVIOS = [f"previo{i}" for i in range(1, 7)]
MIN_PREVIOS = 4
S_MIN = 0.05
AMPLIACION_M = 10.0
FRACCION_VALIDA_MIN = 0.5
AZIMUT_ESPERADO = {"asc": 180.0, "des": 0.0}


def grilla(caja: tuple[float, float, float, float] = CAJA, crs: str = CRS) -> tuple[rasterio.Affine, tuple[int, int]]:
    x0, y0, x1, y1 = transform_bounds("EPSG:4326", crs, *caja)
    x0 = np.floor(x0 / RES) * RES
    y1 = np.ceil(y1 / RES) * RES
    ancho = int(np.ceil((x1 - x0) / RES))
    alto = int(np.ceil((y1 - y0) / RES))
    return from_origin(x0, y1, RES, RES), (alto, ancho)


def capa(zip_ruta: Path, sufijo: str, transform: rasterio.Affine, forma: tuple[int, int], crs: str = CRS) -> np.ndarray:
    with zipfile.ZipFile(zip_ruta) as z:
        nombre = next(n for n in z.namelist() if n.endswith(f"_{sufijo}.tif"))
    destino = np.full(forma, np.nan, dtype="float32")
    with rasterio.open(f"/vsizip/{zip_ruta.as_posix()}/{nombre}") as r:
        reproject(
            source=rasterio.band(r, 1),
            destination=destino,
            src_nodata=0.0,
            dst_nodata=np.nan,
            dst_transform=transform,
            dst_crs=crs,
            resampling=Resampling.bilinear,
        )
    return destino


def mosaico(capas: list[np.ndarray]) -> np.ndarray:
    pila = np.stack(capas)
    with np.errstate(invalid="ignore"):
        cuenta = np.sum(np.isfinite(pila), axis=0)
        suma = np.nansum(pila, axis=0)
    salida = np.where(cuenta > 0, suma / np.maximum(cuenta, 1), np.nan)
    return salida.astype("float32")


def angulo_dif(a: np.ndarray | float, b: float) -> np.ndarray | float:
    return np.abs((np.asarray(a) - b + 180.0) % 360.0 - 180.0)


def mascara_geometria(
    theta: np.ndarray,
    phi: np.ndarray,
    dem: np.ndarray,
    geometria: str,
    registro: list[str],
    etiqueta: str | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Mascara de inversion y sombra. `geometria` es la direccion ('asc' o 'des'); `etiqueta`, la orbita."""
    nombre = etiqueta if etiqueta is not None else geometria
    t = theta[np.isfinite(theta)]
    p = phi[np.isfinite(phi)]
    med_t = float(np.median(t))
    med_p = float(np.median(p))
    unidad_rad = med_t < 2.0
    if unidad_rad:
        theta = np.degrees(theta)
        phi = np.degrees(phi)
        med_t, med_p = np.degrees(med_t), np.degrees(med_p)
    if med_t > 45.0:
        incid = 90.0 - theta
        conv_t = "elevacion"
    else:
        incid = theta
        conv_t = "incidencia"
    esperado = AZIMUT_ESPERADO[geometria]
    if angulo_dif(med_p, esperado) < 60.0:
        azim = phi
        conv_p = "hacia el satelite"
    elif angulo_dif(med_p + 180.0, esperado) < 60.0:
        azim = phi + 180.0
        conv_p = "opuesto, se suma 180"
    else:
        raise ValueError(f"{nombre}: mediana de lv_phi {med_p:.1f} grados no calza con lo esperado")
    registro.append(
        f"{nombre}: lv_theta mediana {med_t:.2f} grados ({'radianes' if unidad_rad else 'grados'} en origen, "
        f"{conv_t}); incidencia mediana {float(np.nanmedian(incid)):.2f}; lv_phi mediana {med_p:.1f} ({conv_p})"
    )
    dzdy_fila, dzdx = np.gradient(dem.astype("float64"), RES)
    dzdy = -dzdy_fila  # las filas crecen hacia el sur
    az = np.radians(azim)
    alfa = np.degrees(np.arctan(dzdx * np.cos(az) + dzdy * np.sin(az)))
    theta_loc = incid - alfa
    valido = np.isfinite(theta_loc) & (theta_loc > 0.0) & (theta_loc < 90.0)
    pendiente = np.degrees(np.arctan(np.hypot(dzdx, dzdy)))
    return valido, pendiente.astype("float32")


def ponderar(
    geoms: np.ndarray,
    transform: rasterio.Affine,
    forma: tuple[int, int],
    capas: dict[str, np.ndarray],
    validos: dict[str, np.ndarray],
) -> pd.DataFrame:
    """Media ponderada por area exacta de interseccion huella-pixel, por capa con su mascara."""
    alto, ancho = forma
    x0, y1 = transform.c, transform.f
    filas_out: dict[str, np.ndarray] = {}
    n = len(geoms)
    for clave in capas:
        filas_out[clave] = np.full(n, np.nan)
        filas_out[f"frac_{clave}"] = np.zeros(n)
    area_total = shapely.area(geoms)
    bloque = 20000
    for ini in range(0, n, bloque):
        sub = geoms[ini : ini + bloque]
        b = shapely.bounds(sub)
        c0 = np.clip(np.floor((b[:, 0] - x0) / RES).astype(int), 0, ancho - 1)
        c1 = np.clip(np.floor((b[:, 2] - x0) / RES).astype(int), 0, ancho - 1)
        r0 = np.clip(np.floor((y1 - b[:, 3]) / RES).astype(int), 0, alto - 1)
        r1 = np.clip(np.floor((y1 - b[:, 1]) / RES).astype(int), 0, alto - 1)
        idx, rr, cc = [], [], []
        for k in range(len(sub)):
            r, c = np.meshgrid(np.arange(r0[k], r1[k] + 1), np.arange(c0[k], c1[k] + 1), indexing="ij")
            idx.append(np.full(r.size, k))
            rr.append(r.ravel())
            cc.append(c.ravel())
        idx_a, rr_a, cc_a = np.concatenate(idx), np.concatenate(rr), np.concatenate(cc)
        cajas = shapely.box(x0 + cc_a * RES, y1 - (rr_a + 1) * RES, x0 + (cc_a + 1) * RES, y1 - rr_a * RES)
        a = shapely.area(shapely.intersection(sub[idx_a], cajas))
        for clave, arr in capas.items():
            v = arr[rr_a, cc_a]
            ok = validos[clave][rr_a, cc_a] & np.isfinite(v) & (a > 0)
            peso = np.bincount(idx_a[ok], weights=a[ok], minlength=len(sub))
            suma = np.bincount(idx_a[ok], weights=(a * np.where(ok, v, 0.0))[ok], minlength=len(sub))
            with np.errstate(invalid="ignore", divide="ignore"):
                media = np.where(peso > 0, suma / np.where(peso > 0, peso, 1), np.nan)
            filas_out[clave][ini : ini + len(sub)] = media
            filas_out[f"frac_{clave}"][ini : ini + len(sub)] = peso / area_total[ini : ini + len(sub)]
    return pd.DataFrame(filas_out)


def combinar_por_grupo(tabla: pd.DataFrame, grupos: dict[str, list[str]]) -> pd.DataFrame:
    """Columnas por grupo y combinada a partir de las columnas por orbita ya enmascaradas.

    Un grupo con una sola orbita del mismo nombre (Vina) no agrega columnas: ya son las del grupo. Un grupo
    con varias orbitas agrega `z_<grupo>`, `zpost_<grupo>`, `cohprev_<grupo>` como media de las orbitas
    validas y `valida_<grupo>` si alguna lo es. La combinada es la media de los grupos con dato.
    """
    for grupo, ids in grupos.items():
        if ids == [grupo]:
            continue
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=RuntimeWarning)
            for pre in ("z", "zpost", "cohprev"):
                pila = np.vstack([tabla[f"{pre}_{o}"].to_numpy(dtype=float) for o in ids])
                tabla[f"{pre}_{grupo}"] = np.nanmean(pila, axis=0)
        tabla[f"valida_{grupo}"] = np.any(np.vstack([tabla[f"valida_{o}"].to_numpy() for o in ids]), axis=0)
    with np.errstate(invalid="ignore"):
        tabla["z_comb"] = np.nanmean(np.vstack([tabla["z_asc"], tabla["z_des"]]), axis=0)
        tabla["zpost_comb"] = np.nanmean(np.vstack([tabla["zpost_asc"], tabla["zpost_des"]]), axis=0)
        tabla["cohprev_comb"] = np.nanmean(np.vstack([tabla["cohprev_asc"], tabla["cohprev_des"]]), axis=0)
    return tabla


def escribir_tif(ruta: Path, arr: np.ndarray, transform: rasterio.Affine, crs: str = CRS) -> None:
    with rasterio.open(
        ruta,
        "w",
        driver="GTiff",
        height=arr.shape[0],
        width=arr.shape[1],
        count=1,
        dtype="float32",
        crs=crs,
        transform=transform,
        nodata=np.nan,
        compress="deflate",
        predictor=3,
        tiled=True,
    ) as w:
        w.write(arr.astype("float32"), 1)


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    carpeta_caso, trabajo = map(Path, sys.argv[1:])
    caso = caso_mod.cargar(carpeta_caso)
    t04 = trabajo / "derivados" / "t04"
    salida = trabajo / "derivados" / "t05"
    if (salida / "senales_huellas.parquet").exists():
        print("FALLO ya existen las senales en la carpeta de trabajo; no se sobrescriben")
        return 1
    salida.mkdir(parents=True, exist_ok=True)
    print(f"== inicio {dt.datetime.now().isoformat(timespec='seconds')} caso {caso.nombre}")
    for linea in caso_mod.verificar_documentos(caso):
        print(linea)
    h = sha256(t04 / "particion.csv")
    if h != caso.fijada("particion_sha256"):
        print(f"FALLO huella de la particion: {h}")
        return 1
    print("verificada la particion de la tarea 04")

    banco = caso.ruta("banco_hyp3")
    proc = tomllib.loads((banco / "procedencia.toml").read_text(encoding="utf-8"))
    archivos = proc["archivo"]
    print(f"productos registrados: {len(archivos)}")
    for a in archivos:
        if sha256(banco / a["nombre"]) != a["sha256"]:
            print(f"FALLO huella de {a['nombre']}")
            return 1
    print(f"huellas de los {len(archivos)} productos verificadas")
    with zipfile.ZipFile(banco / archivos[0]["nombre"]) as zf:
        readme = next(n for n in zf.namelist() if n.endswith("_README.md.txt"))
        lineas_dem = [x.strip() for x in zf.read(readme).decode("utf-8", "replace").splitlines() if "DEM" in x]
    for linea in lineas_dem[:6]:
        print(f"README (DEM): {linea}")

    crs = caso.crs
    transform, forma = grilla(caso.caja, crs)
    print(f"grilla comun {crs} {forma[1]} x {forma[0]} pixeles de {RES:.0f} m")
    registro: list[str] = []
    capas: dict[str, np.ndarray] = {}
    validos: dict[str, np.ndarray] = {}
    pendientes = []
    for orbita in caso.orbitas:
        oid = orbita.id
        propios = [a for a in archivos if a["geometria"] == oid]
        if not propios:
            print(f"FALLO no hay productos de la orbita {oid} en el banco")
            return 1
        coh: dict[str, np.ndarray] = {}
        for rol in [*PREVIOS, "evento", "posterior"]:
            zs = [banco / a["nombre"] for a in propios if a["rol"] == rol]
            coh[rol] = mosaico([capa(z, "corr", transform, forma, crs) for z in zs])
        evento = [banco / a["nombre"] for a in propios if a["rol"] == "evento"]
        theta = mosaico([capa(z, "lv_theta", transform, forma, crs) for z in evento])
        phi = mosaico([capa(z, "lv_phi", transform, forma, crs) for z in evento])
        dem = mosaico([capa(z, "dem", transform, forma, crs) for z in evento])
        geo_ok, pend = mascara_geometria(theta, phi, dem, orbita.direccion, registro, oid)
        pendientes.append(pend)
        pila = np.stack([coh[r] for r in PREVIOS])
        n_prev = np.sum(np.isfinite(pila), axis=0)
        with np.errstate(invalid="ignore"):
            m = np.nanmean(pila, axis=0)
            s = np.nanstd(pila, axis=0, ddof=1)
        s_ef = np.maximum(s, S_MIN)
        base = geo_ok & (n_prev >= MIN_PREVIOS)
        z = np.where(base & np.isfinite(coh["evento"]), (m - coh["evento"]) / s_ef, np.nan)
        zp = np.where(base & np.isfinite(coh["posterior"]), (m - coh["posterior"]) / s_ef, np.nan)
        m_ok = np.where(base, m, np.nan)
        for clave, arr in ((f"z_{oid}", z), (f"zpost_{oid}", zp), (f"cohprev_{oid}", m_ok)):
            capas[clave] = arr.astype("float32")
            validos[clave] = np.isfinite(arr)
            escribir_tif(salida / f"{clave}.tif", arr, transform, crs)
        escribir_tif(salida / f"mascara_geometria_{oid}.tif", geo_ok.astype("float32"), transform, crs)
        print(
            f"{oid}: pixeles con z valida {int(np.isfinite(z).sum())} de {z.size}; "
            f"inversion o sombra {int((~geo_ok & np.isfinite(dem)).sum())}"
        )
    for r in registro:
        print(f"convencion {r}")
    pendiente = mosaico(pendientes)
    capas["pendiente"] = pendiente
    validos["pendiente"] = np.isfinite(pendiente)
    escribir_tif(salida / "pendiente.tif", pendiente, transform, crs)

    huellas = gpd.read_parquet(t04 / "huellas_sensibilidad.parquet")
    geoms = shapely.buffer(huellas.geometry.to_numpy(), AMPLIACION_M)
    print(f"huellas a ponderar: {len(geoms)}")
    tabla = ponderar(geoms, transform, forma, capas, validos)
    tabla.insert(0, "id_huella", huellas["id_huella"].to_numpy())
    for orbita in caso.orbitas:
        o = orbita.id
        tabla[f"valida_{o}"] = tabla[f"frac_z_{o}"] >= FRACCION_VALIDA_MIN
        tabla.loc[~tabla[f"valida_{o}"], [f"z_{o}", f"zpost_{o}", f"cohprev_{o}"]] = np.nan
    tabla = combinar_por_grupo(tabla, caso.grupos)

    col_clase = caso.columna_clase
    with rasterio.open(caso.ruta("clases_tif")) as r:
        cl = r.read(1)
        cent = huellas.geometry.centroid
        if rasterio.crs.CRS.from_user_input(crs) != r.crs:
            cent = cent.to_crs(r.crs)
        filas, cols = rasterio.transform.rowcol(r.transform, cent.x.to_numpy(), cent.y.to_numpy())
    filas, cols = np.asarray(filas), np.asarray(cols)
    dentro = (filas >= 0) & (filas < cl.shape[0]) & (cols >= 0) & (cols < cl.shape[1])
    clase = np.zeros(len(huellas), dtype=int)
    clase[dentro] = cl[filas[dentro], cols[dentro]]
    tabla[col_clase] = clase
    tabla["optico_A"] = np.where(clase > 0, clase >= 4, np.nan)
    tabla["optico_B"] = np.where(clase > 0, clase >= 5, np.nan)

    tabla.to_parquet(salida / "senales_huellas.parquet", index=False)
    conjuntos_res: dict[str, Any] = {}
    resumen: dict[str, Any] = {"convenciones": registro, "conjuntos": conjuntos_res}
    for nombre in caso.conjuntos:
        hh = pd.read_parquet(t04 / f"huellas_{nombre}.parquet", columns=["id_huella", "rol", "particion"])
        j = hh.merge(tabla[["id_huella", "valida_asc", "valida_des", "z_comb", col_clase]], on="id_huella")
        j["valida_comb"] = np.isfinite(j["z_comb"])
        j["con_optico"] = j[col_clase] > 0
        conjuntos_res[nombre] = {
            f"{rol}|{part}": {
                "huellas": len(g),
                "validas_asc": int(g["valida_asc"].sum()),
                "validas_des": int(g["valida_des"].sum()),
                "validas_comb": int(g["valida_comb"].sum()),
                "con_dato_optico": int(g["con_optico"].sum()),
            }
            for (rol, part), g in j.groupby(["rol", "particion"])
        }
        print(f"[{nombre}] {json.dumps(resumen['conjuntos'][nombre], ensure_ascii=False)}")
    (salida / "resumen_t05.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=2), encoding="utf-8")
    for f in sorted(salida.iterdir()):
        if f.is_file():
            print(f"huella {f.name} {sha256(f)}")
    print("FIN OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
