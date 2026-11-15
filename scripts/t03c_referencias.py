"""Tarea 03c del caso Penco 2026: que significa el grado de la referencia, comparado con Vina 2024.

No lee ninguna senal de radar ni la deteccion optica. Responde, con las mismas medidas para las dos
referencias, si los puntos de dano marcan edificaciones evaluadas una por una o todas las que caen dentro
del area quemada:

- conteo de valores de cada campo de la capa de puntos (grado, metodo de deteccion, notas, fuentes);
- fraccion de puntos dentro del area quemada de referencia y distancia de los que quedan fuera;
- huellas de Google Open Buildings con centroide en el area quemada y fraccion de ellas con punto de dano,
  por conjunto de confianza (si es casi 1, el grado se asigno por perimetro y no por edificacion).

Penco: EMSR859, area 4, producto de grado (`builtUpP`, `observedEventA`, `areaOfInterestA`), del zip del
banco verificado contra su `procedencia.toml`. Vina: EMSN188 P08 y area quemada de EMSR715 AOI01 v2, leidas
con `referencia.leer`, que verifica sus huellas.

Uso:
  python t03c_referencias.py <carpeta_caso_penco> <carpeta_caso_vina> <carpeta_trabajo_penco>

Escribe `<carpeta_trabajo_penco>/derivados/t03c/referencias.json` y no lo sobrescribe si existe.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import io
import itertools
import json
import shutil
import sys
import tomllib
import zipfile
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import pandas as pd
import pyogrio

import caso as caso_mod
import referencia
import t04_huellas_particion as t04
from caso import Caso, sha256

TOPE_VALORES = 15
TRAMOS_M = (0.0, 10.0, 50.0, 100.0, 500.0, 1000.0, 2000.0)
CAMPOS_FUERA = {"geometry", "fid", "grado"}


def conteo_campos(puntos: gpd.GeoDataFrame) -> dict[str, Any]:
    """Para cada campo: cuantos valores distintos tiene y los mas frecuentes (numericos: resumen)."""
    salida: dict[str, Any] = {}
    for c in puntos.columns:
        if c in CAMPOS_FUERA:
            continue
        s = puntos[c]
        d: dict[str, Any] = {"distintos": int(s.nunique(dropna=False)), "nulos": int(s.isna().sum())}
        if pd.api.types.is_numeric_dtype(s) and s.nunique(dropna=True) > TOPE_VALORES:
            v = s.dropna().astype(float)
            d["resumen"] = {
                "min": float(v.min()),
                "p25": float(v.quantile(0.25)),
                "mediana": float(v.median()),
                "p75": float(v.quantile(0.75)),
                "max": float(v.max()),
            }
        else:
            cuentas = s.astype("string").fillna("<nulo>").value_counts()
            d["valores"] = {str(k): int(n) for k, n in cuentas.head(TOPE_VALORES).items()}
            if len(cuentas) > TOPE_VALORES:
                d["otros"] = int(cuentas.iloc[TOPE_VALORES:].sum())
        salida[str(c)] = d
    return salida


def tramos_distancia(dist: np.ndarray) -> dict[str, int]:
    """Cuenta distancias en tramos: exactamente 0 (dentro), (0, 10], (10, 50], ... y mas de 2000."""
    salida = {"0 (dentro)": int((dist == 0).sum())}
    for a, b in itertools.pairwise(TRAMOS_M):
        salida[f"({a:g}, {b:g}]"] = int(((dist > a) & (dist <= b)).sum())
    salida[f"> {TRAMOS_M[-1]:g}"] = int((dist > TRAMOS_M[-1]).sum())
    return salida


def frac(a: int, b: int) -> float | None:
    return round(a / b, 4) if b else None


def resumir(
    puntos: gpd.GeoDataFrame,
    quemado: gpd.GeoDataFrame,
    huellas: gpd.GeoDataFrame,
    conjuntos: dict[str, float],
    radio_m: float,
    grados: dict[int, str],
) -> dict[str, Any]:
    """Mismas medidas para cualquier referencia. `puntos` trae `fid`, `grado` y sus campos originales."""
    union = quemado.geometry.union_all()
    dist = puntos.geometry.distance(union).to_numpy()
    dentro = dist == 0
    por_grado: dict[str, Any] = {}
    for g, nombre in sorted(grados.items(), reverse=True):
        m = (puntos["grado"] == g).to_numpy()
        por_grado[nombre] = {"puntos": int(m.sum()), "dentro_quemado": int((m & dentro).sum())}
    salida: dict[str, Any] = {
        "puntos": len(puntos),
        "por_grado": por_grado,
        "campos": conteo_campos(puntos),
        "area_quemada_ha": round(float(quemado.geometry.area.sum()) / 10_000, 1),
        "puntos_dentro_quemado": int(dentro.sum()),
        "fraccion_puntos_dentro_quemado": frac(int(dentro.sum()), len(puntos)),
        "distancia_al_quemado_m": tramos_distancia(dist),
        "conjuntos": {},
    }
    for nombre, umbral in conjuntos.items():
        h = huellas[huellas["confidence"] >= umbral].reset_index(drop=True)
        par = t04.emparejar(puntos[["fid", "grado", "geometry"]], h, radio_m)
        con_punto = set(par["id_huella"].dropna())
        centroides = gpd.GeoDataFrame(h[["id_huella"]], geometry=h.geometry.centroid, crs=h.crs)
        en_quemado = centroides[centroides.geometry.within(union)]
        ids_q = set(en_quemado["id_huella"])
        con_punto_q = ids_q & con_punto
        dist_h = centroides.geometry.distance(union).to_numpy()
        cerca = set(centroides.loc[(dist_h > 0) & (dist_h <= 1000.0), "id_huella"])
        salida["conjuntos"][nombre] = {
            "umbral_confianza": umbral,
            "huellas_en_caja": len(h),
            "puntos_por_metodo": {str(k): int(v) for k, v in par["metodo"].value_counts().items()},
            "fraccion_puntos_sin_huella": frac(int((par["metodo"] == "sin_huella").sum()), len(par)),
            "huellas_con_punto": len(con_punto),
            "huellas_centroide_en_quemado": len(ids_q),
            "huellas_en_quemado_con_punto": len(con_punto_q),
            "fraccion_huellas_en_quemado_con_punto": frac(len(con_punto_q), len(ids_q)),
            "huellas_a_1km_o_menos_fuera_del_quemado": len(cerca),
            "huellas_a_1km_o_menos_fuera_con_punto": len(cerca & con_punto),
            "fraccion_huellas_con_punto_dentro_quemado": frac(len(con_punto_q), len(con_punto)),
        }
    return salida


def verificar_zip_banco(zip_ruta: Path) -> str:
    procedencia = zip_ruta.parent / "procedencia.toml"
    registrados = {a["nombre"]: a for a in tomllib.loads(procedencia.read_text(encoding="utf-8"))["archivo"]}
    if zip_ruta.name not in registrados:
        raise caso_mod.CasoInvalido(f"{zip_ruta.name} no esta en {procedencia}")
    h = sha256(zip_ruta)
    if h != registrados[zip_ruta.name]["sha256"]:
        raise caso_mod.CasoInvalido(f"huella de {zip_ruta.name} distinta de la registrada: {h}")
    return h


def leer_penco(caso: Caso, tmp: Path) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame, gpd.GeoDataFrame, list[str]]:
    """Puntos (con todos sus campos), area quemada y area de interes del producto de grado del area fijada."""
    ref = caso.referencia
    zip_ruta = caso.ruta("referencia_zip")
    registro = [f"verificado {zip_ruta.name} {verificar_zip_banco(zip_ruta)}"]
    activacion, aoi, v = str(ref["activacion"]), int(ref["aoi"]), int(ref["version_puntos"])
    interno = f"{activacion}_AOI{aoi:02d}_GRA_PRODUCT_v{v}.zip"
    with zipfile.ZipFile(zip_ruta) as z:
        datos = z.read(interno)
    registro.append(f"producto interno {interno} sha256 {hashlib.sha256(datos).hexdigest()}")
    destino = tmp / interno.removesuffix(".zip")
    destino.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(datos)) as zi:
        zi.extractall(destino)
    prefijo = f"{activacion}_AOI{aoi:02d}_GRA_PRODUCT_"

    def capa(nombre: str) -> gpd.GeoDataFrame:
        encontradas = sorted(destino.rglob(f"{prefijo}{nombre}_v{v}.shp"))
        if len(encontradas) != 1:
            raise caso_mod.CasoInvalido(f"se esperaba una capa {prefijo}{nombre}_v{v}.shp y hay {len(encontradas)}")
        return gpd.read_file(encontradas[0]).to_crs(caso.crs)

    puntos = capa("builtUpP").reset_index(drop=True)
    valores = {str(k): int(n) for k, n in ref["valores_grado"].items()}
    puntos.insert(0, "fid", np.arange(len(puntos)))
    puntos.insert(1, "grado", puntos["damage_gra"].map(valores).fillna(0).astype(int))
    return puntos, capa("observedEventA"), capa("areaOfInterestA"), registro


def leer_vina(caso: Caso, tmp: Path) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame, list[str]]:
    """Puntos de EMSN188 P08 con todos sus campos y area quemada de EMSR715, con huellas verificadas."""
    ref = referencia.leer(caso, tmp)
    base = "/vsizip/" + str(caso.ruta("referencia_zip")).replace("\\", "/") + "/" + str(caso.referencia["gdb"])
    crudos = pyogrio.read_dataframe(base, layer=str(caso.referencia["capa_puntos"])).to_crs(caso.crs)
    if len(crudos) != len(ref.puntos):
        raise caso_mod.CasoInvalido("la capa de puntos de Vina no calza con la leida por referencia.leer")
    crudos = crudos.reset_index(drop=True)
    crudos.insert(0, "fid", ref.puntos["fid"].to_numpy())
    crudos.insert(1, "grado", ref.puntos["grado"].to_numpy())
    return crudos, ref.quemado, ref.registro


def main() -> int:
    if len(sys.argv) != 4:
        print(__doc__)
        return 2
    carpeta_penco, carpeta_vina, trabajo = map(Path, sys.argv[1:])
    salida = trabajo / "derivados" / "t03c"
    archivo = salida / "referencias.json"
    if archivo.exists():
        print("FALLO ya existe referencias.json en la carpeta de trabajo; no se sobrescribe")
        return 1
    salida.mkdir(parents=True, exist_ok=True)
    print(f"== inicio {dt.datetime.now().isoformat(timespec='seconds')}")
    penco = caso_mod.cargar(carpeta_penco)
    vina = caso_mod.cargar(carpeta_vina)
    for linea in caso_mod.verificar_documentos(penco):
        print(linea)
    tmp = salida / "_tmp"
    informe: dict[str, Any] = {"generado": dt.datetime.now().astimezone().isoformat(timespec="seconds")}
    try:
        puntos_p, quemado_p, aoi_p, reg_p = leer_penco(penco, tmp / "penco")
        for linea in reg_p:
            print(linea)
        huellas_p = t04.leer_open_buildings(penco, penco.ruta("open_buildings"))
        print(f"penco: {len(puntos_p)} puntos, {len(huellas_p)} huellas en la caja")
        informe["penco"] = resumir(
            puntos_p, quemado_p, huellas_p, penco.conjuntos, penco.radio_empareje_m, penco.grados
        )
        informe["penco"]["area_interes_ha"] = round(float(aoi_p.geometry.area.sum()) / 10_000, 1)
        informe["penco"]["referencia"] = "EMSR859 AOI04 producto de grado v2 (builtUpP, observedEventA)"

        puntos_v, quemado_v, reg_v = leer_vina(vina, tmp / "vina")
        for linea in reg_v:
            print(linea)
        huellas_v = t04.leer_open_buildings(vina, vina.ruta("open_buildings"))
        print(f"vina: {len(puntos_v)} puntos, {len(huellas_v)} huellas en la caja")
        informe["vina"] = resumir(puntos_v, quemado_v, huellas_v, vina.conjuntos, vina.radio_empareje_m, vina.grados)
        informe["vina"]["referencia"] = "EMSN188 P08 (puntos) y EMSR715 AOI01 v2 (area quemada)"
    finally:
        referencia.limpiar(tmp / "vina")
        shutil.rmtree(tmp, ignore_errors=True)

    presentes = {str(k) for k, d in informe["penco"]["por_grado"].items() if d["puntos"] > 0}
    faltan = sorted(set(penco.grados.values()) - presentes)
    informe["deteccion_1_lectura_estricta"] = {"detener": bool(faltan), "grados_ausentes": faltan}
    texto = json.dumps(informe, ensure_ascii=False, indent=2)
    archivo.write_text(texto, encoding="utf-8")
    print(texto)
    print(f"huella referencias.json {sha256(archivo)}")
    print("FIN OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
