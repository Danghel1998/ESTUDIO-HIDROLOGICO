"""Método del Número de Curva SCS + Hidrograma Unitario Triangular (Mockus).

Reemplaza el uso de HEC-HMS: aplica las abstracciones SCS al hietograma de
diseño (bloque alterno) para obtener la lluvia efectiva, genera el hidrograma
unitario triangular sintético de Mockus/SCS y los convoluciona para obtener
el hidrograma de creciente y el caudal máximo (Qmax).
"""

import numpy as np
import pandas as pd


def retencion_potencial_mm(cn: float) -> float:
    """S = 25400/CN - 254 (mm)"""
    return 25400.0 / cn - 254.0


def abstraccion_inicial_mm(s_mm: float, factor: float = 0.2) -> float:
    """Ia = factor * S (factor típico 0.2, rango aceptado 0.1 - 0.3)."""
    return factor * s_mm


def precipitacion_efectiva_acumulada(p_acum_mm: np.ndarray, cn: float, factor_ia: float = 0.2) -> np.ndarray:
    """Aplica la ecuación SCS a la precipitación ACUMULADA (no a los
    incrementos), tal como corresponde para obtener el hietograma de exceso.
    """
    s = retencion_potencial_mm(cn)
    ia = abstraccion_inicial_mm(s, factor_ia)
    p = np.asarray(p_acum_mm, dtype=float)
    pe = np.where(p > ia, (p - ia) ** 2 / (p - ia + s), 0.0)
    return pe


def hietograma_efectivo(hietograma_incremental_mm: np.ndarray, cn: float, factor_ia: float = 0.2) -> np.ndarray:
    """A partir del hietograma incremental (bloque alterno), calcula el
    hietograma de lluvia efectiva (mm) por intervalo."""
    p_acum = np.cumsum(hietograma_incremental_mm)
    pe_acum = precipitacion_efectiva_acumulada(p_acum, cn, factor_ia)
    pe_incremental = np.diff(pe_acum, prepend=0.0)
    return np.maximum(pe_incremental, 0.0)


def hidrograma_unitario_triangular(area_km2: float, tc_h: float, dt_h: float, lag_override_h: float | None = None) -> dict:
    """Hidrograma Unitario Sintético Triangular de Mockus/SCS, para 1 mm de
    lluvia efectiva caída uniformemente en dt horas sobre la cuenca.

    tp = dt/2 + tr ; tr = 0.6*tc (o lag_override_h si se indica) ; tb = 2.67*tp ; qp = 0.208*A/tp

    `lag_override_h` permite fijar directamente el tiempo de retardo (tr), tal
    como el parámetro "Lag" del método de transformación "SCS Unit Hydrograph"
    de HEC-HMS: en un modelo real ese valor es editable/calibrable por el
    usuario y no siempre coincide con 0.6*Tc calculado por fórmula.
    """
    tr = lag_override_h if lag_override_h is not None else 0.6 * tc_h
    tp = dt_h / 2.0 + tr
    tb = 2.67 * tp
    qp = 0.208 * area_km2 / tp  # m3/s por mm de lluvia efectiva

    # Discretiza el HU en pasos dt para poder convolucionar.
    n_pasos = max(int(np.ceil(tb / dt_h)), 2)
    t = np.arange(0, n_pasos + 1) * dt_h
    q = np.where(
        t <= tp,
        qp * (t / tp) if tp > 0 else 0.0,
        np.where(t <= tb, qp * (tb - t) / (tb - tp), 0.0),
    )
    q = np.clip(q, 0, None)
    return {"tr_h": tr, "tp_h": tp, "tb_h": tb, "qp_m3s_mm": qp, "t_h": t, "q_m3s_mm": q}


# Hidrograma Unitario Adimensional del SCS (forma curvilínea), tabla estándar
# t/Tp vs Q/Qp (USDA-NRCS National Engineering Handbook, Parte 630, Cap. 16).
# Es la forma que usa por defecto el método "SCS Unit Hydrograph" de HEC-HMS
# (a diferencia de la aproximación triangular de Mockus).
_SCS_ADIM_T_TP = np.array([
    0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0,
    1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9, 2.0,
    2.2, 2.4, 2.6, 2.8, 3.0, 3.2, 3.4, 3.6, 3.8, 4.0, 4.5, 5.0,
])
_SCS_ADIM_Q_QP = np.array([
    0.000, 0.030, 0.100, 0.190, 0.310, 0.470, 0.660, 0.820, 0.930, 0.990, 1.000,
    0.990, 0.930, 0.860, 0.780, 0.680, 0.560, 0.460, 0.390, 0.330, 0.280,
    0.207, 0.147, 0.107, 0.077, 0.055, 0.040, 0.029, 0.021, 0.015, 0.011, 0.005, 0.000,
])


