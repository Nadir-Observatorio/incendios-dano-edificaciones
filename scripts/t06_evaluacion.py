"""Tarea 06 del caso de dano a edificaciones (etapa E5). Se corre UNA vez.

Fija los umbrales en la particion de ajuste (percentil 90 de la senal en los negativos de ajuste) y
evalua la particion de prueba una sola vez, con intervalos por remuestreo de bloques. Responde P1 a P5
del protocolo sellado con las enmiendas 01 y 02.

Uso: python t06_evaluacion.py <carpeta_caso> <carpeta_t04> <carpeta_t05> <carpeta_salida>
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

VERIFICAR_CASO = {
    "PROTOCOLO_dano-edificaciones_sellado_2026-11-11.md": "de1993790a4e7485aeef3d64749a490dd735679feb5575263bc61ca727387f5d",
    "ENMIENDA_01_2026-11-11.md": "8ff741dde5bb5b2bbf391fe7652e5088640c2c02b0ac4c28818d0419a122bc1e",
    "ENMIENDA_02_2026-11-11.md": "82f1000d908f662e9e24596232a0832b493aa767d117af95012dd724d4341b27",
}
PARTICION_SHA256 = "2eaf84510b7c100ae5ca1f216ad7eb6c2f347bee011bb9b05fac81a4a7a61d2e"
SENALES_SHA256 = "76cf0a233ae0eb5d6cea644170f5a253d03dc75d8c3e7b87961307c070b0869b"

SEMILLA = 20240202
N_BOOT = 2000
PERCENTIL = 90.0
SENALES = ["z_comb", "z_asc", "z_des"]
GRADOS = {3: "Destroyed", 2: "Damaged", 1: "Possible damage"}


def sha256(ruta: Path) -> str:
    h = hashlib.sha256()
    with ruta.open("rb") as f:
        for bloque in iter(lambda: f.read(1 << 22), b""):
            h.update(bloque)
    return h.hexdigest()


def auc_ponderada(s: np.ndarray, y: np.ndarray, w: np.ndarray) -> float:
    """AUC de ROC con pesos (Mann-Whitney), empates a la mitad."""
    orden = np.argsort(s, kind="mergesort")
    s, y, w = s[orden], y[orden], w[orden]
    _, inicio = np.unique(s, return_index=True)
    grupos = np.repeat(np.arange(len(inicio)), np.diff(np.append(inicio, len(s))))
    wp = np.bincount(grupos, weights=w * y)
    wn = np.bincount(grupos, weights=w * (1 - y))
    neg_antes = np.cumsum(wn) - wn
    tp, tn = wp.sum(), wn.sum()
    if tp == 0 or tn == 0:
        return float("nan")
    return float(np.sum(wp * (neg_antes + 0.5 * wn)) / (tp * tn))


def ap_ponderada(s: np.ndarray, y: np.ndarray, w: np.ndarray) -> float:
    """Precision promedio (area bajo precision-sensibilidad) con pesos."""
    orden = np.argsort(-s, kind="mergesort")
    y, w = y[orden], w[orden]
    vp = np.cumsum(w * y)
    total = np.cumsum(w)
    tp = vp[-1]
    if tp == 0:
        return float("nan")
    precision = vp / np.where(total > 0, total, 1)
    return float(np.sum(precision * w * y) / tp)


def metricas(d: pd.DataFrame, w: np.ndarray, umbrales: dict[str, float]) -> dict[str, float]:
    m: dict[str, float] = {}
    pos = (d["rol"] == "positivo").to_numpy()
    neg = (d["rol"] == "negativo").to_numpy()
    ctl = (d["rol"] == "control").to_numpy()
    for senal, u in umbrales.items():
        v = d[senal].to_numpy()
        ok = np.isfinite(v)
        det = ok & (v >= u)
        wp, wn, wc = (w * (pos & ok)).sum(), (w * (neg & ok)).sum(), (w * (ctl & ok)).sum()
        vp, fp, fc = (w * (pos & det)).sum(), (w * (neg & det)).sum(), (w * (ctl & det)).sum()
        sens = vp / wp if wp else np.nan
        fa = fp / wn if wn else np.nan
        prec = vp / (vp + fp) if (vp + fp) else np.nan
        m[f"{senal}.sensibilidad"] = sens
        m[f"{senal}.falsa_alarma_negativos"] = fa
        m[f"{senal}.falsa_alarma_control"] = fc / wc if wc else np.nan
        m[f"{senal}.precision"] = prec
        m[f"{senal}.f1"] = 2 * prec * sens / (prec + sens) if (prec + sens) else np.nan
        m[f"{senal}.exactitud_balanceada"] = (sens + 1 - fa) / 2
        sel = (pos | neg) & ok
        m[f"{senal}.auc_roc"] = auc_ponderada(v[sel], pos[sel].astype(float), w[sel])
        m[f"{senal}.auc_pr"] = ap_ponderada(v[sel], pos[sel].astype(float), w[sel])
        for g, nombre in GRADOS.items():
            sg = pos & ok & (d["grado"].to_numpy() == g)
            m[f"{senal}.sensibilidad.{nombre}"] = (w * (sg & det)).sum() / (w * sg).sum() if (w * sg).sum() else np.nan
    # P2: optico (Etapa 1) frente a radar (z_comb) en las mismas huellas positivas con ambos datos
    v = d["z_comb"].to_numpy()
    radar = np.isfinite(v) & (v >= umbrales["z_comb"])
    for umbral_opt in ("A", "B"):
        o = d[f"optico_{umbral_opt}"].to_numpy()
        tiene = pos & np.isfinite(o) & np.isfinite(v)
        opt = np.where(np.isfinite(o), o, 0) > 0.5
        wt = (w * tiene).sum()
        s2 = (w * (tiene & opt)).sum() / wt if wt else np.nan
        s1 = (w * (tiene & radar)).sum() / wt if wt else np.nan
        un = (w * (tiene & (opt | radar))).sum() / wt if wt else np.nan
        no_opt = tiene & ~opt
        s1_rescate = (w * (no_opt & radar)).sum() / (w * no_opt).sum() if (w * no_opt).sum() else np.nan
        negt = neg & np.isfinite(o)
        m[f"p2.{umbral_opt}.sensibilidad_s2"] = s2
        m[f"p2.{umbral_opt}.sensibilidad_s1"] = s1
        m[f"p2.{umbral_opt}.sensibilidad_union"] = un
        m[f"p2.{umbral_opt}.diferencia_union_menos_s2"] = un - s2
        m[f"p2.{umbral_opt}.s1_entre_no_detectadas_s2"] = s1_rescate
        m[f"p2.{umbral_opt}.falsa_alarma_s2_negativos"] = (
            (w * (negt & opt)).sum() / (w * negt).sum() if (w * negt).sum() else np.nan
        )
        m[f"p2.{umbral_opt}.falsa_alarma_union_negativos"] = (
            (w * (negt & (opt | radar))).sum() / (w * negt).sum() if (w * negt).sum() else np.nan
        )
    # persistencia (descriptiva): de las positivas detectadas, cuantas siguen sobre el umbral en el par posterior
    zp = d["zpost_comb"].to_numpy()
    dp = pos & radar
    m["persistencia.positivas_detectadas_que_persisten"] = (
        (w * (dp & (zp >= umbrales["z_comb"]))).sum() / (w * dp).sum() if (w * dp).sum() else np.nan
    )
    return m


def main() -> int:
    if len(sys.argv) != 5:
        print(__doc__)
        return 2
    caso, t04, t05, salida = map(Path, sys.argv[1:])
    if (salida / "metricas.json").exists():
        print("FALLO la evaluacion de prueba ya se hizo; no se repite")
        return 1
    salida.mkdir(parents=True, exist_ok=True)
    print(f"== inicio {dt.datetime.now().isoformat(timespec='seconds')}")
    for nombre, esperado in VERIFICAR_CASO.items():
        if sha256(caso / nombre) != esperado:
            print(f"FALLO huella de {nombre}")
            return 1
    if sha256(t04 / "particion.csv") != PARTICION_SHA256 or sha256(t05 / "senales_huellas.parquet") != SENALES_SHA256:
        print("FALLO huella de la particion o de las senales")
        return 1
    print("verificados protocolo, enmiendas, particion y senales")

    senales = pd.read_parquet(t05 / "senales_huellas.parquet")
    resultado: dict[str, Any] = {
        "nota": "Evaluacion unica de la particion de prueba. Umbral: percentil 90 de cada senal en los "
        "negativos de ajuste. Intervalos 95 % por remuestreo de bloques H3 r8 de prueba.",
        "semilla": SEMILLA,
        "repeticiones": N_BOOT,
        "conjuntos": {},
    }
    celdas_salida: dict[str, pd.DataFrame] = {}
    for conjunto in ("principal", "sensibilidad"):
        h = pd.read_parquet(
            t04 / f"huellas_{conjunto}.parquet",
            columns=["id_huella", "rol", "grado", "particion", "h3_r8", "h3_r9", "h3_r10", "en_aoi", "area_in_meters"],
        )
        d = h.merge(senales, on="id_huella", how="left")
        aj = d[d["particion"] == "ajuste"]
        pr = d[d["particion"] == "prueba"].reset_index(drop=True)

        umbrales = {}
        for s in SENALES:
            neg = aj.loc[(aj["rol"] == "negativo") & np.isfinite(aj[s]), s].to_numpy()
            umbrales[s] = float(np.percentile(neg, PERCENTIL))
        print(f"[{conjunto}] umbrales (ajuste): {umbrales}")

        punto = metricas(pr, np.ones(len(pr)), umbrales)
        bloques = pr["h3_r8"].to_numpy()
        ub, inv = np.unique(bloques, return_inverse=True)
        rng = np.random.default_rng(SEMILLA)
        muestras: dict[str, list[float]] = {k: [] for k in punto}
        for _ in range(N_BOOT):
            mult = np.bincount(rng.integers(0, len(ub), len(ub)), minlength=len(ub))
            mb = metricas(pr, mult[inv].astype(float), umbrales)
            for k, v in mb.items():
                muestras[k].append(v)
        tabla = {
            k: {
                "valor": punto[k],
                "ic95": [float(np.nanpercentile(muestras[k], 2.5)), float(np.nanpercentile(muestras[k], 97.5))],
            }
            for k in punto
        }

        # P4: estratos por tercil (cortes fijados con las huellas positivas y negativas de ajuste)
        estratos: dict[str, Any] = {}
        base_aj = aj[aj["rol"].isin(["positivo", "negativo"])]
        for var, nombre in (
            ("pendiente", "pendiente"),
            ("area_in_meters", "area_huella"),
            ("cohprev_comb", "coherencia_previa"),
        ):
            cortes = np.nanpercentile(base_aj[var], [100 / 3, 200 / 3])
            ter = np.digitize(pr[var].to_numpy(), cortes)
            estratos[nombre] = {"cortes_ajuste": [float(c) for c in cortes]}
            for t in range(3):
                sub = pr[(ter == t) & np.isfinite(pr[var].to_numpy())]
                mm = metricas(sub, np.ones(len(sub)), {"z_comb": umbrales["z_comb"]})
                estratos[nombre][f"tercil_{t + 1}"] = {
                    "n_positivas": int((sub["rol"] == "positivo").sum()),
                    "n_negativas": int((sub["rol"] == "negativo").sum()),
                    "sensibilidad": mm["z_comb.sensibilidad"],
                    "falsa_alarma_negativos": mm["z_comb.falsa_alarma_negativos"],
                }

        # Exploratorio: regresion logistica en ajuste, evaluada en prueba
        cols = ["z_asc", "z_des", "pendiente", "area_in_meters"]

        def prep(x: pd.DataFrame, cols: list[str] = cols) -> tuple[np.ndarray, np.ndarray]:
            x = x[x["rol"].isin(["positivo", "negativo"])].dropna(subset=cols)
            xx = x[cols].to_numpy(dtype=float).copy()
            xx[:, 3] = np.log(xx[:, 3])
            return xx, (x["rol"] == "positivo").to_numpy(dtype=float)

        xa, ya = prep(aj)
        xp, yp = prep(pr)
        mu, sd = xa.mean(axis=0), xa.std(axis=0)
        modelo = LogisticRegression(max_iter=1000).fit((xa - mu) / sd, ya)
        prob = modelo.predict_proba((xp - mu) / sd)[:, 1]
        exploratorio = {
            "rotulo": "EXPLORATORIO",
            "variables": ["z_asc", "z_des", "pendiente", "log(area_huella)"],
            "coeficientes_estandarizados": [float(c) for c in modelo.coef_[0]],
            "auc_roc_prueba": auc_ponderada(prob, yp, np.ones(len(yp))),
            "brier_prueba": float(np.mean((prob - yp) ** 2)),
            "brier_referencia_prueba": float(np.mean((ya.mean() - yp) ** 2)),
        }

        conteos = {
            f"{rol}|{part}": int(n)
            for (rol, part), n in d[np.isfinite(d["z_comb"])].groupby(["rol", "particion"]).size().items()
        }
        resultado["conjuntos"][conjunto] = {
            "umbrales_ajuste": umbrales,
            "huellas_validas": conteos,
            "metricas_prueba": tabla,
            "p4_estratos_prueba": estratos,
            "exploratorio": exploratorio,
        }
        print(f"[{conjunto}] P1 sensibilidad z_comb {tabla['z_comb.sensibilidad']}")

        # P5: celdas fuera del area de EMSN188 (estimacion de modelo)
        if conjunto == "principal":
            fuera = d[~d["en_aoi"] & np.isfinite(d["z_comb"])]
            for res in (10, 9):
                c = (
                    fuera.groupby(f"h3_r{res}")
                    .agg(n_huellas=("id_huella", "size"), z_comb_mediana=("z_comb", "median"))
                    .reset_index()
                )
                c = c.rename(columns={f"h3_r{res}": "celda"})
                c["sobre_umbral"] = c["z_comb_mediana"] >= umbrales["z_comb"]
                celdas_salida[f"p5_celdas_r{res}"] = c
                resultado["conjuntos"][conjunto][f"p5_r{res}"] = {
                    "celdas": len(c),
                    "celdas_sobre_umbral": int(c["sobre_umbral"].sum()),
                    "rotulo": "estimacion de modelo",
                }
            # Celdas dentro y fuera, para el sitio (todas las huellas validas del conjunto principal)
            todas = d[np.isfinite(d["z_comb"])].copy()
            todas["det_s1"] = todas["z_comb"] >= umbrales["z_comb"]
            todas["det_s2"] = todas["optico_A"] > 0.5
            for res in (10, 9):
                c = (
                    todas.groupby(f"h3_r{res}")
                    .agg(
                        n_huellas=("id_huella", "size"),
                        n_emsn188=("rol", lambda r: int((r == "positivo").sum())),
                        n_detectadas_s1=("det_s1", "sum"),
                        n_detectadas_s2=("det_s2", "sum"),
                        n_detectadas_union=(
                            "det_s1",
                            lambda x, todas=todas: int((x | todas.loc[x.index, "det_s2"]).sum()),
                        ),
                        z_coherencia_mediana=("z_comb", "median"),
                        en_aoi_emsn188=("en_aoi", "max"),
                    )
                    .reset_index()
                    .rename(columns={f"h3_r{res}": "celda"})
                )
                celdas_salida[f"celdas_r{res}"] = c

    for nombre, c in celdas_salida.items():
        c.to_parquet(salida / f"{nombre}.parquet", index=False)
    texto = json.dumps(resultado, ensure_ascii=False, indent=2, default=float)
    (salida / "metricas.json").write_text(texto, encoding="utf-8")
    print(texto)
    for f in sorted(salida.iterdir()):
        print(f"huella {f.name} {sha256(f)}")
    print("FIN OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
