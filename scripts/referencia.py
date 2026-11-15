"""Lectura de la referencia de dano y de las zonas de cada caso.

Una referencia entrega lo mismo para cualquier caso:

- `puntos`: puntos de dano con `fid` y `grado` (3, 2 o 1 segun `[grados]` del caso);
- `zona`: zona de negativos (en Vina, `P00_aoi` de EMSN188);
- `area_control`: area donde puede haber control lejano (en Vina, el area de interes de EMSR715 AOI01);
- `quemado`: area quemada oficial de la que se mide la distancia del control;
- `asentamientos`: capa de asentamientos para medir completitud de huellas, si la referencia la trae.

Tipos soportados: `emsn188_emsr715` (Vina 2024). Otro tipo se rechaza con un error explicito.
"""

from __future__ import annotations

import hashlib
import io
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

import geopandas as gpd
import pyogrio

from caso import Caso, CasoInvalido, sha256


@dataclass
class Referencia:
    puntos: gpd.GeoDataFrame
    zona: gpd.GeoDataFrame
    area_control: gpd.GeoDataFrame
    quemado: gpd.GeoDataFrame
    asentamientos: gpd.GeoDataFrame | None
    registro: list[str] = field(default_factory=list)


def _emsn188(caso: Caso, zip_ruta: Path) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame, gpd.GeoDataFrame]:
    ref = caso.referencia
    base = "/vsizip/" + str(zip_ruta).replace("\\", "/") + "/" + str(ref["gdb"])
    puntos = pyogrio.read_dataframe(base, layer=str(ref["capa_puntos"]), fid_as_index=True)
    puntos = puntos.reset_index().rename(columns={"index": "fid", "fid": "fid"})
    if "fid" not in puntos.columns:
        puntos = puntos.rename(columns={puntos.columns[0]: "fid"})
    puntos["grado"] = puntos[str(ref["campo_grado"])].astype(int)
    puntos = puntos[["fid", "grado", "geometry"]].to_crs(caso.crs)
    aoi = pyogrio.read_dataframe(base, layer=str(ref["capa_zona"])).to_crs(caso.crs)
    asentamientos = pyogrio.read_dataframe(base, layer=str(ref["capa_asentamientos"])).to_crs(caso.crs)
    return puntos, aoi, asentamientos


def emsr715_zonas(caso: Caso, zip_ruta: Path, tmp: Path) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    """Area de interes y area quemada observada del producto de delineacion de control, con su huella interna."""
    ref = caso.referencia
    producto = str(ref["control_producto"])
    with zipfile.ZipFile(zip_ruta) as externo:
        interno = externo.read(producto)
    h = hashlib.sha256(interno).hexdigest()
    if h != str(ref["control_producto_sha256"]):
        raise CasoInvalido(f"huella del producto interno {producto} distinta: {h}")
    tmp.mkdir(parents=True, exist_ok=True)
    capa_aoi, capa_evento = str(ref["control_capa_area"]), str(ref["control_capa_quemado"])
    with zipfile.ZipFile(io.BytesIO(interno)) as z:
        for nombre in z.namelist():
            if capa_aoi in nombre or capa_evento in nombre:
                (tmp / Path(nombre).name).write_bytes(z.read(nombre))
    prefijo = producto.removesuffix(".zip").rsplit("_v", 1)[0]
    aoi = gpd.read_file(tmp / f"{prefijo}_{capa_aoi}.shp").to_crs(caso.crs)
    evento = gpd.read_file(tmp / f"{prefijo}_{capa_evento}.shp").to_crs(caso.crs)
    return aoi, evento


def limpiar(tmp: Path) -> None:
    if tmp.exists():
        for f in sorted(tmp.iterdir()):
            f.unlink()
        tmp.rmdir()


def leer(caso: Caso, tmp: Path) -> Referencia:
    """Lee y verifica la referencia del caso. Los archivos temporales quedan en `tmp` hasta `limpiar`."""
    tipo = str(caso.referencia["tipo"])
    if tipo != "emsn188_emsr715":
        raise CasoInvalido(f"tipo de referencia no soportado: {tipo}")
    registro = []
    zip_ref = caso.ruta("referencia_zip")
    zip_ctl = caso.ruta("control_zip")
    for ruta, esperado in (
        (zip_ref, str(caso.referencia["sha256"])),
        (zip_ctl, str(caso.referencia["control_sha256"])),
    ):
        h = sha256(ruta)
        if h != esperado:
            raise CasoInvalido(f"huella de {ruta.name} distinta: {h}")
        registro.append(f"verificado {ruta.name} {h}")
    puntos, zona, asentamientos = _emsn188(caso, zip_ref)
    area_control, quemado = emsr715_zonas(caso, zip_ctl, tmp)
    registro.append("control: area quemada de la delineacion de control leida y verificada")
    return Referencia(puntos, zona, area_control, quemado, asentamientos, registro)
