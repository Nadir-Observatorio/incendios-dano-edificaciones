"""Tarea 03b del caso Penco 2026: baja EMSR859 al banco e inspecciona su estructura.

No lee ninguna senal de radar ni la deteccion optica. Guarda en el banco el zip de productos de Copernicus EMS
y una copia de la respuesta de su API publica (de ahi sale la direccion del zip y la version de cada
producto), con su procedencia. Despues inspecciona el producto de grado del area de interes del caso y la
delineacion de verificacion, y responde las detenciones 1 y 2 del protocolo sellado:

1. el producto no trae la capa de puntos en la version fijada, o su campo de grado no trae los valores fijados;
2. la capa de areas construidas (`builtUpA`) trae elementos con grado de dano.

Uso:
  python t03b_emsr859.py <carpeta_caso> <carpeta_trabajo>

El banco es la carpeta del zip en `rutas.toml` (`referencia_zip`). Si el zip ya esta en el banco con su
huella registrada, no se vuelve a bajar. Si el servidor corta la descarga, se sigue por rangos; si el zip se
bajo a mano en el navegador y aun no tiene procedencia, se registra tal cual con ese metodo. El informe queda
en `<carpeta_trabajo>/derivados/t03b/`.
"""

from __future__ import annotations

import datetime as dt
import http.client
import io
import json
import shutil
import ssl
import sys
import time
import tomllib
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

import geopandas as gpd
import truststore

import caso as caso_mod
from caso import Caso, sha256

INTENTOS = 3
INTENTOS_DESCARGA = 8
ESPERA_S = 5.0
BLOQUE = 1 << 20
# Verificacion TLS con el almacen de certificados del sistema operativo: en Windows completa
# los certificados intermedios que el servidor no envia. La verificacion nunca se desactiva.
CONTEXTO_TLS = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)


def abrir(url: str, timeout: float, cabeceras: dict[str, str] | None = None) -> Any:
    if not url.startswith("https://"):
        raise ValueError(f"solo se usan direcciones https: {url}")
    for intento in range(1, INTENTOS + 1):
        try:
            pedido = urllib.request.Request(  # noqa: S310 (https comprobado)
                url, headers={"User-Agent": "nadir-dano/1.0", **(cabeceras or {})}
            )
            return urllib.request.urlopen(pedido, timeout=timeout, context=CONTEXTO_TLS)  # noqa: S310
        except OSError as error:
            if intento == INTENTOS:
                raise
            print(f"reintento {intento} de {url}: {error}")
            time.sleep(ESPERA_S * intento)
    raise RuntimeError("no se alcanzo el servicio")


def largo_total(r: Any, desde: int) -> int | None:
    """Tamano completo del archivo segun las cabeceras de la respuesta, si el servidor lo informa."""
    if r.status == 206:
        rango = r.headers.get("Content-Range", "")
        total = rango.rpartition("/")[2]
        return int(total) if total.isdigit() else None
    largo = r.headers.get("Content-Length", "")
    return int(largo) + desde if largo.isdigit() else None


