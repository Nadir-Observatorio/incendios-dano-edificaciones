"""Pruebas de las funciones de las que dependen las cifras publicadas."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import geopandas as gpd
import numpy as np
import pytest
import shapely
from rasterio.transform import from_origin

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def cargar(nombre: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(nombre, SCRIPTS / f"{nombre}.py")
    assert spec is not None
    assert spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[nombre] = modulo
    spec.loader.exec_module(modulo)
    return modulo


t04 = cargar("t04_huellas_particion")
t05 = cargar("t05_senales")
t06 = cargar("t06_evaluacion")


def ladera(pendiente_grados: float) -> np.ndarray:
    """Plano que sube hacia el este con la pendiente dada, en una grilla de 20 m."""
    x = np.arange(50) * 20.0
    return np.tile(np.tan(np.radians(pendiente_grados)) * x, (50, 1)).astype("float32")


def test_mascara_inversion_si_la_ladera_mira_al_satelite() -> None:
    elevacion = np.full((50, 50), 51.0)  # incidencia de 39 grados
    valido, pendiente = t05.mascara_geometria(elevacion, np.zeros((50, 50)), ladera(50), "des", [])
    assert not valido[5:-5, 5:-5].any()
    assert pendiente[25, 25] == pytest.approx(50.0, abs=0.01)


def test_mascara_valida_y_sombra_si_la_ladera_da_la_espalda() -> None:
    elevacion = np.full((50, 50), 51.0)
    hacia_oeste = np.full((50, 50), 180.0)
    valido_50, _ = t05.mascara_geometria(elevacion, hacia_oeste, ladera(50), "asc", [])
    valido_60, _ = t05.mascara_geometria(elevacion, hacia_oeste, ladera(60), "asc", [])
    assert valido_50[5:-5, 5:-5].all()
    assert not valido_60[5:-5, 5:-5].any()


def test_mascara_convenciones_en_radianes_y_azimut_opuesto() -> None:
    registro: list[str] = []
    elevacion = np.full((50, 50), np.radians(51.0))
    opuesto = np.full((50, 50), np.radians(0.0))  # en ascendente se espera cerca de 180
    valido, _ = t05.mascara_geometria(elevacion, opuesto, ladera(0), "asc", registro)
    assert valido[5:-5, 5:-5].all()
    assert "radianes" in registro[0]
    assert "se suma 180" in registro[0]


def test_mascara_se_detiene_si_el_azimut_no_calza() -> None:
    with pytest.raises(ValueError, match="no calza"):
        t05.mascara_geometria(np.full((5, 5), 51.0), np.full((5, 5), 90.0), ladera(0)[:5, :5], "des", [])


def test_ponderacion_por_area_exacta() -> None:
    transform = from_origin(0, 100, 20, 20)
    valores = np.zeros((5, 5), dtype="float32")
    valores[0, 0], valores[0, 1], valores[1, 0], valores[1, 1] = 1, 2, 3, 4
    huella = np.array([shapely.box(10, 70, 30, 90)])
    tabla = t05.ponderar(huella, transform, (5, 5), {"v": valores}, {"v": np.ones((5, 5), bool)})
    assert tabla.loc[0, "v"] == pytest.approx(2.5)
    assert tabla.loc[0, "frac_v"] == pytest.approx(1.0)


def test_ponderacion_respeta_la_mascara() -> None:
    transform = from_origin(0, 100, 20, 20)
    valores = np.ones((5, 5), dtype="float32")
    valores[0, 0] = 9.0
    mascara = np.ones((5, 5), bool)
    mascara[0, 0] = False
    huella = np.array([shapely.box(10, 70, 30, 90)])
    tabla = t05.ponderar(huella, transform, (5, 5), {"v": valores}, {"v": mascara})
    assert tabla.loc[0, "v"] == pytest.approx(1.0)
    assert tabla.loc[0, "frac_v"] == pytest.approx(0.75)


def auc_por_pares(s: np.ndarray, y: np.ndarray, w: np.ndarray) -> float:
    pos, neg = y == 1, y == 0
    dif = s[pos][:, None] - s[neg][None, :]
    peso = w[pos][:, None] * w[neg][None, :]
    return float(((dif > 0) * peso + 0.5 * (dif == 0) * peso).sum() / peso.sum())


def test_auc_ponderada_igual_a_la_definicion_por_pares() -> None:
    rng = np.random.default_rng(1)
    y = (rng.random(400) < 0.3).astype(float)
    s = np.round(rng.normal(size=400) + y, 1)  # con empates
    w = rng.integers(0, 4, 400).astype(float)
    assert t06.auc_ponderada(s, y, w) == pytest.approx(auc_por_pares(s, y, w))
    assert t06.auc_ponderada(s, y, np.ones(400)) == pytest.approx(auc_por_pares(s, y, np.ones(400)))


def test_precision_promedio_casos_extremos() -> None:
    y = np.array([1.0, 1.0, 0.0, 0.0])
    assert t06.ap_ponderada(np.array([4.0, 3.0, 2.0, 1.0]), y, np.ones(4)) == pytest.approx(1.0)
    assert t06.ap_ponderada(np.array([1.0, 2.0, 3.0, 4.0]), y, np.ones(4)) == pytest.approx((1 / 3 + 2 / 4) / 2)


def test_particion_reproducible_y_mitades_por_estrato() -> None:
    celdas = [f"88{i:013x}" for i in range(40)]
    huellas = gpd.GeoDataFrame({"h3_r8": celdas[:30]}, geometry=[shapely.Point(0, 0)] * 30)
    puntos = gpd.GeoDataFrame({"h3_r8": celdas[25:40]}, geometry=[shapely.Point(0, 0)] * 15)
    a = t04.particion(huellas, puntos)
    b = t04.particion(huellas, puntos)
    assert a.equals(b)
    assert len(a) == 40
    conteo = a.groupby(["estrato", "particion"]).size()
    assert conteo[("con_dano", "ajuste")] == 7
    assert conteo[("con_dano", "prueba")] == 8
    assert conteo[("sin_dano", "ajuste")] == 12
    assert conteo[("sin_dano", "prueba")] == 13


def test_emparejar_dentro_cercano_y_sin_huella() -> None:
    huellas = gpd.GeoDataFrame(
        {"id_huella": ["a", "b"], "area_in_meters": [100.0, 100.0]},
        geometry=[shapely.box(0, 0, 10, 10), shapely.box(100, 0, 110, 10)],
        crs=t04.CRS,
    )
    puntos = gpd.GeoDataFrame(
        {"fid": [1, 2, 3], "grado": [3, 2, 1]},
        geometry=[shapely.Point(5, 5), shapely.Point(118, 5), shapely.Point(60, 60)],
        crs=t04.CRS,
    )
    emp = t04.emparejar(puntos, huellas).set_index("fid")
    assert emp.loc[1, "metodo"] == "dentro"
    assert emp.loc[1, "id_huella"] == "a"
    assert emp.loc[2, "metodo"] == "cercano"
    assert emp.loc[2, "id_huella"] == "b"
    assert emp.loc[2, "distancia_m"] == pytest.approx(8.0)
    assert emp.loc[3, "metodo"] == "sin_huella"


def test_grilla_comun_alineada_a_20_m() -> None:
    transform, (alto, ancho) = t05.grilla()
    assert transform.a == 20.0
    assert transform.e == -20.0
    assert transform.c % 20 == 0
    assert transform.f % 20 == 0
    assert alto > 0
    assert ancho > 0
