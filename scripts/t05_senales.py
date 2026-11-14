"""Tarea 05 del caso de dano a edificaciones (etapa E4).

Senales por pixel y por huella: coherencia previa, `z` del evento y `z` posterior por geometria, mascara
de inversion y sombra, pendiente, y deteccion optica de la Etapa 1. No fija umbrales ni calcula
metricas; eso es la tarea 06, que evalua la particion de prueba una sola vez. El resumen de esta tarea
solo informa cuantas huellas tienen dato, sin distribuciones de la senal por rol.

Uso:
  python t05_senales.py <carpeta_caso> <carpeta_banco_hyp3> <carpeta_t04> <clases_tif> <carpeta_salida>
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import sys
import tomllib
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

VERIFICAR = {
    "PROTOCOLO_dano-edificaciones_sellado_2026-11-11.md": "de1993790a4e7485aeef3d64749a490dd735679feb5575263bc61ca727387f5d",
    "ENMIENDA_01_2026-11-11.md": "8ff741dde5bb5b2bbf391fe7652e5088640c2c02b0ac4c28818d0419a122bc1e",
    "ENMIENDA_02_2026-11-11.md": "82f1000d908f662e9e24596232a0832b493aa767d117af95012dd724d4341b27",
}
PARTICION_SHA256 = "2eaf84510b7c100ae5ca1f216ad7eb6c2f347bee011bb9b05fac81a4a7a61d2e"
CLASES_CONTENT_SHA256 = "ef09b76717fc2855e0fcaf1cd939ecf2e69e6ea7ea416c9f4618e050244f6902"

OESTE, SUR, ESTE, NORTE = -71.60, -33.13, -71.38, -32.94
CRS = "EPSG:32719"
RES = 20.0
PREVIOS = [f"previo{i}" for i in range(1, 7)]
MIN_PREVIOS = 4
S_MIN = 0.05
AMPLIACION_M = 10.0
FRACCION_VALIDA_MIN = 0.5
AZIMUT_ESPERADO = {"asc": 180.0, "des": 0.0}


def sha256(ruta: Path) -> str:
    h = hashlib.sha256()
    with ruta.open("rb") as f:
        for bloque in iter(lambda: f.read(1 << 22), b""):
            h.update(bloque)
    return h.hexdigest()


def grilla() -> tuple[rasterio.Affine, tuple[int, int]]:
    x0, y0, x1, y1 = transform_bounds("EPSG:4326", CRS, OESTE, SUR, ESTE, NORTE)
    x0 = np.floor(x0 / RES) * RES
    y1 = np.ceil(y1 / RES) * RES
    ancho = int(np.ceil((x1 - x0) / RES))
    alto = int(np.ceil((y1 - y0) / RES))
    return from_origin(x0, y1, RES, RES), (alto, ancho)


def capa(zip_ruta: Path, sufijo: str, transform: rasterio.Affine, forma: tuple[int, int]) -> np.ndarray:
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
            dst_crs=CRS,
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
    theta: np.ndarray, phi: np.ndarray, dem: np.ndarray, geometria: str, registro: list[str]
) -> tuple[np.ndarray, np.ndarray]:
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
        raise ValueError(f"{geometria}: mediana de lv_phi {med_p:.1f} grados no calza con lo esperado")
    registro.append(
        f"{geometria}: lv_theta mediana {med_t:.2f} grados ({'radianes' if unidad_rad else 'grados'} en origen, "
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


def escribir_tif(ruta: Path, arr: np.ndarray, transform: rasterio.Affine) -> None:
    with rasterio.open(
        ruta,
        "w",
        driver="GTiff",
        height=arr.shape[0],
        width=arr.shape[1],
        count=1,
        dtype="float32",
        crs=CRS,
        transform=transform,
        nodata=np.nan,
        compress="deflate",
        predictor=3,
        tiled=True,
    ) as w:
        w.write(arr.astype("float32"), 1)


def main() -> int:
    if len(sys.argv) != 6:
        print(__doc__)
        return 2
    caso, banco, t04, clases_tif, salida = map(Path, sys.argv[1:])
    salida.mkdir(parents=True, exist_ok=True)
    print(f"== inicio {dt.datetime.now().isoformat(timespec='seconds')}")
    for nombre, esperado in VERIFICAR.items():
        h = sha256(caso / nombre)
        if h != esperado:
            print(f"FALLO huella de {nombre}: {h}")
            return 1
        print(f"verificado {nombre}")
    h = sha256(t04 / "particion.csv")
    if h != PARTICION_SHA256:
        print(f"FALLO huella de la particion: {h}")
        return 1
    print("verificada la particion de la tarea 04")

    proc = tomllib.loads((banco / "procedencia.toml").read_text(encoding="utf-8"))
    archivos = proc["archivo"]
    print(f"productos registrados: {len(archivos)}")
    for a in archivos:
        h = sha256(banco / a["nombre"])
        if h != a["sha256"]:
            print(f"FALLO huella de {a['nombre']}")
            return 1
    print("huellas de los 56 productos verificadas")
    with zipfile.ZipFile(banco / archivos[0]["nombre"]) as zf:
        readme = next(n for n in zf.namelist() if n.endswith("_README.md.txt"))
        lineas_dem = [x.strip() for x in zf.read(readme).decode("utf-8", "replace").splitlines() if "DEM" in x]
    for linea in lineas_dem[:6]:
        print(f"README (DEM): {linea}")

    transform, forma = grilla()
    print(f"grilla comun {CRS} {forma[1]} x {forma[0]} pixeles de {RES:.0f} m")
    registro: list[str] = []
    capas: dict[str, np.ndarray] = {}
    validos: dict[str, np.ndarray] = {}
    pendientes = []
    for geometria in ("asc", "des"):
        propios = [a for a in archivos if a["geometria"] == geometria]
        coh: dict[str, np.ndarray] = {}
        for rol in [*PREVIOS, "evento", "posterior"]:
            zs = [banco / a["nombre"] for a in propios if a["rol"] == rol]
            coh[rol] = mosaico([capa(z, "corr", transform, forma) for z in zs])
        evento = [banco / a["nombre"] for a in propios if a["rol"] == "evento"]
        theta = mosaico([capa(z, "lv_theta", transform, forma) for z in evento])
        phi = mosaico([capa(z, "lv_phi", transform, forma) for z in evento])
        dem = mosaico([capa(z, "dem", transform, forma) for z in evento])
        geo_ok, pend = mascara_geometria(theta, phi, dem, geometria, registro)
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
        for clave, arr in ((f"z_{geometria}", z), (f"zpost_{geometria}", zp), (f"cohprev_{geometria}", m_ok)):
            capas[clave] = arr.astype("float32")
            validos[clave] = np.isfinite(arr)
            escribir_tif(salida / f"{clave}.tif", arr, transform)
        escribir_tif(salida / f"mascara_geometria_{geometria}.tif", geo_ok.astype("float32"), transform)
        print(
            f"{geometria}: pixeles con z valida {int(np.isfinite(z).sum())} de {z.size}; "
            f"inversion o sombra {int((~geo_ok & np.isfinite(dem)).sum())}"
        )
    for r in registro:
        print(f"convencion {r}")
    pendiente = mosaico(pendientes)
    capas["pendiente"] = pendiente
    validos["pendiente"] = np.isfinite(pendiente)
    escribir_tif(salida / "pendiente.tif", pendiente, transform)

    huellas = gpd.read_parquet(t04 / "huellas_sensibilidad.parquet")
    geoms = shapely.buffer(huellas.geometry.to_numpy(), AMPLIACION_M)
    print(f"huellas a ponderar: {len(geoms)}")
    tabla = ponderar(geoms, transform, forma, capas, validos)
    tabla.insert(0, "id_huella", huellas["id_huella"].to_numpy())
    for g in ("asc", "des"):
        tabla[f"valida_{g}"] = tabla[f"frac_z_{g}"] >= FRACCION_VALIDA_MIN
        tabla.loc[~tabla[f"valida_{g}"], [f"z_{g}", f"zpost_{g}", f"cohprev_{g}"]] = np.nan
    za = tabla["z_asc"].to_numpy()
    zd = tabla["z_des"].to_numpy()
    with np.errstate(invalid="ignore"):
        tabla["z_comb"] = np.nanmean(np.vstack([za, zd]), axis=0)
        tabla["zpost_comb"] = np.nanmean(np.vstack([tabla["zpost_asc"], tabla["zpost_des"]]), axis=0)
        tabla["cohprev_comb"] = np.nanmean(np.vstack([tabla["cohprev_asc"], tabla["cohprev_des"]]), axis=0)

    with rasterio.open(clases_tif) as r:
        cl = r.read(1)
        cent = huellas.geometry.centroid
        filas, cols = rasterio.transform.rowcol(r.transform, cent.x.to_numpy(), cent.y.to_numpy())
    filas, cols = np.asarray(filas), np.asarray(cols)
    dentro = (filas >= 0) & (filas < cl.shape[0]) & (cols >= 0) & (cols < cl.shape[1])
    clase = np.zeros(len(huellas), dtype=int)
    clase[dentro] = cl[filas[dentro], cols[dentro]]
    tabla["clase_etapa1"] = clase
    tabla["optico_A"] = np.where(clase > 0, clase >= 4, np.nan)
    tabla["optico_B"] = np.where(clase > 0, clase >= 5, np.nan)

    tabla.to_parquet(salida / "senales_huellas.parquet", index=False)
    conjuntos_res: dict[str, Any] = {}
    resumen: dict[str, Any] = {"convenciones": registro, "conjuntos": conjuntos_res}
    for nombre in ("principal", "sensibilidad"):
        h = pd.read_parquet(t04 / f"huellas_{nombre}.parquet", columns=["id_huella", "rol", "particion"])
        j = h.merge(tabla[["id_huella", "valida_asc", "valida_des", "z_comb", "clase_etapa1"]], on="id_huella")
        j["valida_comb"] = np.isfinite(j["z_comb"])
        j["con_optico"] = j["clase_etapa1"] > 0
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
