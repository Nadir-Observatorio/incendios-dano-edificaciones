"""Tarea 04 del caso de dano a edificaciones (etapa E3).

Huellas, emparejamiento con EMSN188 y particion de ajuste y prueba. No lee ninguna senal de radar ni
la deteccion optica de la Etapa 1. El control lejano sale de la delineacion oficial de EMSR715
(enmienda 01, punto 5).

Uso:
  python t04_huellas_particion.py <carpeta_caso> <carpeta_open_buildings> <zip_emsn188>
                                  <zip_emsr715> <carpeta_salida>
"""

from __future__ import annotations

import datetime as dt
import hashlib
import io
import json
import sys
import zipfile
from pathlib import Path
from typing import Any

import geopandas as gpd
import h3
import numpy as np
import pandas as pd
import pyogrio
import shapely

PROTOCOLO = "PROTOCOLO_dano-edificaciones_sellado_2026-11-11.md"
PROTOCOLO_SHA256 = "de1993790a4e7485aeef3d64749a490dd735679feb5575263bc61ca727387f5d"
ENMIENDA = "ENMIENDA_01_2026-11-11.md"
ENMIENDA_SHA256 = "8ff741dde5bb5b2bbf391fe7652e5088640c2c02b0ac4c28818d0419a122bc1e"
EMSN188_SHA256 = "443e7c353f392c56124004a9ae3b2dfc1dbb1af26d9fd0fef31f610cb5dafed3"
EMSR715_SHA256 = "aa31440615508ba60cba1fe3da0c9e980d308d6547d76a7a0bf21a81b0a25905"
EMSR715_PRODUCTO = "EMSR715_AOI01_DEL_PRODUCT_v2.zip"
EMSR715_PRODUCTO_SHA256 = "7742f03b8191187757e09d1f318b4001786612bd8b3c223e4023e9a662b67eb8"

OESTE, SUR, ESTE, NORTE = -71.60, -33.13, -71.38, -32.94
CRS = "EPSG:32719"
TESELAS = ["967_buildings.csv.gz", "969_buildings.csv.gz"]
GDB = "Geospatial_data/GDB/EMSN188_STD_UTM19S_r02_v01.gdb"
CONJUNTOS = {"principal": 0.75, "sensibilidad": 0.65}
RADIO_EMPAREJE_M = 10.0
CONTROL_DIST_M = 2000.0
SEMILLA = 20240202
GRADOS = {3: "Destroyed", 2: "Damaged", 1: "Possible damage"}


def sha256(ruta: Path) -> str:
    h = hashlib.sha256()
    with ruta.open("rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def leer_open_buildings(carpeta: Path) -> gpd.GeoDataFrame:
    partes = []
    for nombre in TESELAS:
        for trozo in pd.read_csv(
            carpeta / nombre,
            usecols=["latitude", "longitude", "area_in_meters", "confidence", "geometry", "full_plus_code"],
            chunksize=500_000,
        ):
            m = (
                (trozo["confidence"] >= min(CONJUNTOS.values()))
                & trozo["longitude"].between(OESTE, ESTE)
                & trozo["latitude"].between(SUR, NORTE)
            )
            if m.any():
                partes.append(trozo.loc[m].assign(tesela=nombre.split("_")[0]))
    df = pd.concat(partes, ignore_index=True)
    df = df.drop_duplicates(subset=["full_plus_code", "area_in_meters", "confidence"])
    df = df.sort_values(["full_plus_code", "area_in_meters"]).reset_index(drop=True)
    gdf = gpd.GeoDataFrame(
        df.drop(columns=["geometry"]),
        geometry=shapely.from_wkt(df["geometry"].to_numpy()),
        crs="EPSG:4326",
    )
    gdf["id_huella"] = [f"gob{i:07d}" for i in range(len(gdf))]
    return gdf.to_crs(CRS)


def leer_emsn188(zip_ruta: Path) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame, gpd.GeoDataFrame]:
    base = "/vsizip/" + str(zip_ruta).replace("\\", "/") + "/" + GDB
    puntos = pyogrio.read_dataframe(base, layer="P08DDA_DamageAssessmentP", fid_as_index=True)
    puntos = puntos.reset_index().rename(columns={"index": "fid", "fid": "fid"})
    if "fid" not in puntos.columns:
        puntos = puntos.rename(columns={puntos.columns[0]: "fid"})
    puntos["grado"] = puntos["damage_gra"].astype(int)
    puntos = puntos[["fid", "grado", "geometry"]].to_crs(CRS)
    aoi = pyogrio.read_dataframe(base, layer="P00_aoi").to_crs(CRS)
    p18 = pyogrio.read_dataframe(base, layer="P18HUST_HumanSettlements").to_crs(CRS)
    return puntos, aoi, p18


