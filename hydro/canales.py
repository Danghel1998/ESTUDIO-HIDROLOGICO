"""Diseño hidráulico de canales (flujo uniforme, ecuación de Manning) — mismo
alcance que el software H Canales (M. Villón), usado para dimensionar cunetas,
canales y alcantarillas a partir del caudal de diseño.
"""

import numpy as np
from scipy.optimize import brentq

G = 9.81  # m/s2


# ---------------------------------------------------------------------------
# Geometría de la sección: cada una expone area(y), perimetro(y), espejo(y)
# ---------------------------------------------------------------------------

def _geom_trapezoidal(b: float, z: float):
    def area(y):
        return (b + z * y) * y

    def perimetro(y):
        return b + 2 * y * np.sqrt(1 + z ** 2)

    def espejo(y):
        return b + 2 * z * y

    return area, perimetro, espejo


def _geom_rectangular(b: float):
    return _geom_trapezoidal(b, 0.0)


def _geom_triangular(z: float):
    return _geom_trapezoidal(0.0, z)


def _geom_circular(d: float):
    def _theta(y):
        y = min(max(y, 1e-9), d - 1e-9)
        return 2 * np.arccos(1 - 2 * y / d)

    def area(y):
        th = _theta(y)
        return (d ** 2 / 8) * (th - np.sin(th))

    def perimetro(y):
        return d * _theta(y) / 2

    def espejo(y):
        th = _theta(y)
        return d * np.sin(th / 2)

    return area, perimetro, espejo


SECCIONES = {
    "Rectangular": _geom_rectangular,
    "Trapezoidal": _geom_trapezoidal,
    "Triangular": _geom_triangular,
    "Circular": _geom_circular,
}


def _geometria(seccion: str, **kw):
    if seccion == "Rectangular":
        return _geom_rectangular(kw["b"])
    if seccion == "Trapezoidal":
        return _geom_trapezoidal(kw["b"], kw["z"])
    if seccion == "Triangular":
        return _geom_triangular(kw["z"])
    if seccion == "Circular":
        return _geom_circular(kw["d"])
    raise ValueError(f"Sección no soportada: {seccion}")


def caudal_manning(y: float, n: float, s: float, seccion: str, **kw) -> float:
    """Q = (1/n) * A * R^(2/3) * S^(1/2)  (ecuación de Manning, unidades SI)."""
    area, perimetro, _ = _geometria(seccion, **kw)
    a = area(y)
    p = perimetro(y)
    if a <= 0 or p <= 0:
        return 0.0
    r = a / p
    return (1.0 / n) * a * r ** (2.0 / 3.0) * s ** 0.5


def tirante_normal(q: float, n: float, s: float, seccion: str, y_max: float = 50.0, **kw) -> float:
    """Resuelve el tirante normal yn tal que caudal_manning(yn) = q, por
    bisección (Q crece monótonamente con y)."""
    f = lambda y: caudal_manning(y, n, s, seccion, **kw) - q
    if f(y_max) < 0:
        raise ValueError("El tirante normal supera y_max; aumenta el rango de búsqueda.")
    return brentq(f, 1e-6, y_max)


def tirante_critico(q: float, seccion: str, y_max: float = 50.0, **kw) -> float:
    """Resuelve el tirante crítico yc tal que Q²·T / (g·A³) = 1 (Froude = 1)."""
    area, _, espejo = _geometria(seccion, **kw)

    def f(y):
        a = area(y)
        t = espejo(y)
        if a <= 0:
            return -1.0
        return (q ** 2 * t) / (G * a ** 3) - 1.0

    return brentq(f, 1e-6, y_max)


def numero_froude(q: float, y: float, seccion: str, **kw) -> float:
    area, _, espejo = _geometria(seccion, **kw)
    a = area(y)
    t = espejo(y)
    if a <= 0:
        return 0.0
    v = q / a
    d_h = a / t
    return v / np.sqrt(G * d_h)


def velocidad(q: float, y: float, seccion: str, **kw) -> float:
    area, _, _ = _geometria(seccion, **kw)
    a = area(y)
    return q / a if a > 0 else 0.0


def propiedades_seccion(y: float, seccion: str, **kw) -> dict:
    """Área hidráulica (A), perímetro mojado (P), espejo de agua (T) y radio
    hidráulico (R) para un tirante y dado — mismas salidas que H Canales."""
    area, perimetro, espejo = _geometria(seccion, **kw)
    a = area(y)
    p = perimetro(y)
    t = espejo(y)
    return {"area": a, "perimetro": p, "espejo": t, "radio_hidraulico": a / p if p > 0 else 0.0}


def energia_especifica(q: float, y: float, seccion: str, **kw) -> float:
    """E = y + V² / (2g)  (energía específica, m)."""
    v = velocidad(q, y, seccion, **kw)
    return y + v ** 2 / (2 * G)


# ---------------------------------------------------------------------------
# Tablas de referencia — Manual de Hidrología, Hidráulica y Drenaje del MTC
# (RD-20-2011-MTC-14), valores de la columna "normal" de la Tabla Nº 09
# (Coeficiente de Rugosidad de Manning, adaptada de Ven Te Chow).
# ---------------------------------------------------------------------------

MANNING_N = {
    "Concreto (tubo recto, libre de basuras)": 0.013,
    "Concreto (acabado/afinado)": 0.015,
    "Acero soldado": 0.012,
    "Metal corrugado (dren para aguas lluvias)": 0.024,
    "Mampostería de piedra con mortero": 0.032,
    "Tierra, recto y uniforme": 0.018,
    "Tierra con algo de vegetación": 0.025,
    "Tierra sinuoso con malezas y pasto": 0.035,
    "Roca, irregular": 0.040,
}

VELOCIDAD_MAX_MS = {
    "Arena fina / limo": 0.40,
    "Arcilla arenosa": 0.60,
    "Arcilla compacta / grava fina": 1.20,
    "Grava gruesa": 1.80,
    "Roca sana / concreto": 4.50,
}

VELOCIDAD_MIN_MS = 0.30  # m/s, mínima recomendada para evitar sedimentación


def borde_libre_alcantarilla(altura_o_diametro: float) -> float:
    """Manual MTC 4.1.1.3.6(b): el borde libre en alcantarillas debe ser como
    mínimo el 25% de la altura, diámetro o flecha de la estructura (no deben
    diseñarse a sección llena, para no incrementar el riesgo de obstrucción)."""
    return 0.25 * altura_o_diametro


BORDE_LIBRE_BADEN_MIN_M = 0.30
BORDE_LIBRE_BADEN_MAX_M = 0.50
BORDE_LIBRE_BADEN_DEFAULT_M = 0.40
# Manual MTC 4.1.1.4.1(e): borde libre del badén entre el nivel de flujo
# máximo esperado y la superficie de rodadura, recomendado entre 0.30 y 0.50 m.
