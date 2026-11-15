"""Escribe README.md y README.en.md de un caso desde sus plantillas y sus informes.

Ninguna cifra de los README del caso se escribe a mano. Cada marca `{fuente:ruta|formato}` de
`<carpeta_caso>/plantillas/README.<idioma>.md` se reemplaza por el valor que esta en `ruta` dentro del
archivo `fuente`, declarado en `<carpeta_caso>/plantillas/fuentes.toml`:

- `ruta` son claves separadas por `/` (por ejemplo `penco/conjuntos/principal/huellas_centroide_en_quemado`);
  `@sha256` y `@bytes` dan la huella y el tamano del archivo fuente.
- `formato`: `ent` (entero con separador de miles), `pct1` o `pct2` (fraccion como porcentaje con 1 o 2
  decimales), `dec1` (un decimal con separador de miles), `fecha` (la primera fecha AAAA-MM-DD del texto,
  escrita "25 de enero de 2026" o "25 January 2026") y `txt` (tal cual, el valor por omision).

Con `--verificar` no escribe: comprueba que los README coincidan.

Uso: python scripts/escribir_readme_caso.py <carpeta_caso> [--verificar]
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import tomllib
from pathlib import Path
from typing import Any

FECHA = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
MESES = {
    "es": (
        "enero",
        "febrero",
        "marzo",
        "abril",
        "mayo",
        "junio",
        "julio",
        "agosto",
        "septiembre",
        "octubre",
        "noviembre",
        "diciembre",
    ),
    "en": (
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    ),
}
MARCA = re.compile(r"\{([a-z0-9_]+):([^|{}]+?)(?:\|([a-z0-9]+))?\}")
IDIOMAS = {"es": "README.md", "en": "README.en.md"}


def miles(entero: int, idioma: str) -> str:
    texto = f"{entero:,}"
    return texto.replace(",", ".") if idioma == "es" else texto


def decimal(valor: float, decimales: int, idioma: str) -> str:
    entero, _, fraccion = f"{valor:.{decimales}f}".partition(".")
    signo = "-" if entero.startswith("-") else ""
    cuerpo = miles(abs(int(entero)), idioma)
    sep = "," if idioma == "es" else "."
    return f"{signo}{cuerpo}{sep}{fraccion}" if fraccion else f"{signo}{cuerpo}"


def formatear(valor: Any, formato: str, idioma: str) -> str:
    if formato == "txt":
        return str(valor)
    if formato == "fecha":
        m = FECHA.search(str(valor))
        if m is None:
            raise ValueError(f"el formato fecha no encuentra una fecha AAAA-MM-DD en {valor!r}")
        anio, mes, dia = int(m.group(1)), int(m.group(2)), int(m.group(3))
        nombre = MESES[idioma][mes - 1]
        return f"{dia} de {nombre} de {anio}" if idioma == "es" else f"{dia} {nombre} {anio}"
    if isinstance(valor, bool) or not isinstance(valor, int | float):
        raise TypeError(f"el formato {formato} pide un numero y el valor es {valor!r}")
    if formato == "ent":
        if not float(valor).is_integer():
            raise ValueError(f"el formato ent pide un entero y el valor es {valor!r}")
        return miles(int(valor), idioma)
    if formato in ("pct1", "pct2"):
        texto = decimal(100 * float(valor), int(formato[-1]), idioma)
        return f"{texto} %" if idioma == "es" else f"{texto}%"
    if formato == "dec1":
        return decimal(float(valor), 1, idioma)
    raise ValueError(f"formato desconocido: {formato}")


def leer_fuentes(carpeta: Path) -> dict[str, tuple[Path, Any]]:
    declaradas = tomllib.loads((carpeta / "plantillas" / "fuentes.toml").read_text(encoding="utf-8"))
    fuentes: dict[str, tuple[Path, Any]] = {}
    for nombre, relativa in declaradas.items():
        ruta = carpeta / str(relativa)
        texto = ruta.read_text(encoding="utf-8")
        datos = tomllib.loads(texto) if ruta.suffix == ".toml" else json.loads(texto)
        fuentes[str(nombre)] = (ruta, datos)
    return fuentes


def valor(fuentes: dict[str, tuple[Path, Any]], fuente: str, ruta: str) -> Any:
    if fuente not in fuentes:
        raise KeyError(f"fuente no declarada en fuentes.toml: {fuente}")
    archivo, datos = fuentes[fuente]
    if ruta == "@sha256":
        return hashlib.sha256(archivo.read_bytes()).hexdigest()
    if ruta == "@bytes":
        return archivo.stat().st_size
    actual: Any = datos
    for clave in ruta.split("/"):
        if isinstance(actual, list):
            actual = actual[int(clave)]
        elif isinstance(actual, dict) and clave in actual:
            actual = actual[clave]
        else:
            raise KeyError(f"{fuente}: no existe la ruta {ruta}")
    return actual


def generar(carpeta: Path, idioma: str) -> str:
    fuentes = leer_fuentes(carpeta)
    plantilla = (carpeta / "plantillas" / f"README.{idioma}.md").read_text(encoding="utf-8")

    def poner(m: re.Match[str]) -> str:
        return formatear(valor(fuentes, m.group(1), m.group(2)), m.group(3) or "txt", idioma)

    texto = MARCA.sub(poner, plantilla)
    if re.search(r"\{[a-z0-9_]+:", texto):
        raise ValueError(f"quedo una marca sin reemplazar en la plantilla {idioma}")
    return texto


def main() -> int:
    argumentos = [a for a in sys.argv[1:] if a != "--verificar"]
    if len(argumentos) != 1:
        print(__doc__)
        return 2
    carpeta = Path(argumentos[0])
    verificar = "--verificar" in sys.argv[1:]
    fallas = 0
    for idioma, nombre in IDIOMAS.items():
        ruta = carpeta / nombre
        texto = generar(carpeta, idioma)
        if verificar:
            if not ruta.exists() or ruta.read_text(encoding="utf-8") != texto:
                print(f"FALLO {ruta.as_posix()} no coincide con la plantilla y los informes")
                fallas += 1
        else:
            ruta.write_text(texto, encoding="utf-8", newline="\n")
            print(f"escrito {ruta.as_posix()}")
    if fallas:
        return 1
    print("README del caso verificados" if verificar else "FIN OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