def hidrograma_unitario_scs_adimensional(area_km2: float, tc_h: float, dt_h: float, lag_override_h: float | None = None) -> dict:
    """Hidrograma Unitario Adimensional del SCS (forma curvilínea real, no la
    aproximación triangular), para 1 mm de lluvia efectiva caída uniformemente
    en dt horas sobre la cuenca. Reproduce el mismo cálculo que el método de
    transformación "SCS Unit Hydrograph" de HEC-HMS.

    tp = dt/2 + tr ; tr = 0.6*tc (o lag_override_h si se indica) ; qp = 0.208*A/tp

    `lag_override_h` permite fijar directamente el tiempo de retardo (tr), tal
    como el parámetro "Lag" del método de transformación "SCS Unit Hydrograph"
    de HEC-HMS: en un modelo real ese valor es editable/calibrable por el
    usuario y no siempre coincide con 0.6*Tc calculado por fórmula.
    """
    tr = lag_override_h if lag_override_h is not None else 0.6 * tc_h
    tp = dt_h / 2.0 + tr
    tb = 5.0 * tp  # la cola de la curva se extiende hasta t/Tp = 5
    qp = 0.208 * area_km2 / tp  # m3/s por mm de lluvia efectiva

    n_pasos = max(int(np.ceil(tb / dt_h)), 2)
    t = np.arange(0, n_pasos + 1) * dt_h
    t_tp = t / tp if tp > 0 else np.zeros_like(t)
    q = qp * np.interp(t_tp, _SCS_ADIM_T_TP, _SCS_ADIM_Q_QP, left=0.0, right=0.0)
    return {"tr_h": tr, "tp_h": tp, "tb_h": tb, "qp_m3s_mm": qp, "t_h": t, "q_m3s_mm": q}


def tabla_convolucion(pe_incremental_mm: np.ndarray, hu: dict, dt_h: float, max_pulsos: int = 24):
    """Tabla explícita de la convolución discreta: una columna por cada uno de
    los `max_pulsos` pulsos de lluvia efectiva más grandes, con su hidrograma
    unitario desplazado y escalado, más 'Otros pulsos' (la suma de los pulsos
    restantes, más pequeños) y 'Q total' = suma de todo. Es el mismo mecanismo
    interno que usa el motor de cálculo de HEC-HMS para combinar el 'Loss' con
    el 'Transform' (convolución), mostrado paso a paso."""
    q_unit = hu["q_m3s_mm"]
    n_pe, n_hu = len(pe_incremental_mm), len(q_unit)
    n_total = n_pe + n_hu - 1
    t = np.arange(n_total) * dt_h

    idx_no_cero = [i for i, v in enumerate(pe_incremental_mm) if v > 0]
    idx_no_cero.sort(key=lambda i: pe_incremental_mm[i], reverse=True)
    idx_mostrados = set(idx_no_cero[:max_pulsos])

    data = {"t (h)": t}
    total = np.zeros(n_total)
    otros = np.zeros(n_total)
    for i in sorted(idx_mostrados):
        pe_i = pe_incremental_mm[i]
        col = np.zeros(n_total)
        col[i:i + n_hu] = pe_i * q_unit
        data[f"Pulso t={i * dt_h:.2f}h (Pe={pe_i:.2f}mm)"] = col
        total += col
    for i in idx_no_cero:
        if i in idx_mostrados:
            continue
        pe_i = pe_incremental_mm[i]
        col = np.zeros(n_total)
        col[i:i + n_hu] = pe_i * q_unit
        otros += col
        total += col
    if otros.any():
        data["Otros pulsos menores"] = otros
    data["Q total (m3/s)"] = total
    return pd.DataFrame(data)


def hidrograma_creciente(pe_incremental_mm: np.ndarray, hu: dict, dt_h: float) -> dict:
    """Convoluciona el hietograma de lluvia efectiva con el HU triangular
    para obtener el hidrograma de escorrentía directa. Devuelve el arreglo de
    tiempo/caudal y el caudal máximo (Qmax)."""
    q_unit = hu["q_m3s_mm"]
    q_total = np.convolve(pe_incremental_mm, q_unit)
    t_total = np.arange(len(q_total)) * dt_h
    return {"t_h": t_total, "q_m3s": q_total, "q_max": float(np.max(q_total)) if len(q_total) else 0.0}
