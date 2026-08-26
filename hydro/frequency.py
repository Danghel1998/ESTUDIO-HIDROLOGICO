"""Análisis de frecuencias de valores máximos (precipitación o caudal).

Implementa las 8 distribuciones recomendadas por el Manual de Hidrología,
Hidráulica y Drenaje del MTC, la prueba de bondad de ajuste Kolmogorov-Smirnov
y el cálculo de valores para distintos periodos de retorno.
"""

from dataclasses import dataclass, field

import numpy as np
from scipy import stats

from .outliers import estadisticos_descriptivos

# ---------------------------------------------------------------------------
# Valor crítico de Kolmogorov-Smirnov: fórmula asintótica Dα = c(α)/√n,
# usada por Hidroesta 2 y por el Manual MTC para cualquier tamaño de muestra
# (fila "n grande" de la tabla del manual).
# ---------------------------------------------------------------------------
_KS_COEF = {0.20: 1.07, 0.10: 1.22, 0.05: 1.36, 0.02: 1.52, 0.01: 1.63}


def ks_critical(n: int, alpha: float = 0.05) -> float:
    """Valor crítico D_alpha de Kolmogorov-Smirnov: c(alpha)/sqrt(n)."""
    coef = _KS_COEF.get(alpha, 1.36)
    return coef / np.sqrt(n)


@dataclass
class DistFitResult:
    name: str
    params: dict
    ks_d: float
    ks_crit: float
    accepted: bool
    quantile_fn: object = field(repr=False)  # callable(p_exceed) -> x
    x_sorted: np.ndarray = field(default=None, repr=False)
    cdf_empirica: np.ndarray = field(default=None, repr=False)
    cdf_teorica: np.ndarray = field(default=None, repr=False)

    def value_for_return_period(self, tr: float) -> float:
        return float(self.quantile_fn(1.0 / tr))


def _ks_statistic(x_sorted: np.ndarray, cdf_vals: np.ndarray) -> float:
    n = len(x_sorted)
    # Fo(xm): posición de graficación empírica (Aparicio, 1996) m/(n+1)
    emp = np.arange(1, n + 1) / (n + 1)
    return float(np.max(np.abs(emp - cdf_vals)))


def _make_result(name, params, x_sorted, cdf_vals, quantile_fn) -> DistFitResult:
    n = len(x_sorted)
    emp = np.arange(1, n + 1) / (n + 1)
    d = _ks_statistic(x_sorted, cdf_vals)
    d_crit = ks_critical(n)
    return DistFitResult(name, params, d, d_crit, d < d_crit, quantile_fn, x_sorted, emp, cdf_vals)


def fit_normal(x: np.ndarray) -> DistFitResult:
    mu, sigma = x.mean(), x.std(ddof=1)
    x_sorted = np.sort(x)
    cdf = stats.norm.cdf(x_sorted, mu, sigma)
    qfn = lambda p: stats.norm.isf(p, mu, sigma)
    return _make_result("Normal", {"mu": mu, "sigma": sigma}, x_sorted, cdf, qfn)


def fit_lognormal2(x: np.ndarray) -> DistFitResult:
    y = np.log(x)
    muy, sigmay = y.mean(), y.std(ddof=1)
    x_sorted = np.sort(x)
    cdf = stats.norm.cdf(np.log(x_sorted), muy, sigmay)
    qfn = lambda p: np.exp(stats.norm.isf(p, muy, sigmay))
    return _make_result("Log Normal 2 parámetros", {"muy": muy, "sigmay": sigmay}, x_sorted, cdf, qfn)


def fit_lognormal3(x: np.ndarray) -> DistFitResult:
    """Log Normal 3 parámetros -- mismo estimador que Hidroesta 2: el
    parámetro de posición x0 se obtiene por el método de los 3 puntos
    (mínimo, mediana, máximo):
        x0 = (x1·xn - xm²) / (x1 + xn - 2·xm)
    y luego μy, σy son la media y la desviación estándar POBLACIONAL
    (ddof=0) de y = ln(x - x0)."""
    x1 = x.min()
    xn = x.max()
    xm = np.median(x)
    x0 = (x1 * xn - xm ** 2) / (x1 + xn - 2 * xm)
    y = np.log(x - x0)
    muy = y.mean()
    sigmay = y.std(ddof=0)
    x_sorted = np.sort(x)
    cdf = stats.norm.cdf(np.log(x_sorted - x0), muy, sigmay)
    qfn = lambda p: x0 + np.exp(stats.norm.isf(p, muy, sigmay))
    return _make_result(
        "Log Normal 3 parámetros",
        {"x0 (loc)": x0, "escala (uy)": muy, "forma (Sy)": sigmay},
        x_sorted, cdf, qfn,
    )


def fit_gamma2(x: np.ndarray) -> DistFitResult:
    """Gamma 2 parámetros por máxima verosimilitud, vía la aproximación
    cerrada de Thom (1958) -- el mismo estimador que usa Hidroesta 2 bajo la
    etiqueta "momentos ordinarios":
        A = ln(media) - media(ln(x))
        forma = (1 + sqrt(1 + 4A/3)) / (4A)
        escala = media / forma
    """
    media = x.mean()
    a_thom = np.log(media) - np.mean(np.log(x))
    shape = (1 + np.sqrt(1 + 4 * a_thom / 3)) / (4 * a_thom)
    scale = media / shape
    x_sorted = np.sort(x)
    cdf = stats.gamma.cdf(x_sorted, shape, loc=0, scale=scale)
    qfn = lambda p: stats.gamma.isf(p, shape, loc=0, scale=scale)
    return _make_result("Gamma 2 parámetros", {"forma": shape, "escala": scale}, x_sorted, cdf, qfn)


