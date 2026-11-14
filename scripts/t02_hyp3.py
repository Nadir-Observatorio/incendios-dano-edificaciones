"""Tarea 02 del caso de dano a edificaciones (etapa E2).

Pide a HyP3 Basic los 56 pares de rafaga fijados en la seccion 3 del protocolo sellado, espera a que
terminen y baja cada producto al banco con su procedencia. Es interactiva: pide usuario y contrasena
de Earthdata en la consola (no se guardan) y una confirmacion escrita antes de enviar.

Se puede correr de nuevo sin riesgo: no vuelve a pedir pares que ya existen con el mismo nombre de
proyecto, y no vuelve a bajar productos que ya estan en el banco con su huella.

Uso: python t02_hyp3.py <carpeta_caso> <carpeta_banco> <archivo_log>
"""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import hyp3_sdk as sdk

PROYECTO = "nadir-dano-vina2024"
LOOKS = "5x1"
PROTOCOLO = "PROTOCOLO_dano-edificaciones_sellado_2026-11-11.md"
PROTOCOLO_SHA256 = "de1993790a4e7485aeef3d64749a490dd735679feb5575263bc61ca727387f5d"

RAFAGAS_ASC = ["018_038457_IW1", "018_038457_IW2", "018_038458_IW1", "018_038458_IW2"]
PARES_ASC = [
    ("previo1", "2023-11-12", "2023-11-24"),
    ("previo2", "2023-11-24", "2023-12-06"),
    ("previo3", "2023-12-06", "2023-12-18"),
    ("previo4", "2023-12-18", "2023-12-30"),
    ("previo5", "2023-12-30", "2024-01-11"),
    ("previo6", "2024-01-11", "2024-01-23"),
    ("evento", "2024-01-23", "2024-02-04"),
    ("posterior", "2024-02-04", "2024-02-16"),
]
RAFAGAS_DES = ["156_334205_IW2", "156_334206_IW2", "156_334207_IW2"]
PARES_DES = [
    ("previo1", "2023-11-22", "2023-12-04"),
    ("previo2", "2023-12-04", "2023-12-16"),
    ("previo3", "2023-12-16", "2023-12-28"),
    ("previo4", "2023-12-28", "2024-01-09"),
    ("previo5", "2024-01-09", "2024-01-21"),
    ("previo6", "2024-01-21", "2024-02-02"),
    ("evento", "2024-02-02", "2024-02-14"),
    ("posterior", "2024-02-14", "2024-02-26"),
]

LOG: Path | None = None


def log(texto: str) -> None:
    print(texto, flush=True)
    if LOG is not None:
        with LOG.open("a", encoding="utf-8") as f:
            f.write(texto + "\n")


