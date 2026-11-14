"""Tarea 03 del caso de dano a edificaciones (etapa E3).

Baja al banco las dos teselas oficiales de Google Open Buildings que cubren el area (S2 nivel 4,
967 y 969), con su huella y procedencia. No recorta ni calcula nada. Se puede correr de nuevo:
salta lo que ya esta registrado.

Uso: python t03_open_buildings.py <carpeta_banco>
"""

from __future__ import annotations

import datetime as dt
import hashlib
import sys
from pathlib import Path

import requests

URL = "https://storage.googleapis.com/open-buildings-data/v3/polygons_s2_level_4_gzip/{t}_buildings.csv.gz"
TESELAS = ["967", "969"]


def sha256(ruta: Path) -> str:
    h = hashlib.sha256()
    with ruta.open("rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def main() -> int:
    if len(sys.argv) != 2:
        print("uso: python t03_open_buildings.py <carpeta_banco>")
        return 2
    banco = Path(sys.argv[1])
    banco.mkdir(parents=True, exist_ok=True)
    procedencia = banco / "procedencia.toml"
    if not procedencia.exists():
        procedencia.write_text(
            "# Bank provenance. Original files are never edited; entries are only appended.\n"
            f"# Written by nadir-dano on {dt.date.today().isoformat()}.\n\n"
            "[fuente]\n"
            'organismo = "Google Research, Open Buildings"\n'
            'conjunto = "Open Buildings, poligonos por celda S2 de nivel 4 (inferencia de mayo de 2023)"\n'
            'fuente_pagina = "https://sites.research.google/open-buildings/"\n'
            'licencia = "CC-BY-4.0"\n'
            'licencia_nota = "Google ofrece CC BY 4.0 u ODbL 1.0 a eleccion; Nadir usa CC BY 4.0 (DE-2a)"\n'
            'atribucion = "Google Open Buildings (Sirko et al. 2021), CC BY 4.0"\n',
            encoding="utf-8",
        )
    texto = procedencia.read_text(encoding="utf-8")
    for t in TESELAS:
        nombre = f"{t}_buildings.csv.gz"
        destino = banco / nombre
        if f'nombre = "{nombre}"' in texto and destino.exists():
            print(f"ya registrado {nombre}")
            continue
        url = URL.format(t=t)
        parcial = destino.with_suffix(destino.suffix + ".part")
        with requests.get(url, stream=True, timeout=120) as r:
            r.raise_for_status()
            esperado = int(r.headers.get("Content-Length", "0"))
            modificado = r.headers.get("Last-Modified", "")
            with parcial.open("wb") as f:
                for bloque in r.iter_content(chunk_size=1 << 20):
                    f.write(bloque)
        tam = parcial.stat().st_size
        if esperado and tam != esperado:
            print(f"FALLO tamano {nombre}: {tam} de {esperado}")
            return 1
        parcial.replace(destino)
        entrada = (
            "\n[[archivo]]\n"
            f'nombre = "{nombre}"\n'
            f'url = "{url}"\n'
            f'ultima_modificacion_servidor = "{modificado}"\n'
            f'fecha_descarga = "{dt.datetime.now().astimezone().isoformat(timespec="seconds")}"\n'
            f"bytes = {tam}\n"
            f'sha256 = "{sha256(destino)}"\n'
        )
        with procedencia.open("a", encoding="utf-8") as f:
            f.write(entrada)
        texto += entrada
        print(f"bajado {nombre} {tam} bytes")
    print("FIN OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