def _gamma3_momentos(media: float, sigma: float, cs: float):
    """Parámetros de Gamma/Pearson III por método de momentos a partir de la
    media, desviación estándar y coeficiente de sesgo (Cs) de la muestra."""
    beta = sigma * cs / 2.0
    shape = (2.0 / cs) ** 2
    x0 = media - shape * beta
    return shape, beta, x0


def _pearson3_cdf_qfn(x_sorted: np.ndarray, shape: float, beta: float, x0: float):
    """CDF y función cuantil de la distribución Pearson III (beta puede ser
    negativo, caso de sesgo negativo, mediante reflexión)."""
    if beta > 0:
        cdf = stats.gamma.cdf(x_sorted, shape, loc=x0, scale=beta)
        qfn = lambda p: stats.gamma.isf(p, shape, loc=x0, scale=beta)
    else:
        cdf = stats.gamma.cdf(x0 - x_sorted, shape, loc=0, scale=-beta)
        qfn = lambda p: x0 - stats.gamma.isf(1 - p, shape, loc=0, scale=-beta)
    return cdf, qfn


def fit_gamma3(x: np.ndarray) -> DistFitResult:
    """Gamma 3 parámetros (Pearson III) por método de momentos, usando el
    mismo coeficiente de sesgo (Cs) que la tabla de parámetros estadísticos."""
    st_desc = estadisticos_descriptivos(x)
    media, sigma, cs = st_desc["media"], st_desc["desv_std"], st_desc["coef_sesgo"]
    shape, beta, x0 = _gamma3_momentos(media, sigma, cs)
    x_sorted = np.sort(x)
    cdf, qfn = _pearson3_cdf_qfn(x_sorted, shape, beta, x0)
    return _make_result(
        "Gamma 3 parámetros", {"x0 (loc)": x0, "escala": beta, "forma": shape}, x_sorted, cdf, qfn
    )


def fit_logpearson3(x: np.ndarray) -> DistFitResult:
    """Log Pearson tipo III por método de momentos sobre log10(x)."""
    y = np.log10(x)
    st_desc = estadisticos_descriptivos(y)
    media, sigma, cs = st_desc["media"], st_desc["desv_std"], st_desc["coef_sesgo"]
    shape, beta, y0 = _gamma3_momentos(media, sigma, cs)
    x_sorted = np.sort(x)
    y_sorted = np.log10(x_sorted)
    cdf, qfn_log = _pearson3_cdf_qfn(y_sorted, shape, beta, y0)
    qfn = lambda p: 10 ** qfn_log(p)
    return _make_result(
        "Log Pearson tipo III", {"asimetria": cs, "loc": y0, "escala": beta}, x_sorted, cdf, qfn
    )


def fit_gumbel(x: np.ndarray) -> DistFitResult:
    sigma = np.sqrt(6) * x.std(ddof=1) / np.pi  # alpha (escala)
    mu = x.mean() - 0.5772 * sigma  # beta (localización)
    x_sorted = np.sort(x)
    cdf = stats.gumbel_r.cdf(x_sorted, mu, sigma)
    qfn = lambda p: stats.gumbel_r.isf(p, mu, sigma)
    return _make_result("Gumbel", {"alpha": sigma, "beta": mu}, x_sorted, cdf, qfn)


def fit_loggumbel(x: np.ndarray) -> DistFitResult:
    y = np.log(x)
    sigma = np.sqrt(6) * y.std(ddof=1) / np.pi
    mu = y.mean() - 0.5772 * sigma
    x_sorted = np.sort(x)
    cdf = stats.gumbel_r.cdf(np.log(x_sorted), mu, sigma)
    qfn = lambda p: np.exp(stats.gumbel_r.isf(p, mu, sigma))
    return _make_result("Log Gumbel", {"alpha": sigma, "beta": mu}, x_sorted, cdf, qfn)


ALL_FITTERS = {
    "Normal": fit_normal,
    "Log Normal 2 parámetros": fit_lognormal2,
    "Log Normal 3 parámetros": fit_lognormal3,
    "Gamma 2 parámetros": fit_gamma2,
    "Gamma 3 parámetros": fit_gamma3,
    "Log Pearson tipo III": fit_logpearson3,
    "Gumbel": fit_gumbel,
    "Log Gumbel": fit_loggumbel,
}


def fit_all(x: np.ndarray) -> list[DistFitResult]:
    """Ajusta las 8 distribuciones y devuelve resultados ordenados por mejor ajuste (menor D)."""
    results = []
    for name, fn in ALL_FITTERS.items():
        try:
            results.append(fn(np.asarray(x, dtype=float)))
        except Exception as exc:  # distribución no convergente para esta muestra
            results.append(
                DistFitResult(name, {"error": str(exc)}, np.nan, np.nan, False, lambda p: np.nan)
            )
    results.sort(key=lambda r: (np.isnan(r.ks_d), r.ks_d))
    return results
