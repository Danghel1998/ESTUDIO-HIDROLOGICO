"""Curvas Intensidad - Duración - Frecuencia (IDF) a partir de Pmax24h.

Implementa los dos criterios usados en los estudios viales del MTC cuando no
se cuenta con registros pluviográficos:

- Dyck y Peschke: relación fija duración/24h -> intensidad.
- Frederic Bell / regresión general I = a * T^b * D^-m, ajustada por mínimos
  cuadrados (linealización log-log) a partir de las duraciones e intensidades
  Dyck-Peschke, tal como lo hace el manual del MTC para obtener una ecuación
  cerrada I(T, D).
"""

import numpy as np

DURACIONES_MIN_DEFAULT = [5, 10, 20, 30, 60, 120, 180, 240, 360, 720, 1440]


def dyck_peschke_pt(p24h_t: float, duracion_min: float) -> float:
    """Precipitación Pd (mm) para una duración d (min) dada Pmax24h para el
    periodo de retorno T, según Dyck y Peschke (Guevara, 1991)."""
    d_horas = duracion_min / 60.0
    return p24h_t * (d_horas / 24.0) ** 0.25


def dyck_peschke_intensidad(p24h_t: float, duracion_min: float) -> float:
    pd = dyck_peschke_pt(p24h_t, duracion_min)
    return pd / (duracion_min / 60.0)


def tabla_intensidades(p24h_por_tr: dict[float, float], duraciones_min=None) -> "pd.DataFrame":
    """Genera la tabla Intensidad(T, D) por el criterio Dyck-Peschke.

    p24h_por_tr: {T (años): Pmax24h (mm)}
    """
    import pandas as pd

    duraciones_min = duraciones_min or DURACIONES_MIN_DEFAULT
    data = {}
    for tr, p24h in p24h_por_tr.items():
        data[tr] = [dyck_peschke_intensidad(p24h, d) for d in duraciones_min]
    df = pd.DataFrame(data, index=duraciones_min)
    df.index.name = "Duración (min)"
    return df


def frederic_bell_p110(p24h_t10: float) -> float:
    """Precipitación de 1 hora y 10 años (P1,10), estimada por Dyck-Peschke a
    partir de Pmax24h para T=10 años (tal como lo hace el Manual MTC cuando no
    se cuenta con el dato medido directamente)."""
    return dyck_peschke_pt(p24h_t10, 60)


def frederic_bell_precipitacion(p110: float, tr_years: float, duracion_min: float) -> float:
    """P(T,D) = P1,10 * (0.21*ln(T) + 0.52) * (0.54*D^0.25 - 0.50)

    D en minutos (válido aprox. 5 - 120 min), T en años (2 - 100).
    """
    return p110 * (0.21 * np.log(tr_years) + 0.52) * (0.54 * duracion_min ** 0.25 - 0.50)


def frederic_bell_intensidad_fn(p24h_t10: float):
    """Devuelve una función intensidad_fn(T, D_min) -> mm/h según el criterio
    de Frederic Bell, calibrada con Pmax24h de T=10 años de la propia estación."""
    p110 = frederic_bell_p110(p24h_t10)

    def intensidad_fn(tr_years: float, duracion_min: float) -> float:
        p = frederic_bell_precipitacion(p110, tr_years, duracion_min)
        return p / (duracion_min / 60.0)

    return intensidad_fn


