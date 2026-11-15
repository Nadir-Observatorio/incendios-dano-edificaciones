"""Tarea 04 del caso de dano a edificaciones: huellas, emparejamiento con la referencia y particion.

No lee ninguna senal de radar ni la deteccion optica. Los parametros del caso salen de
`casos/<caso>/caso.toml` y las rutas de los insumos de `rutas.toml`.

Uso:
  python t04_huellas_particion.py <carpeta_caso> <carpeta_trabajo>

Escribe en `<carpeta_trabajo>/derivados/t04/` y se detiene si ya existe una particion ahi.
"""

from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path
from typing import Any

import geopandas as gpd
import h3
import numpy as np
import pandas as pd
import shapely

import caso as caso_mod
import referencia
from caso import Caso, sha256

# Valores del caso de origen (Vina 2024). Solo los usan las pruebas; las tareas leen caso.toml.
CRS = "EPSG:32719"
SEMILLA = 20240202
RADIO_EMPAREJE_M = 10.0


def leer_open_buildings(caso: Caso, carpeta: Path) -> gpd.GeoDataFrame:
    oeste, sur, este, norte = caso.caja
    minimo = min(caso.conjuntos.values())
    partes = []
    for nombre in caso.teselas:
        for trozo in pd.read_csv(
            carpeta / nombre,
            usecols=["latitude", "longitude", "area_in_meters", "confidence", "geometry", "full_plus_code"],
            chunksize=500_000,
        ):
            m = (
                (trozo["confidence"] >= minimo)
                & trozo["longitude"].between(oeste, este)
                & trozo["latitude"].between(sur, norte)
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
    return gdf.to_crs(caso.crs)


def h3_de(geoms: gpd.GeoSeries, res: int) -> list[str]:
    ll = geoms.to_crs("EPSG:4326")
    return [h3.latlng_to_cell(p.y, p.x, res) for p in ll]


def emparejar(puntos: gpd.GeoDataFrame, huellas: gpd.GeoDataFrame, radio_m: float = RADIO_EMPAREJE_M) -> pd.DataFrame:
    """Cada punto a la huella que lo contiene (la de menor area) o a la mas cercana a `radio_m` o menos."""
    h = huellas[["id_huella", "area_in_meters", "geometry"]]
    dentro = gpd.sjoin(puntos, h, predicate="within", how="inner")
    dentro = dentro.sort_values(["fid", "area_in_meters", "id_huella"]).drop_duplicates("fid")
    dentro = dentro.assign(metodo="dentro", distancia_m=0.0)[["fid", "id_huella", "metodo", "distancia_m"]]
    resto = puntos[~puntos["fid"].isin(dentro["fid"])]
    cerca = gpd.sjoin_nearest(resto, h, max_distance=radio_m, distance_col="distancia_m", how="inner")
    cerca = cerca.sort_values(["fid", "distancia_m", "id_huella"]).drop_duplicates("fid")
    cerca = cerca.assign(metodo="cercano")[["fid", "id_huella", "metodo", "distancia_m"]]
    todo = pd.concat([dentro, cerca], ignore_index=True)
    sin = puntos.loc[~puntos["fid"].isin(todo["fid"]), ["fid"]].assign(
        id_huella=None, metodo="sin_huella", distancia_m=np.nan
    )
    out = pd.concat([todo, sin], ignore_index=True).merge(puntos[["fid", "grado"]], on="fid")
    return out.sort_values("fid").reset_index(drop=True)


def particion(huellas: gpd.GeoDataFrame, puntos: gpd.GeoDataFrame, semilla: int = SEMILLA) -> pd.DataFrame:
    bloques = set(huellas["h3_r8"]) | set(puntos["h3_r8"])
    con_dano = set(puntos["h3_r8"])
    rng = np.random.default_rng(semilla)
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
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    carpeta_caso, trabajo = map(Path, sys.argv[1:])
    caso = caso_mod.cargar(carpeta_caso)
    salida = trabajo / "derivados" / "t04"
    if (salida / "particion.csv").exists():
        print("FALLO ya existe una particion en la carpeta de trabajo; no se sobrescribe")
        return 1
    salida.mkdir(parents=True, exist_ok=True)
    print(f"== inicio {dt.datetime.now().isoformat(timespec='seconds')} caso {caso.nombre}")
    docs_t04 = ["protocolo"] + [d.clave for d in caso.documentos if d.en_resumen_t04]
    for linea in caso_mod.verificar_documentos(caso, docs_t04):
        print(linea)

    tmp = salida / "_control"
    ref = referencia.leer(caso, tmp)
    for linea in ref.registro:
        print(linea)
    puntos = ref.puntos
    etiqueta = str(caso.referencia["etiqueta"])
    ctl = str(caso.referencia["etiqueta_control"])
    print(f"puntos de {etiqueta}: {len(puntos)}; grados {puntos['grado'].value_counts().sort_index().to_dict()}")
    huellas = leer_open_buildings(caso, caso.ruta("open_buildings"))
    print(f"huellas en la caja con confianza >= {min(caso.conjuntos.values())}: {len(huellas)}")

    cent = huellas.geometry.centroid
    huellas["h3_r8"] = h3_de(cent, 8)
    huellas["h3_r9"] = h3_de(cent, 9)
    huellas["h3_r10"] = h3_de(cent, 10)
    puntos["h3_r8"] = h3_de(puntos.geometry, 8)
    zona_geom = ref.zona.geometry.union_all()
    huellas["en_aoi"] = cent.within(zona_geom).to_numpy()
    area_geom = ref.area_control.geometry.union_all()
    quemado_geom = ref.quemado.geometry.union_all()
    shapely.prepare(area_geom)
    shapely.prepare(quemado_geom)
    pts = cent.to_numpy()
    huellas[f"en_aoi_{ctl}"] = shapely.contains(area_geom, pts)
    huellas[f"cerca_quemado_{ctl}"] = shapely.dwithin(quemado_geom, pts, caso.control_dist_m)

    part = particion(huellas, puntos, caso.semilla)
    ruta_part = salida / "particion.csv"
    part.to_csv(ruta_part, index=False, lineterminator="\n")
    h_part = sha256(ruta_part)
    (salida / "particion.sha256").write_text(f"{h_part}  particion.csv\n", encoding="utf-8")
    print(f"particion escrita: {len(part)} bloques, sha256 {h_part}")
    print(part.groupby(["estrato", "particion"]).size().to_string())

    conjuntos_res: dict[str, Any] = {}
    resumen: dict[str, Any] = {"protocolo_sha256": caso.documentos[0].sha256}
    for d in caso.documentos[1:]:
        if d.en_resumen_t04:
            resumen[f"{d.clave}_sha256"] = d.sha256
    resumen["particion_sha256"] = h_part
    resumen[str(caso.referencia["clave_puntos"])] = len(puntos)
    resumen["conjuntos"] = conjuntos_res
    if ref.asentamientos is not None:
        asent_area = float(ref.asentamientos.geometry.area.sum())
        asent_union = ref.asentamientos.geometry.union_all()

    for nombre, umbral in caso.conjuntos.items():
        sub = huellas[huellas["confidence"] >= umbral].copy()
        emp = emparejar(puntos, sub, caso.radio_empareje_m)
        emp.to_parquet(salida / f"puntos_{nombre}.parquet", index=False)
        por_huella = (
            emp.dropna(subset=["id_huella"]).groupby("id_huella").agg(n_puntos=("fid", "size"), grado=("grado", "max"))
        )
        sub = sub.merge(por_huella, left_on="id_huella", right_index=True, how="left")
        sub["n_puntos"] = sub["n_puntos"].fillna(0).astype(int)
        sub["grado"] = sub["grado"].fillna(0).astype(int)
        cerca = gpd.sjoin_nearest(
            sub[["id_huella", "geometry"]],
            puntos[["fid", "geometry"]],
            max_distance=caso.radio_empareje_m,
            how="inner",
        )
        con_punto_cerca = set(cerca["id_huella"])
        rol = np.where(sub["n_puntos"] > 0, "positivo", "otro").astype(object)
        neg = (sub["n_puntos"] == 0) & sub["en_aoi"] & ~sub["id_huella"].isin(con_punto_cerca)
        ctrl = (~sub["en_aoi"]) & sub[f"en_aoi_{ctl}"] & ~sub[f"cerca_quemado_{ctl}"]
        rol[neg.to_numpy()] = "negativo"
        rol[(ctrl & (sub["n_puntos"] == 0)).to_numpy()] = "control"
        sub["rol"] = rol
        sub = sub.merge(part[["h3_r8", "particion"]], on="h3_r8", how="left")
        sub.to_parquet(salida / f"huellas_{nombre}.parquet", index=False)

        res_conj: dict[str, Any] = {
            "umbral_confianza": umbral,
            "huellas": len(sub),
            "puntos_por_metodo": emp["metodo"].value_counts().to_dict(),
            "fraccion_puntos_sin_huella": float((emp["metodo"] == "sin_huella").mean()),
            "huellas_por_rol_y_particion": {
                f"{r}|{p}": int(n) for (r, p), n in sub.groupby(["rol", "particion"]).size().items()
            },
            "positivos_por_grado": {
                caso.grados[int(g)]: int(n)
                for g, n in sub.loc[sub["rol"] == "positivo", "grado"].value_counts().items()
            },
        }
        if ref.asentamientos is not None:
            cubierto = float(shapely.intersection(asent_union, sub.geometry.union_all()).area)
            res_conj[str(caso.referencia["clave_completitud"])] = cubierto / asent_area if asent_area else None
        conjuntos_res[nombre] = res_conj
        print(f"[{nombre}] {json.dumps(resumen['conjuntos'][nombre], ensure_ascii=False)}")

    (salida / "resumen_t04.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=2), encoding="utf-8")
    referencia.limpiar(tmp)
    for f in sorted(salida.iterdir()):
        if f.is_file():
            print(f"huella {f.name} {sha256(f)}")
    print("FIN OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
