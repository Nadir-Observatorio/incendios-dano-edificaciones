"""Escribe README.md y README.en.md desde las plantillas y resultados/resumen_sitio.json.

Ninguna cifra de los README se escribe a mano: cada `{clave}` de la plantilla se reemplaza por la cifra
de `resumen_sitio.json["cifras"]`. Con `--verificar` no escribe: comprueba que los README coincidan.

Uso: python scripts/escribir_readme.py [--verificar]
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parents[1]


def formato(valor: Any, idioma: str, porcentaje: bool) -> str:
    if isinstance(valor, bool) or valor is None:
        return str(valor)
    if isinstance(valor, int):
        texto = f"{valor:,}"
        return texto.replace(",", ".") if idioma == "es" else texto
    if porcentaje:
        texto = f"{100 * float(valor):.1f}"
        return f"{texto.replace('.', ',')} %" if idioma == "es" else f"{texto}%"
    texto = f"{float(valor):.2f}"
    return texto.replace(".", ",") if idioma == "es" else texto


def reemplazos(cifras: dict[str, Any], idioma: str) -> dict[str, str]:
    salida: dict[str, str] = {}
    for clave, c in cifras.items():
        v = c["valor"]
        es_pct = isinstance(v, float) and 0.0 <= abs(v) <= 1.0 and not clave.startswith(("auc", "umbral"))
        salida[clave] = formato(v, idioma, es_pct)
        if "suma" in clave:  # diferencia en puntos porcentuales, sin signo de porcentaje
            salida[clave] = salida[clave].replace(" %", "").replace("%", "")
        if "ic95" in c:
            a, b = (formato(x, idioma, es_pct).replace(" %", "").replace("%", "") for x in c["ic95"])
            salida[f"{clave}_ic"] = f"[{a}; {b}]" if idioma == "es" else f"[{a}, {b}]"
    return salida


def generar(idioma: str) -> str:
    resumen = json.loads((RAIZ / "resultados" / "resumen_sitio.json").read_text(encoding="utf-8"))
    plantilla = (RAIZ / "plantillas" / f"README.{idioma}.md").read_text(encoding="utf-8")
    valores = reemplazos(resumen["cifras"], idioma)

    def poner(m: re.Match[str]) -> str:
        clave = m.group(1)
        if clave not in valores:
            raise KeyError(f"la plantilla {idioma} pide una cifra que no existe: {clave}")
        return valores[clave]

    return re.sub(r"\{([a-z0-9_]+)\}", poner, plantilla)


def main() -> int:
    verificar = "--verificar" in sys.argv[1:]
    destinos = {"es": RAIZ / "README.md", "en": RAIZ / "README.en.md"}
    fallas = 0
    for idioma, ruta in destinos.items():
        texto = generar(idioma)
        if verificar:
            if not ruta.exists() or ruta.read_text(encoding="utf-8") != texto:
                print(f"FALLO {ruta.name} no coincide con la plantilla y las cifras")
                fallas += 1
        else:
            ruta.write_text(texto, encoding="utf-8", newline="\n")
            print(f"escrito {ruta.name}")
    if fallas:
        return 1
    print("README verificados" if verificar else "FIN OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