def leer_emsr715(zip_ruta: Path, tmp: Path) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    """Area de interes y area quemada observada de EMSR715 AOI01, delineacion version 2."""
    with zipfile.ZipFile(zip_ruta) as externo:
        interno = externo.read(EMSR715_PRODUCTO)
    h = hashlib.sha256(interno).hexdigest()
    if h != EMSR715_PRODUCTO_SHA256:
        raise ValueError(f"huella del producto interno de EMSR715 distinta: {h}")
    tmp.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(interno)) as z:
        for nombre in z.namelist():
            if "areaOfInterestA_v2" in nombre or "observedEventA_v2" in nombre:
                (tmp / Path(nombre).name).write_bytes(z.read(nombre))
    aoi = gpd.read_file(tmp / "EMSR715_AOI01_DEL_PRODUCT_areaOfInterestA_v2.shp").to_crs(CRS)
    evento = gpd.read_file(tmp / "EMSR715_AOI01_DEL_PRODUCT_observedEventA_v2.shp").to_crs(CRS)
    return aoi, evento


def h3_de(geoms: gpd.GeoSeries, res: int) -> list[str]:
    ll = geoms.to_crs("EPSG:4326")
    return [h3.latlng_to_cell(p.y, p.x, res) for p in ll]


def emparejar(puntos: gpd.GeoDataFrame, huellas: gpd.GeoDataFrame) -> pd.DataFrame:
    """Cada punto a la huella que lo contiene (la de menor area) o a la mas cercana a <= 10 m."""
    h = huellas[["id_huella", "area_in_meters", "geometry"]]
    dentro = gpd.sjoin(puntos, h, predicate="within", how="inner")
    dentro = dentro.sort_values(["fid", "area_in_meters", "id_huella"]).drop_duplicates("fid")
    dentro = dentro.assign(metodo="dentro", distancia_m=0.0)[["fid", "id_huella", "metodo", "distancia_m"]]
    resto = puntos[~puntos["fid"].isin(dentro["fid"])]
    cerca = gpd.sjoin_nearest(resto, h, max_distance=RADIO_EMPAREJE_M, distance_col="distancia_m", how="inner")
    cerca = cerca.sort_values(["fid", "distancia_m", "id_huella"]).drop_duplicates("fid")
    cerca = cerca.assign(metodo="cercano")[["fid", "id_huella", "metodo", "distancia_m"]]
    todo = pd.concat([dentro, cerca], ignore_index=True)
    sin = puntos.loc[~puntos["fid"].isin(todo["fid"]), ["fid"]].assign(
        id_huella=None, metodo="sin_huella", distancia_m=np.nan
    )
    out = pd.concat([todo, sin], ignore_index=True).merge(puntos[["fid", "grado"]], on="fid")
    return out.sort_values("fid").reset_index(drop=True)


def particion(huellas: gpd.GeoDataFrame, puntos: gpd.GeoDataFrame) -> pd.DataFrame:
    bloques = set(huellas["h3_r8"]) | set(puntos["h3_r8"])
    con_dano = set(puntos["h3_r8"])
    rng = np.random.default_rng(SEMILLA)
    filas = []
    for estrato, miembros in (
        ("con_dano", sorted(b for b in bloques if b in con_dano)),
        ("sin_dano", sorted(b for b in bloques if b not in con_dano)),
    ):
        perm = [miembros[i] for i in rng.permutation(len(miembros))]
        corte = len(perm) // 2
        filas += [(b, estrato, "ajuste") for b in perm[:corte]]
        filas += [(b, estrato, "prueba") for b in perm[corte:]]
    return pd.DataFrame(filas, columns=["h3_r8", "estrato", "particion"]).sort_values("h3_r8").reset_index(drop=True)


