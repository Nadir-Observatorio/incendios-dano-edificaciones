"""Pruebas de la configuracion por caso y de la combinacion de orbitas."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import caso as caso_mod
import t04_huellas_particion as t04
import t05_senales as t05
import t06_evaluacion as t06

CASOS = Path(os.environ.get("NADIR_CASOS", Path(__file__).resolve().parents[1] / "casos"))


def test_vina_toml_coincide_con_los_valores_de_origen_de_las_pruebas() -> None:
    vina = caso_mod.cargar(CASOS / "vina-2024", con_rutas=False)
    assert vina.crs == t04.CRS == t05.CRS
    assert vina.semilla == t04.SEMILLA
    assert vina.radio_empareje_m == t04.RADIO_EMPAREJE_M
    assert vina.caja == t05.CAJA
    assert vina.grados == t06.GRADOS
    assert vina.grupos == {"asc": ["asc"], "des": ["des"]}
    assert vina.senales == ["z_comb", "z_asc", "z_des"]
    assert [d.sha256[:8] for d in vina.documentos] == ["de199379", "8ff741dd", "82f1000d"]
    assert vina.fijada("metricas_sha256").startswith("70960bb6")


def test_penco_toml_sigue_el_protocolo_sellado() -> None:
    penco = caso_mod.cargar(CASOS / "penco-2026", con_rutas=False)
    assert penco.documentos[0].sha256 == "ec6a3cd5651314d6d4ea40149a0e29795103d0802c0d1229d8fa4b6445a43f44"
    assert penco.crs == "EPSG:32718"
    assert penco.semilla == 20260117
    assert penco.grupos == {"asc": ["asc091", "asc164"], "des": ["des156"]}
    assert penco.caja == (-73.059, -36.948, -72.769, -36.618)
    assert penco.grados[1] == "Possibly damaged"
    assert penco.p5_modo == "centro_celda"


def test_huella_fijada_que_falta_detiene_la_tarea() -> None:
    penco = caso_mod.cargar(CASOS / "penco-2026", con_rutas=False)
    with pytest.raises(caso_mod.CasoInvalido, match="particion_sha256"):
        penco.fijada("particion_sha256")


def test_caso_sin_grupo_descendente_se_rechaza(tmp_path: Path) -> None:
    carpeta = tmp_path / "malo"
    shutil.copytree(CASOS / "penco-2026", carpeta)
    texto = (carpeta / "caso.toml").read_text(encoding="utf-8").replace('grupo = "des"', 'grupo = "asc"')
    (carpeta / "caso.toml").write_text(texto, encoding="utf-8")
    with pytest.raises(caso_mod.CasoInvalido, match="asc"):
        caso_mod.cargar(carpeta, con_rutas=False)


def tabla_orbitas(valores: dict[str, list[float]]) -> pd.DataFrame:
    t = pd.DataFrame()
    for o, z in valores.items():
        t[f"z_{o}"] = z
        t[f"zpost_{o}"] = [x / 2 for x in z]
        t[f"cohprev_{o}"] = [0.5] * len(z)
        t[f"valida_{o}"] = np.isfinite(z)
    return t


def test_combinacion_con_una_orbita_por_grupo_es_la_de_vina() -> None:
    t = tabla_orbitas({"asc": [1.0, np.nan, 3.0], "des": [3.0, 2.0, np.nan]})
    columnas = list(t.columns)
    out = t05.combinar_por_grupo(t.copy(), {"asc": ["asc"], "des": ["des"]})
    assert list(out.columns) == [*columnas, "z_comb", "zpost_comb", "cohprev_comb"]
    np.testing.assert_allclose(out["z_comb"], [2.0, 2.0, 3.0])


def test_combinacion_d2a_promedia_ascendentes_antes_que_la_descendente() -> None:
    t = tabla_orbitas({"asc091": [1.0, np.nan, np.nan], "asc164": [3.0, 5.0, np.nan], "des156": [6.0, 1.0, 4.0]})
    out = t05.combinar_por_grupo(t, {"asc": ["asc091", "asc164"], "des": ["des156"]})
    np.testing.assert_allclose(out["z_asc"], [2.0, 5.0, np.nan])
    np.testing.assert_array_equal(out["valida_asc"], [True, True, False])
    # mitad ascendente y mitad descendente, no un tercio por orbita
    np.testing.assert_allclose(out["z_comb"], [4.0, 3.0, 4.0])


def test_mascara_nombra_la_orbita_en_el_error() -> None:
    with pytest.raises(ValueError, match="asc164"):
        t05.mascara_geometria(
            np.full((5, 5), 51.0), np.full((5, 5), 90.0), np.zeros((5, 5)), "asc", [], etiqueta="asc164"
        )


def test_precision_promedio_sin_huellas_es_sin_dato() -> None:
    vacio = np.array([], dtype=float)
    assert np.isnan(t06.ap_ponderada(vacio, vacio, vacio))