def bajar(url: str, destino: Path) -> dict[str, Any]:
    """Baja a un archivo parcial y lo completa por rangos si el servidor corta la conexion.

    Solo se deja en `destino` un zip completo: mismo largo que informa el servidor y estructura de zip valida.
    Si no se completa, el parcial queda en el banco y la proxima ejecucion sigue desde donde quedo.
    """
    parcial = destino.with_suffix(destino.suffix + ".part")
    total: int | None = None
    modificado = ""
    for intento in range(1, INTENTOS_DESCARGA + 1):
        desde = parcial.stat().st_size if parcial.exists() else 0
        cabeceras = {"Range": f"bytes={desde}-"} if desde else {}
        try:
            with abrir(url, timeout=600.0, cabeceras=cabeceras) as r:
                if desde and r.status != 206:
                    print("el servidor no acepta rangos; se baja desde el comienzo")
                    desde = 0
                total = largo_total(r, desde) or total
                modificado = modificado or r.headers.get("Last-Modified", "")
                with parcial.open("ab" if desde else "wb") as f:
                    shutil.copyfileobj(r, f, BLOQUE)
        except (OSError, http.client.HTTPException) as error:
            print(f"corte en el intento {intento}: {error}")
        tengo = parcial.stat().st_size if parcial.exists() else 0
        print(f"intento {intento}: {tengo} de {total if total is not None else 'largo no informado'} bytes")
        if total is not None and tengo == total:
            break
        if total is not None and tengo > total:
            parcial.unlink()
            raise caso_mod.CasoInvalido(f"{destino.name}: llegaron mas bytes ({tengo}) que los informados ({total})")
        if total is None and tengo and zipfile.is_zipfile(parcial):
            break
        time.sleep(ESPERA_S * intento)
    tengo = parcial.stat().st_size if parcial.exists() else 0
    if total is not None and tengo != total:
        raise caso_mod.CasoInvalido(
            f"{destino.name} incompleto: {tengo} de {total} bytes; vuelva a correr la tarea para seguir"
        )
    if not zipfile.is_zipfile(parcial):
        parcial.unlink()
        raise caso_mod.CasoInvalido(f"{destino.name} no es un zip valido; se borro el parcial")
    parcial.replace(destino)
    return {"ultima_modificacion_servidor": modificado, "metodo": "descarga por la tarea"}


def toml_texto(valor: object) -> str:
    return json.dumps(valor, ensure_ascii=False)


def escribir_procedencia(banco: Path, caso: Caso, entradas: list[dict[str, Any]]) -> None:
    ref = caso.referencia
    activacion = str(ref["activacion"])
    lineas = [
        "# Bank provenance. Original files are never edited; entries are only appended.",
        f"# Written by nadir-dano on {dt.date.today().isoformat()}.",
        "",
        "[fuente]",
        'organismo = "Copernicus Emergency Management Service (Comision Europea)"',
        f"conjunto = {toml_texto(f'{activacion}, incendios de Biobio y Nuble de enero de 2026, productos')}",
        f"fuente_pagina = {toml_texto(f'https://rapidmapping.emergency.copernicus.eu/{activacion}')}",
        'licencia = "Copernicus-EMS"',
        "atribucion = "
        + toml_texto(
            f"(c) European Union, 2026. Copernicus Emergency Management Service, {activacion}. Se cita; no se redistribuye"
        ),
        "",
    ]
    for e in entradas:
        lineas.append("[[archivo]]")
        lineas += [f"{k} = {toml_texto(v)}" for k, v in e.items()]
        lineas.append("")
    (banco / "procedencia.toml").write_text("\n".join(lineas), encoding="utf-8")


