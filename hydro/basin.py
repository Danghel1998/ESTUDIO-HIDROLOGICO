"""Parámetros geomorfológicos e hidrológicos de cuenca (Manual MTC)."""

import numpy as np


def ancho_medio(area_km2: float, longitud_cauce_km: float) -> float:
    return area_km2 / longitud_cauce_km


def coef_compacidad(perimetro_km: float, area_km2: float) -> float:
    """Kc (Gravelius) = 0.28 * P / sqrt(A)"""
    return 0.28 * perimetro_km / np.sqrt(area_km2)


def factor_forma(area_km2: float, longitud_cauce_km: float) -> float:
    return area_km2 / (longitud_cauce_km ** 2)


def pendiente_cauce(delta_h_m: float, longitud_m: float) -> float:
    return delta_h_m / longitud_m


# --- Tiempo de concentración (Tc en horas) ---------------------------------

def tc_kirpich(long_km: float, s_m_m: float) -> float:
    return 0.06628 * (long_km ** 0.77) * (s_m_m ** -0.385)


def tc_hathaway(long_km: float, s_m_m: float, n_rugosidad: float = 0.5) -> float:
    return (0.606 * (long_km * n_rugosidad) ** 0.467) / (s_m_m ** 0.234)


def tc_bransby_williams(area_km2: float, long_km: float, s_m_m: float) -> float:
    """Tc = 0.2433 * L / (A^0.1 * s^0.2)  [Tc horas, L km, A km2, s m/m]"""
    return 0.2433 * long_km / (area_km2 ** 0.1 * s_m_m ** 0.2)


def tc_us_corps(long_km: float, s_m_m: float) -> float:
    return 0.3 * (long_km ** 0.76) / (s_m_m ** 0.19)


TC_METODOS = {
    "Kirpich": tc_kirpich,
    "Hathaway": tc_hathaway,
    "Bransby-Williams": tc_bransby_williams,
    "US Corps of Engineers": tc_us_corps,
}


def tiempo_concentracion_todos(area_km2, long_km, s_m_m) -> dict[str, float]:
    return {
        "Kirpich": tc_kirpich(long_km, s_m_m),
        "Hathaway": tc_hathaway(long_km, s_m_m),
        "Bransby-Williams": tc_bransby_williams(area_km2, long_km, s_m_m),
        "US Corps of Engineers": tc_us_corps(long_km, s_m_m),
    }


def clasificacion_cuenca(area_km2: float) -> str:
    if area_km2 <= 100:
        return "Microcuenca"
    if area_km2 <= 1000:
        return "Cuenca pequeña"
    if area_km2 <= 5000:
        return "Cuenca mediana"
    if area_km2 <= 10000:
        return "Cuenca grande"
    return "Cuenca muy grande"
