"""Lectura de la configuracion de un caso de dano a edificaciones.

Cada caso vive en `casos/<caso>/` con dos archivos:

- `caso.toml`: los parametros del metodo fijados en su protocolo sellado (caja, sistema de coordenadas,
  semilla, orbitas, grados de la referencia, textos del sitio). Es publicable.
- `rutas.toml`: rutas locales a los insumos del banco. No se publica.

Ninguna tarea tiene parametros de un caso escritos en su codigo: todos salen de aqui. Las huellas que
encadenan las tareas (particion, senales, metricas) se registran en `[fijadas]` de `caso.toml` a medida
que cada etapa termina, y la tarea siguiente se detiene si falta la huella o no calza.
"""

from __future__ import annotations

import hashlib
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DIRECCIONES = ("asc", "des")
MODOS_P5 = ("fuera_zona", "centro_celda")


class CasoInvalido(ValueError):
    """La configuracion del caso no cumple lo que las tareas necesitan."""


@dataclass(frozen=True)
class Documento:
    """Protocolo sellado o enmienda, con la huella que debe tener en disco."""

    clave: str
    archivo: str
    sha256: str
    en_resumen_t04: bool


@dataclass(frozen=True)
class Orbita:
    """Orbita relativa usada en el caso. `id` es el valor del campo `geometria` en la procedencia del banco."""

    id: str
    direccion: str
    grupo: str


@dataclass(frozen=True)
class Caso:
    nombre: str
    carpeta: Path
    caja: tuple[float, float, float, float]
    crs: str
    semilla: int
    conjuntos: dict[str, float]
    radio_empareje_m: float
    control_dist_m: float
    teselas: list[str]
    grados: dict[int, str]
    documentos: list[Documento]
    orbitas: list[Orbita]
    senales: list[str]
    referencia: dict[str, Any]
    columna_clase: str
    p5_modo: str
    fijadas: dict[str, str]
    sitio: dict[str, Any]
    rutas: dict[str, Path] = field(default_factory=dict)

    @property
    def grupos(self) -> dict[str, list[str]]:
        """Grupo de geometria (asc, des) a sus orbitas, en el orden del archivo."""
        salida: dict[str, list[str]] = {}
        for o in self.orbitas:
            salida.setdefault(o.grupo, []).append(o.id)
        return salida

    def ruta(self, clave: str) -> Path:
        if clave not in self.rutas:
            raise CasoInvalido(f"falta la ruta '{clave}' en rutas.toml de {self.nombre}")
        return self.rutas[clave]

    def fijada(self, clave: str) -> str:
        valor = self.fijadas.get(clave, "")
        if not valor:
            raise CasoInvalido(
                f"falta la huella fijada '{clave}' en caso.toml de {self.nombre}; la etapa anterior no se ha cerrado"
            )
        return valor

    def documento_ruta(self, doc: Documento) -> Path:
        return self.ruta("protocolo") / doc.archivo


def sha256(ruta: Path) -> str:
    h = hashlib.sha256()
    with ruta.open("rb") as f:
        for bloque in iter(lambda: f.read(1 << 22), b""):
            h.update(bloque)
    return h.hexdigest()


def _tabla(datos: dict[str, Any], clave: str) -> dict[str, Any]:
    valor = datos.get(clave)
    if not isinstance(valor, dict):
        raise CasoInvalido(f"falta la tabla [{clave}]")
    return valor


def cargar(carpeta: Path, con_rutas: bool = True) -> Caso:
    """Lee `caso.toml` (y `rutas.toml` si `con_rutas`) y valida lo que las tareas usan."""
    carpeta = Path(carpeta)
    datos = tomllib.loads((carpeta / "caso.toml").read_text(encoding="utf-8"))
    metodo = _tabla(datos, "metodo")
    caja = metodo["caja"]
    if len(caja) != 4 or not (caja[0] < caja[2] and caja[1] < caja[3]):
        raise CasoInvalido("caja debe ser [oeste, sur, este, norte] con oeste < este y sur < norte")
    documentos = [
        Documento(
            clave=str(d["clave"]),
            archivo=str(d["archivo"]),
            sha256=str(d["sha256"]),
            en_resumen_t04=bool(d.get("en_resumen_t04", False)),
        )
        for d in datos.get("documento", [])
    ]
    if not documentos or documentos[0].clave != "protocolo":
        raise CasoInvalido("el primer [[documento]] debe ser el protocolo sellado")
    orbitas = [Orbita(str(o["id"]), str(o["direccion"]), str(o["grupo"])) for o in datos.get("orbita", [])]
    if not orbitas:
        raise CasoInvalido("falta al menos una [[orbita]]")
    for o in orbitas:
        if o.direccion not in DIRECCIONES or o.grupo not in DIRECCIONES:
            raise CasoInvalido(f"orbita {o.id}: direccion y grupo deben ser 'asc' o 'des'")
    if len({o.id for o in orbitas}) != len(orbitas):
        raise CasoInvalido("ids de orbita repetidos")
    grupos = {o.grupo for o in orbitas}
    if grupos != set(DIRECCIONES):
        raise CasoInvalido("el caso necesita orbitas de los grupos 'asc' y 'des'")
    p5 = _tabla(datos, "p5")
    if p5["modo"] not in MODOS_P5:
        raise CasoInvalido(f"p5.modo debe ser uno de {MODOS_P5}")
    rutas: dict[str, Path] = {}
    if con_rutas:
        crudas = tomllib.loads((carpeta / "rutas.toml").read_text(encoding="utf-8"))
        rutas = {str(k): Path(str(v)) for k, v in crudas.items()}
    return Caso(
        nombre=str(datos["nombre"]),
        carpeta=carpeta,
        caja=(float(caja[0]), float(caja[1]), float(caja[2]), float(caja[3])),
        crs=str(metodo["crs"]),
        semilla=int(metodo["semilla"]),
        conjuntos={str(k): float(v) for k, v in _tabla(metodo, "conjuntos").items()},
        radio_empareje_m=float(metodo["radio_empareje_m"]),
        control_dist_m=float(metodo["control_dist_m"]),
        teselas=[str(t) for t in metodo["teselas_open_buildings"]],
        grados={int(k): str(v) for k, v in _tabla(datos, "grados").items()},
        documentos=documentos,
        orbitas=orbitas,
        senales=[str(s) for s in metodo["senales"]],
        referencia=_tabla(datos, "referencia"),
        columna_clase=str(metodo["columna_clase_optica"]),
        p5_modo=str(p5["modo"]),
        fijadas={str(k): str(v) for k, v in datos.get("fijadas", {}).items()},
        sitio=datos.get("sitio", {}),
        rutas=rutas,
    )


def verificar_documentos(caso: Caso, claves: list[str] | None = None) -> list[str]:
    """Comprueba las huellas del protocolo y las enmiendas. Devuelve lineas para el registro; lanza si no calza."""
    lineas = []
    for doc in caso.documentos:
        if claves is not None and doc.clave not in claves:
            continue
        h = sha256(caso.documento_ruta(doc))
        if h != doc.sha256:
            raise CasoInvalido(f"huella de {doc.archivo} distinta: {h}")
        lineas.append(f"verificado {doc.archivo} {h}")
    return lineas