def asegurar_banco(caso: Caso) -> tuple[Path, dict[str, Any]]:
    """Deja en el banco el zip y la respuesta de la API, con procedencia. Devuelve el zip y esa respuesta."""
    ref = caso.referencia
    zip_ruta = caso.ruta("referencia_zip")
    banco = zip_ruta.parent
    procedencia = banco / "procedencia.toml"
    if procedencia.exists():
        registrados = {a["nombre"]: a for a in tomllib.loads(procedencia.read_text(encoding="utf-8"))["archivo"]}
        for nombre, a in registrados.items():
            h = sha256(banco / nombre)
            if h != a["sha256"]:
                raise caso_mod.CasoInvalido(f"huella de {nombre} en el banco distinta: {h}")
            print(f"verificado en el banco {nombre} {h}")
        api_nombre = next(n for n in registrados if n.startswith("api_"))
        return zip_ruta, json.loads((banco / api_nombre).read_text(encoding="utf-8"))

    banco.mkdir(parents=True, exist_ok=True)
    ahora = dt.datetime.now().astimezone().isoformat(timespec="seconds")
    url_api = str(ref["api"])
    with abrir(url_api, timeout=120.0) as r:
        crudo = r.read()
    api_nombre = f"api_{ref['activacion']}_{dt.date.today().isoformat()}.json"
    (banco / api_nombre).write_bytes(crudo)
    api = json.loads(crudo)
    url_zip = str(api["results"][0]["productsPath"])
    if Path(url_zip).name != zip_ruta.name:
        raise caso_mod.CasoInvalido(f"la API apunta a {url_zip}, no a {zip_ruta.name}")
    if zip_ruta.exists() and zipfile.is_zipfile(zip_ruta):
        print(f"{zip_ruta.name} ya esta en el banco sin procedencia (bajado a mano); se registra tal cual")
        extra = {"ultima_modificacion_servidor": "", "metodo": "descarga manual en el navegador"}
    else:
        if zip_ruta.exists():
            print(f"{zip_ruta.name} en el banco no es un zip valido; se descarta")
            zip_ruta.unlink()
        print(f"bajando {url_zip}")
        extra = bajar(url_zip, zip_ruta)
    entradas = [
        {
            "nombre": api_nombre,
            "url": url_api,
            "fecha_descarga": ahora,
            "bytes": (banco / api_nombre).stat().st_size,
            "sha256": sha256(banco / api_nombre),
        },
        {
            "nombre": zip_ruta.name,
            "url": url_zip,
            "ultima_modificacion_servidor": extra["ultima_modificacion_servidor"],
            "metodo": extra["metodo"],
            "fecha_descarga": ahora,
            "bytes": zip_ruta.stat().st_size,
            "sha256": sha256(zip_ruta),
        },
    ]
    escribir_procedencia(banco, caso, entradas)
    for e in entradas:
        print(f"registrado en el banco {e['nombre']} {e['sha256']} ({e['bytes']} bytes)")
    return zip_ruta, api


def capas_de(z: zipfile.ZipFile, interno: str, tmp: Path) -> dict[str, Path]:
    """Extrae un producto interno y devuelve sus capas vectoriales por nombre (sin prefijo ni version)."""
    destino = tmp / interno.removesuffix(".zip")
    destino.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(z.read(interno))) as zi:
        zi.extractall(destino)
    capas: dict[str, Path] = {}
    for shp in sorted(destino.rglob("*.shp")):
        capas[shp.stem] = shp
    return capas


