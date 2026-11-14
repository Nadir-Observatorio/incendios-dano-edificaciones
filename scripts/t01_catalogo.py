"""Tarea 01 del caso de dano a edificaciones (etapa E1).

Solo metadatos: consulta el catalogo de rafagas Sentinel-1 de ASF sobre el area de EMSN188 con un
margen, y comprueba la existencia y el tamano de la tesela de Google Open Buildings que la cubre.
No descarga imagenes ni calcula resultados. Verifica ademas la huella de la referencia EMSN188
que usa la Etapa 1 (solo lectura).

Uso: python t01_catalogo.py <carpeta_salida> <zip_emsn188>
"""

from __future__ import annotations

import csv
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import asf_search as asf
import requests
import s2sphere

# Caja del area analizada por EMSN188 (P00_aoi, "Las Tablas") con unos 5 km de margen, EPSG:4326.
OESTE, SUR, ESTE, NORTE = -71.60, -33.13, -71.38, -32.94
INICIO = "2023-10-01T00:00:00Z"
FIN = "2024-03-31T23:59:59Z"

EMSN188_SHA256 = "443e7c353f392c56124004a9ae3b2dfc1dbb1af26d9fd0fef31f610cb5dafed3"

GOB_URL = "https://storage.googleapis.com/open-buildings-data/v3/polygons_s2_level_4_gzip/{token}_buildings.csv.gz"


def wkt_caja() -> str:
    return f"POLYGON(({OESTE} {SUR},{ESTE} {SUR},{ESTE} {NORTE},{OESTE} {NORTE},{OESTE} {SUR}))"


def sha256(ruta: Path) -> str:
    h = hashlib.sha256()
    with ruta.open("rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def plano(props: dict[str, Any]) -> dict[str, Any]:
    """Aplana el diccionario de propiedades de un producto de rafaga."""
    rafaga = props.get("burst") or {}
    return {
        "sceneName": props.get("sceneName"),
        "fileID": props.get("fileID"),
        "startTime": props.get("startTime"),
        "platform": props.get("platform"),
        "flightDirection": props.get("flightDirection"),
        "pathNumber": props.get("pathNumber"),
        "polarization": props.get("polarization"),
        "fullBurstID": rafaga.get("fullBurstID"),
        "relativeBurstID": rafaga.get("relativeBurstID"),
        "subswath": rafaga.get("subswath"),
        "burstIndex": rafaga.get("burstIndex"),
    }


def catalogo(salida: Path) -> list[str]:
    lineas: list[str] = []
    resultados = asf.search(
        dataset=asf.DATASET.SLC_BURST,
        intersectsWith=wkt_caja(),
        start=INICIO,
        end=FIN,
    )
    filas = [plano(dict(p.properties)) for p in resultados]
    lineas.append(f"rafagas encontradas: {len(filas)}")

    with (salida / "rafagas.jsonl").open("w", encoding="utf-8") as f:
        for p in resultados:
            f.write(json.dumps(dict(p.properties), ensure_ascii=False, default=str) + "\n")

    campos = list(filas[0].keys()) if filas else list(plano({}).keys())
    with (salida / "catalogo_rafagas.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        for fila in sorted(filas, key=lambda x: (str(x["fullBurstID"]), str(x["startTime"]))):
            w.writerow(fila)

    # Resumen: por geometria y rafaga, fechas disponibles (VV) y plataforma.
    por_rafaga: dict[tuple[str, str, str], list[str]] = defaultdict(list)
    plataformas: set[str] = set()
    for fila in filas:
        plataformas.add(str(fila["platform"]))
        if fila["polarization"] not in ("VV", None):
            continue
        clave = (str(fila["flightDirection"]), str(fila["pathNumber"]), str(fila["fullBurstID"]))
        por_rafaga[clave].append(str(fila["startTime"])[:10])
    lineas.append(f"plataformas: {sorted(plataformas)}")
    for (direccion, orbita, rafaga), fechas in sorted(por_rafaga.items()):
        fechas = sorted(set(fechas))
        lineas.append(f"{direccion} orbita {orbita} rafaga {rafaga}: {len(fechas)} fechas")
        lineas.append("    " + " ".join(fechas))
    return lineas


def teselas_open_buildings() -> list[str]:
    lineas: list[str] = []
    tokens: set[str] = set()
    for lat in (SUR, (SUR + NORTE) / 2, NORTE):
        for lon in (OESTE, (OESTE + ESTE) / 2, ESTE):
            celda = s2sphere.CellId.from_lat_lng(s2sphere.LatLng.from_degrees(lat, lon))
            tokens.add(celda.parent(4).to_token())
    for token in sorted(tokens):
        url = GOB_URL.format(token=token)
        try:
            r = requests.head(url, timeout=60, allow_redirects=True)
            lineas.append(
                f"tesela S2 nivel 4 {token}: HTTP {r.status_code}, "
                f"bytes {r.headers.get('Content-Length')}, "
                f"modificado {r.headers.get('Last-Modified')}, url {url}"
            )
        except requests.RequestException as e:
            lineas.append(f"tesela S2 nivel 4 {token}: ERROR {e!r}, url {url}")
    return lineas


def main() -> int:
    if len(sys.argv) != 3:
        print("uso: python t01_catalogo.py <carpeta_salida> <zip_emsn188>")
        return 2
    salida = Path(sys.argv[1])
    emsn188_zip = Path(sys.argv[2])
    salida.mkdir(parents=True, exist_ok=True)
    informe: list[str] = []

    informe.append("== 1. Referencia EMSN188 (solo lectura)")
    if emsn188_zip.exists():
        h = sha256(emsn188_zip)
        estado = "COINCIDE" if h == EMSN188_SHA256 else "NO COINCIDE"
        informe.append(f"{emsn188_zip} sha256 {h} {estado} con metricas.json de la Etapa 1")
    else:
        informe.append(f"NO EXISTE {emsn188_zip}")

    informe.append("== 2. Catalogo de rafagas Sentinel-1 (ASF, solo metadatos)")
    try:
        informe.extend(catalogo(salida))
    except Exception as e:  # el informe debe salir aunque falle la red
        informe.append(f"ERROR catalogo: {e!r}")

    informe.append("== 3. Google Open Buildings, teselas que cubren la caja (solo cabeceras)")
    try:
        informe.extend(teselas_open_buildings())
    except Exception as e:
        informe.append(f"ERROR teselas: {e!r}")

    texto = "\n".join(informe)
    (salida / "resumen_t01.txt").write_text(texto + "\n", encoding="utf-8")
    print(texto)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
