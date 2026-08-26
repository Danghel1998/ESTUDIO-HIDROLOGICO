"""Prueba de datos dudosos (outliers) - método del U.S. Water Resources Council,
tal como se aplica en los estudios de hidrología vial del MTC (Perú)."""

import numpy as np

# Tabla de valores Kn (significancia 10%), interpolada linealmente para n intermedios.
_KN_TABLE = {
    10: 2.036, 11: 2.088, 12: 2.134, 13: 2.175, 14: 2.213, 15: 2.247,
    16: 2.279, 17: 2.309, 18: 2.335, 19: 2.361, 20: 2.385, 21: 2.408,
    22: 2.429, 23: 2.448, 24: 2.467, 25: 2.486, 26: 2.502, 27: 2.519,
    28: 2.534, 29: 2.549, 30: 2.563, 32: 2.591, 34: 2.616, 36: 2.639,
    38: 2.661, 40: 2.682, 42: 2.701, 44: 2.720, 46: 2.737, 48: 2.754,
    50: 2.768, 55: 2.804, 60: 2.837, 65: 2.866, 70: 2.893, 75: 2.917,
    80: 2.940, 85: 2.961, 90: 2.981, 95: 3.000, 100: 3.017,
}


def kn_value(n: int) -> float:
    keys = sorted(_KN_TABLE)
    if n <= keys[0]:
        return _KN_TABLE[keys[0]]
    if n >= keys[-1]:
        return _KN_TABLE[keys[-1]]
    return float(np.interp(n, keys, [_KN_TABLE[k] for k in keys]))


def estadisticos_descriptivos(x: np.ndarray) -> dict:
    """Estadísticos descriptivos con las mismas fórmulas que Hidroesta 2:
    N, Sumatoria, Máximo, Mínimo, Media, Varianza, Desv. Estándar, Coef. de
    Variación, Coeficiente de Sesgo y Coeficiente de Curtosis (muestral,
    ajustados por sesgo, tipo Excel SKEW/KURT+3)."""
    x = np.asarray(x, dtype=float)
    n = len(x)
    media = x.mean()
    std = x.std(ddof=1)
    var = x.var(ddof=1)
    z = (x - media) / std
    sesgo = n / ((n - 1) * (n - 2)) * np.sum(z ** 3)
    curtosis = n ** 2 / ((n - 1) * (n - 2) * (n - 3)) * np.sum(z ** 4)
    return {
        "n": n,
        "suma": x.sum(),
        "maximo": x.max(),
        "minimo": x.min(),
        "media": media,
        "varianza": var,
        "desv_std": std,
        "coef_variacion": std / media,
        "coef_sesgo": sesgo,
        "coef_curtosis": curtosis,
    }


def outlier_test(values: np.ndarray) -> dict:
    """Aplica la prueba de datos dudosos sobre una serie de máximos anuales.

    Devuelve umbrales alto/bajo (en unidades originales) y los valores que
    quedan fuera de rango.
    """
    x = np.asarray(values, dtype=float)
    x = x[~np.isnan(x)]
    n = len(x)
    logx = np.log10(x)
    mean_log = logx.mean()
    std_log = logx.std(ddof=1)
    kn = kn_value(n)

    x_high_log = mean_log + kn * std_log
    x_low_log = mean_log - kn * std_log
    p_high = 10 ** x_high_log
    p_low = 10 ** x_low_log

    high_outliers = x[x > p_high]
    low_outliers = x[x < p_low]

    return {
        "n": n,
        "kn": kn,
        "mean_log": mean_log,
        "std_log": std_log,
        "umbral_alto": p_high,
        "umbral_bajo": p_low,
        "outliers_altos": high_outliers,
        "outliers_bajos": low_outliers,
        "hay_outliers_altos": len(high_outliers) > 0,
        "hay_outliers_bajos": len(low_outliers) > 0,
    }