def describir(g: gpd.GeoDataFrame, crs: str) -> dict[str, Any]:
    d: dict[str, Any] = {
        "elementos": len(g),
        "tipos_geometria": sorted({str(t) for t in g.geometry.geom_type.unique()}),
        "campos": [c for c in g.columns if c != "geometry"],
    }
    if len(g) and g.geometry.geom_type.isin(["Polygon", "MultiPolygon"]).all():
        d["hectareas"] = round(float(g.to_crs(crs).geometry.area.sum()) / 10_000, 1)
    if "damage_gra" in g.columns:
        d["damage_gra"] = {str(k): int(v) for k, v in g["damage_gra"].value_counts(dropna=False).items()}
    return d


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    carpeta_caso, trabajo = map(Path, sys.argv[1:])
    caso = caso_mod.cargar(carpeta_caso)
    salida = trabajo / "derivados" / "t03b"
    if (salida / "inspeccion_emsr859.json").exists():
        print("FALLO ya existe la inspeccion en la carpeta de trabajo; no se sobrescribe")
        return 1
    salida.mkdir(parents=True, exist_ok=True)
    print(f"== inicio {dt.datetime.now().isoformat(timespec='seconds')} caso {caso.nombre}")
    for linea in caso_mod.verificar_documentos(caso):
        print(linea)

    ref = caso.referencia
    activacion, aoi = str(ref["activacion"]), int(ref["aoi"])
    version_puntos = int(ref["version_puntos"])
    esperados = {str(k) for k in ref["valores_grado"]}
    zip_ruta, api = asegurar_banco(caso)

    informe: dict[str, Any] = {"zip": zip_ruta.name, "zip_sha256": sha256(zip_ruta), "productos_api": []}
    for a in api["results"][0]["aois"]:
        if int(a["number"]) == aoi:
            informe["area"] = {"numero": aoi, "nombre": a["name"]}
            for p in a["products"]:
                informe["productos_api"].append(
                    {
                        "tipo": p["type"],
                        "monitoreo": p["monitoringNumber"],
                        "version": p["version"]["number"],
                        "entrega": p["version"]["deliveryTime"],
                        "imagenes": [f"{i['sensorName']} {i['acquisitionTime']}" for i in p["images"]],
                    }
                )

    tmp = salida / "_tmp"
    prefijo = f"{activacion}_AOI{aoi:02d}_"
    with zipfile.ZipFile(zip_ruta) as z:
        nombres = sorted(set(z.namelist()))
        informe["productos_en_zip"] = [n for n in nombres if n.startswith(prefijo)]
        grado = [n for n in informe["productos_en_zip"] if "_GRA_PRODUCT_" in n]
        monit03 = [n for n in informe["productos_en_zip"] if "_DEL_MONIT03_" in n]
        capas: dict[str, Path] = {}
        for n in grado:
            capas.update(capas_de(z, n, tmp))
        capas_m03: dict[str, Path] = {}
        for n in monit03:
            capas_m03.update(capas_de(z, n, tmp))

    detalle: dict[str, Any] = {}
    for nombre, shp in capas.items():
        detalle[nombre] = describir(gpd.read_file(shp), caso.crs)
    informe["capas_producto_grado"] = detalle
    informe["capas_delineacion_monit03"] = {n: describir(gpd.read_file(s), caso.crs) for n, s in capas_m03.items()}

    clave_puntos = f"{prefijo}GRA_PRODUCT_builtUpP_v{version_puntos}"
    puntos = detalle.get(clave_puntos)
    motivos_1 = []
    if puntos is None:
        motivos_1.append(f"no esta la capa {clave_puntos}")
    elif "damage_gra" not in puntos:
        motivos_1.append("la capa de puntos no trae el campo damage_gra")
    else:
        presentes = set(puntos["damage_gra"])
        faltan = sorted(esperados - presentes)
        if faltan:
            motivos_1.append(f"damage_gra no trae los valores fijados {faltan}")
        informe["valores_no_fijados_en_puntos"] = sorted(presentes - esperados)
    areas = [d for n, d in detalle.items() if "_GRA_PRODUCT_builtUpA_" in n]
    con_grado = sum(v for d in areas for k, v in d.get("damage_gra", {}).items() if k in esperados)
    informe["deteccion_1"] = {"detener": bool(motivos_1), "motivos": motivos_1}
    informe["deteccion_2"] = {"detener": con_grado > 0, "elementos_builtUpA_con_grado": con_grado}
    informe["area_quemada_en_producto_grado"] = any("_GRA_PRODUCT_observedEventA_" in n for n in detalle)
    informe["area_interes_en_producto_grado"] = any("_GRA_PRODUCT_areaOfInterestA_" in n for n in detalle)
    informe["area_quemada_en_monit03"] = any("observedEventA" in n for n in capas_m03)

    shutil.rmtree(tmp, ignore_errors=True)
    texto = json.dumps(informe, ensure_ascii=False, indent=2)
    (salida / "inspeccion_emsr859.json").write_text(texto, encoding="utf-8")
    print(texto)
    print(f"huella inspeccion_emsr859.json {sha256(salida / 'inspeccion_emsr859.json')}")
    detener = informe["deteccion_1"]["detener"] or informe["deteccion_2"]["detener"]
    print("DETENCION: se escribe una enmienda antes de seguir" if detener else "SIN DETENCIONES")
    print("FIN OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