def main() -> int:
    if len(sys.argv) != 6:
        print(__doc__)
        return 2
    caso, carpeta_gob, zip_emsn, zip_emsr715, salida = map(Path, sys.argv[1:])
    salida.mkdir(parents=True, exist_ok=True)
    print(f"== inicio {dt.datetime.now().isoformat(timespec='seconds')}")

    for ruta, esperado in (
        (caso / PROTOCOLO, PROTOCOLO_SHA256),
        (caso / ENMIENDA, ENMIENDA_SHA256),
        (zip_emsn, EMSN188_SHA256),
        (zip_emsr715, EMSR715_SHA256),
    ):
        h = sha256(ruta)
        if h != esperado:
            print(f"FALLO huella de {ruta.name}: {h}")
            return 1
        print(f"verificado {ruta.name} {h}")

    puntos, aoi, p18 = leer_emsn188(zip_emsn)
    print(f"puntos P08: {len(puntos)}; grados {puntos['grado'].value_counts().sort_index().to_dict()}")
    huellas = leer_open_buildings(carpeta_gob)
    print(f"huellas en la caja con confianza >= 0,65: {len(huellas)}")

    cent = huellas.geometry.centroid
    huellas["h3_r8"] = h3_de(cent, 8)
    huellas["h3_r9"] = h3_de(cent, 9)
    huellas["h3_r10"] = h3_de(cent, 10)
    puntos["h3_r8"] = h3_de(puntos.geometry, 8)
    aoi_geom = aoi.geometry.union_all()
    huellas["en_aoi"] = cent.within(aoi_geom).to_numpy()
    aoi715, evento715 = leer_emsr715(zip_emsr715, salida / "_emsr715")
    aoi715_geom = aoi715.geometry.union_all()
    evento_geom = evento715.geometry.union_all()
    shapely.prepare(aoi715_geom)
    shapely.prepare(evento_geom)
    pts = cent.to_numpy()
    huellas["en_aoi_emsr715"] = shapely.contains(aoi715_geom, pts)
    huellas["cerca_quemado_emsr715"] = shapely.dwithin(evento_geom, pts, CONTROL_DIST_M)
    print("control: area quemada de EMSR715 AOI01 v2 leida y verificada")

    part = particion(huellas, puntos)
    ruta_part = salida / "particion.csv"
    part.to_csv(ruta_part, index=False, lineterminator="\n")
    h_part = sha256(ruta_part)
    (salida / "particion.sha256").write_text(f"{h_part}  particion.csv\n", encoding="utf-8")
    print(f"particion escrita: {len(part)} bloques, sha256 {h_part}")
    print(part.groupby(["estrato", "particion"]).size().to_string())

    conjuntos_res: dict[str, Any] = {}
    resumen: dict[str, Any] = {
        "protocolo_sha256": PROTOCOLO_SHA256,
        "enmienda_01_sha256": ENMIENDA_SHA256,
        "particion_sha256": h_part,
        "puntos_p08": len(puntos),
        "conjuntos": conjuntos_res,
    }
    p18_area = float(p18.geometry.area.sum())
    p18_union = p18.geometry.union_all()

    for nombre, umbral in CONJUNTOS.items():
        sub = huellas[huellas["confidence"] >= umbral].copy()
        emp = emparejar(puntos, sub)
        emp.to_parquet(salida / f"puntos_{nombre}.parquet", index=False)
        por_huella = (
            emp.dropna(subset=["id_huella"]).groupby("id_huella").agg(n_puntos=("fid", "size"), grado=("grado", "max"))
        )
        sub = sub.merge(por_huella, left_on="id_huella", right_index=True, how="left")
        sub["n_puntos"] = sub["n_puntos"].fillna(0).astype(int)
        sub["grado"] = sub["grado"].fillna(0).astype(int)
        cerca = gpd.sjoin_nearest(
            sub[["id_huella", "geometry"]], puntos[["fid", "geometry"]], max_distance=RADIO_EMPAREJE_M, how="inner"
        )
        con_punto_cerca = set(cerca["id_huella"])
        rol = np.where(sub["n_puntos"] > 0, "positivo", "otro").astype(object)
        neg = (sub["n_puntos"] == 0) & sub["en_aoi"] & ~sub["id_huella"].isin(con_punto_cerca)
        ctrl = (~sub["en_aoi"]) & sub["en_aoi_emsr715"] & ~sub["cerca_quemado_emsr715"]
        rol[neg.to_numpy()] = "negativo"
        rol[(ctrl & (sub["n_puntos"] == 0)).to_numpy()] = "control"
        sub["rol"] = rol
        sub = sub.merge(part[["h3_r8", "particion"]], on="h3_r8", how="left")
        sub.to_parquet(salida / f"huellas_{nombre}.parquet", index=False)

        cubierto = float(shapely.intersection(p18_union, sub.geometry.union_all()).area)
        conjuntos_res[nombre] = {
            "umbral_confianza": umbral,
            "huellas": len(sub),
            "puntos_por_metodo": emp["metodo"].value_counts().to_dict(),
            "fraccion_puntos_sin_huella": float((emp["metodo"] == "sin_huella").mean()),
            "huellas_por_rol_y_particion": {
                f"{r}|{p}": int(n) for (r, p), n in sub.groupby(["rol", "particion"]).size().items()
            },
            "positivos_por_grado": {
                GRADOS[int(g)]: int(n) for g, n in sub.loc[sub["rol"] == "positivo", "grado"].value_counts().items()
            },
            "fraccion_area_p18_cubierta": cubierto / p18_area if p18_area else None,
        }
        print(f"[{nombre}] {json.dumps(resumen['conjuntos'][nombre], ensure_ascii=False)}")

    (salida / "resumen_t04.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=2), encoding="utf-8")
    for f in sorted((salida / "_emsr715").iterdir()):
        f.unlink()
    (salida / "_emsr715").rmdir()
    for f in sorted(salida.iterdir()):
        if f.is_file():
            print(f"huella {f.name} {sha256(f)}")
    print("FIN OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