def ajustar_regresion_potencial(intensidad_base_fn, trs, duraciones_min, calibrar_weibull=True):
    """Ajusta el modelo I = a * T^b * D^-m por regresión lineal múltiple sobre
    log(I) = log(a) + b*log(T) - m*log(D), a partir de los puntos generados
    por `intensidad_base_fn(tr, d)` (Dyck-Peschke, Bell, etc).

    Réplica exacta del procedimiento de Hidroesta 2. Para el criterio Dyck-
    Peschke (calibrar_weibull=True), los n periodos de retorno de diseño NO
    se usan directamente como "T" de la regresión; en su lugar, los n valores
    de precipitación generados se re-indexan como si fueran una muestra
    empírica de tamaño n, asignando a cada uno un T de calibración por
    posición de graficación de Weibull, T_cal = (n+1)/(n+1-i) con i=1..n en
    orden ascendente de precipitación. Para el criterio Bell (calibrar_weibull
    =False) se usan directamente los T nominales del set fijo estándar.
    La ecuación resultante a·Tᵇ·D⁻ᵐ se evalúa igualmente con los T reales
    (de diseño) una vez calibrada.

    Devuelve a, b, m, R y R² (del ajuste log-log) y Se (error estándar de
    estimación en mm/h, escala original, con n-3 grados de libertad), además
    de intensidad_fn(T, D_min) -> I (mm/h).
    """
    trs_ordenados = sorted(trs)
    n = len(trs_ordenados)
    if calibrar_weibull:
        t_calibracion = {tr: (n + 1) / (n + 1 - i) for i, tr in enumerate(trs_ordenados, start=1)}
    else:
        t_calibracion = {tr: tr for tr in trs_ordenados}

    rows_Tcal, rows_D, rows_I = [], [], []
    for tr in trs_ordenados:
        for d in duraciones_min:
            rows_Tcal.append(t_calibracion[tr])
            rows_D.append(d)
            rows_I.append(intensidad_base_fn(tr, d))

    Tcal = np.array(rows_Tcal, dtype=float)
    D = np.array(rows_D, dtype=float)
    I = np.array(rows_I, dtype=float)

    X = np.column_stack([np.ones_like(Tcal), np.log(Tcal), np.log(D)])
    y = np.log(I)
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    log_a, b, neg_m = coef
    a = np.exp(log_a)
    m = -neg_m

    y_pred = X @ coef
    ss_res_log = np.sum((y - y_pred) ** 2)
    ss_tot_log = np.sum((y - y.mean()) ** 2)
    r2 = 1 - ss_res_log / ss_tot_log if ss_tot_log > 0 else float("nan")
    r = float(np.sqrt(r2)) if r2 >= 0 else float("nan")

    def intensidad_fn(tr_years: float, duracion_min: float) -> float:
        return a * (tr_years ** b) * (duracion_min ** (-m))

    i_pred_orig = a * (Tcal ** b) * (D ** (-m))
    resid = I - i_pred_orig
    n_pts, k = len(I), 3
    se = float(np.sqrt(np.sum(resid ** 2) / max(n_pts - k, 1)))

    return {"a": a, "b": b, "m": m, "r": r, "r2": r2, "se": se, "intensidad_fn": intensidad_fn}


def ajustar_regresion_idf(p24h_por_tr: dict[float, float], duraciones_min=None):
    """Ajuste de regresión potencial sobre los puntos generados por Dyck-Peschke."""
    duraciones_min = duraciones_min or DURACIONES_MIN_DEFAULT
    trs = sorted(p24h_por_tr)
    base_fn = lambda tr, d: dyck_peschke_intensidad(p24h_por_tr[tr], d)
    return ajustar_regresion_potencial(base_fn, trs, duraciones_min)


# Set fijo estándar de periodos de retorno y duraciones que usa Hidroesta 2
# para calibrar la ecuación de Bell (no depende de los T de diseño del
# usuario, a diferencia de Dyck-Peschke).
BELL_TRS_ESTANDAR = [2, 3, 5, 10, 25, 50, 100]
BELL_DURACIONES_ESTANDAR = [5, 10, 20, 30, 60, 120]


def ajustar_regresion_bell(p24h_por_tr: dict[float, float], duraciones_min=None):
    """Ajuste de regresión potencial sobre los puntos generados por Frederic
    Bell, usando el set fijo estándar de T (2,3,5,10,25,50,100 años) y
    duraciones (5,10,20,30,60,120 min) de Hidroesta 2, sin recalibración de
    Weibull (a diferencia de Dyck-Peschke)."""
    duraciones_min = duraciones_min or BELL_DURACIONES_ESTANDAR
    trs_ref = sorted(p24h_por_tr)
    if 10 in p24h_por_tr:
        p24h_t10 = p24h_por_tr[10]
    else:
        p24h_t10 = float(np.interp(10, trs_ref, [p24h_por_tr[t] for t in trs_ref]))
    base_fn = frederic_bell_intensidad_fn(p24h_t10)
    return ajustar_regresion_potencial(base_fn, BELL_TRS_ESTANDAR, duraciones_min, calibrar_weibull=False)