def sha256(ruta: Path) -> str:
    h = hashlib.sha256()
    with ruta.open("rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def escenas_vv(catalogo: Path) -> dict[tuple[str, str], str]:
    """(rafaga, fecha) -> nombre de la escena de rafaga VV."""
    salida: dict[tuple[str, str], str] = {}
    with catalogo.open(encoding="utf-8") as f:
        for fila in csv.DictReader(f):
            if fila["polarization"] == "VV":
                salida[(fila["fullBurstID"], fila["startTime"][:10])] = fila["sceneName"]
    return salida


def plan(escenas: dict[tuple[str, str], str]) -> tuple[list[dict[str, str]], list[str]]:
    pares: list[dict[str, str]] = []
    faltan: list[str] = []
    for geometria, rafagas, tabla in (("asc", RAFAGAS_ASC, PARES_ASC), ("des", RAFAGAS_DES, PARES_DES)):
        for rafaga in rafagas:
            for rol, ref, sec in tabla:
                g1 = escenas.get((rafaga, ref))
                g2 = escenas.get((rafaga, sec))
                if g1 is None or g2 is None:
                    faltan.append(f"{geometria} {rafaga} {rol} {ref} {sec}")
                    continue
                pares.append(
                    {
                        "geometria": geometria,
                        "rafaga": rafaga,
                        "rol": rol,
                        "referencia": ref,
                        "secundaria": sec,
                        "granule1": g1,
                        "granule2": g2,
                    }
                )
    return pares, faltan


def conectar() -> sdk.HyP3:
    try:
        return sdk.HyP3(prompt="password")
    except (TypeError, ValueError):
        return sdk.HyP3(prompt=True)


def granulos(job: Any) -> tuple[str, str]:
    g = list((job.job_parameters or {}).get("granules", []))
    if len(g) == 2:
        return str(g[0]), str(g[1])
    g1 = (job.job_parameters or {}).get("reference", [""])
    g2 = (job.job_parameters or {}).get("secondary", [""])
    return str(g1[0] if isinstance(g1, list) else g1), str(g2[0] if isinstance(g2, list) else g2)


def asegurar_procedencia(banco: Path) -> Path:
    ruta = banco / "procedencia.toml"
    if not ruta.exists():
        ruta.write_text(
            "# Bank provenance. Original files are never edited; entries are only appended.\n"
            f"# Written by nadir-dano on {dt.date.today().isoformat()}.\n\n"
            "[fuente]\n"
            'organismo = "NASA Alaska Satellite Facility DAAC, HyP3 Basic (procesamiento a pedido)"\n'
            'conjunto = "Sentinel-1A, InSAR por rafaga con ISCE2 (INSAR_ISCE_BURST), 5x1 looks, VV; '
            'incendio de Vina del Mar, febrero de 2024"\n'
            'fuente_pagina = "https://hyp3-docs.asf.alaska.edu/"\n'
            'licencia = "Copernicus-Sentinel"\n'
            'atribucion = "Contains modified Copernicus Sentinel data 2023-2024, processed by ESA. '
            'InSAR product processed by ASF DAAC HyP3 using ISCE2 (cita exacta en el README de cada producto)"\n',
            encoding="utf-8",
        )
    return ruta


def registrados(procedencia: Path) -> set[str]:
    texto = procedencia.read_text(encoding="utf-8")
    return {linea.split('"')[1] for linea in texto.splitlines() if linea.startswith("nombre = ")}


def main() -> int:
    global LOG
    if len(sys.argv) != 4:
        print("uso: python t02_hyp3.py <carpeta_caso> <carpeta_banco> <archivo_log>")
        return 2
    caso, banco, LOG = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    log(f"== inicio {dt.datetime.now().isoformat(timespec='seconds')}")

    h = sha256(caso / PROTOCOLO)
    if h != PROTOCOLO_SHA256:
        log(f"FALLO el protocolo sellado no coincide: {h}")
        return 1
    log(f"protocolo sellado verificado {h}")

    pares, faltan = plan(escenas_vv(caso / "catalogo" / "catalogo_rafagas.csv"))
    log(f"pares del protocolo con escenas en el catalogo: {len(pares)}")
    for f in faltan:
        log(f"OMITIDO (falta fecha en el catalogo): {f}")

    hyp3 = conectar()
    log(f"creditos disponibles: {hyp3.check_credits()}")

    previos = hyp3.find_jobs(name=PROYECTO)
    ya = {granulos(j): j for j in previos}
    nuevos = [p for p in pares if (p["granule1"], p["granule2"]) not in ya]
    log(f"trabajos ya pedidos con este nombre: {len(ya)}; por pedir: {len(nuevos)}")

    if nuevos:
        respuesta = input(f"Escriba SI para enviar {len(nuevos)} trabajos a HyP3: ").strip()
        if respuesta != "SI":
            log("no se envio nada (sin confirmacion)")
            return 1
        for p in nuevos:
            hyp3.submit_insar_isce_burst_job(
                p["granule1"], p["granule2"], apply_water_mask=False, name=PROYECTO, looks=LOOKS
            )
        log(f"enviados {len(nuevos)}")

    lote = hyp3.find_jobs(name=PROYECTO)
    registro = []
    por_granulos = {(p["granule1"], p["granule2"]): p for p in pares}
    for j in lote:
        p = por_granulos.get(granulos(j), {})
        registro.append({**p, "job_id": j.job_id, "estado": j.status_code})
    (caso / "catalogo" / "pedidos_hyp3.json").write_text(
        json.dumps(registro, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    log("esperando a HyP3 (hasta 3 horas; se puede cerrar y volver a correr la tarea)")
    try:
        lote = hyp3.watch(lote, timeout=10800, interval=60)
    except Exception as e:  # tiempo agotado u otra demora: se baja lo que este listo
        log(f"espera interrumpida: {e!r}")
        lote = hyp3.find_jobs(name=PROYECTO)

    banco.mkdir(parents=True, exist_ok=True)
    procedencia = asegurar_procedencia(banco)
    hechos = registrados(procedencia)
    exitosos = fallidos = pendientes = bajados = 0
    for j in lote:
        if j.status_code == "FAILED":
            fallidos += 1
            log(f"FALLIDO {j.job_id} {granulos(j)}")
            continue
        if j.status_code != "SUCCEEDED":
            pendientes += 1
            continue
        exitosos += 1
        for archivo in j.files or []:
            nombre = archivo["filename"]
            if nombre in hechos and (banco / nombre).exists():
                continue
            rutas = j.download_files(banco)
            for ruta in rutas:
                ruta = Path(ruta)
                if ruta.name in hechos:
                    continue
                p = por_granulos.get(granulos(j), {})
                entrada = (
                    "\n[[archivo]]\n"
                    f'nombre = "{ruta.name}"\n'
                    f'job_id = "{j.job_id}"\n'
                    f'geometria = "{p.get("geometria", "")}"\n'
                    f'rafaga = "{p.get("rafaga", "")}"\n'
                    f'rol = "{p.get("rol", "")}"\n'
                    f'referencia = "{granulos(j)[0]}"\n'
                    f'secundaria = "{granulos(j)[1]}"\n'
                    f'url = "{archivo.get("url", "")}"\n'
                    f'fecha_descarga = "{dt.datetime.now().astimezone().isoformat(timespec="seconds")}"\n'
                    f"bytes = {ruta.stat().st_size}\n"
                    f'sha256 = "{sha256(ruta)}"\n'
                )
                with procedencia.open("a", encoding="utf-8") as fh:
                    fh.write(entrada)
                hechos.add(ruta.name)
                bajados += 1
                log(f"bajado {ruta.name}")
    log(f"exitosos {exitosos}, fallidos {fallidos}, pendientes {pendientes}, bajados ahora {bajados}")
    log(f"creditos disponibles: {hyp3.check_credits()}")
    if pendientes:
        log("QUEDAN PENDIENTES: vuelva a correr la tarea mas tarde (los productos duran 14 dias)")
        return 0
    log("FIN OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
