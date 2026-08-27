"""Diseño hidráulico de canales (flujo uniforme, ecuación de Manning) — mismo
alcance que el software H Canales (M. Villón), usado para dimensionar cunetas,
canales y alcantarillas a partir del caudal de diseño.
"""

import numpy as np
from scipy.integrate import quad
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


def pendiente_friccion(q: float, y: float, n: float, seccion: str, **kw) -> float:
    """Se = (Q·n / (A·R^(2/3)))²  — pendiente de fricción (ecuación de
    Manning despejada), usada en el cálculo de curvas de remanso."""
    prop = propiedades_seccion(y, seccion, **kw)
    a, p = prop["area"], prop["perimetro"]
    if a <= 0 or p <= 0:
        return 0.0
    r = a / p
    v = q / a
    return (v * n / r ** (2.0 / 3.0)) ** 2


# ---------------------------------------------------------------------------
# Remanso (flujo gradualmente variado) — métodos que no requieren tablas o
# funciones de flujo variado tabuladas (Bakhmeteff/Bresse quedan pendientes).
# ---------------------------------------------------------------------------

def perfil_remanso_directo_por_tramos(q: float, n: float, s: float, seccion: str, y1: float, y2: float, nt: int, **kw) -> list:
    """Método directo por tramos (standard step): divide [y1, y2] en `nt`
    incrementos iguales de tirante y calcula Δx en cada uno por balance de
    energía específica, dE/dx = So - Se → Δx = ΔE / (So - Se_promedio)."""
    dy = (y2 - y1) / nt
    filas = []

    def _fila(y, x):
        prop = propiedades_seccion(y, seccion, **kw)
        v = velocidad(q, y, seccion, **kw)
        e = energia_especifica(q, y, seccion, **kw)
        se = pendiente_friccion(q, y, n, seccion, **kw)
        return prop, v, e, se

    prop, v, e, se = _fila(y1, 0.0)
    x = 0.0
    filas.append({
        "y": y1, "A": prop["area"], "P": prop["perimetro"], "R": prop["radio_hidraulico"],
        "R23": prop["radio_hidraulico"] ** (2 / 3), "v": v, "v2_2g": v ** 2 / (2 * G), "E": e,
        "deltaE": 0.0, "Se": se, "SeP": se, "So_SeP": s - se, "deltax": 0.0, "x": x,
    })
    for _ in range(nt):
        y_sig = filas[-1]["y"] + dy
        prop_sig, v_sig, e_sig, se_sig = _fila(y_sig, None)
        delta_e = e_sig - filas[-1]["E"]
        se_prom = (filas[-1]["Se"] + se_sig) / 2
        so_sep = s - se_prom
        delta_x = delta_e / so_sep if abs(so_sep) > 1e-12 else float("nan")
        x += delta_x
        filas.append({
            "y": y_sig, "A": prop_sig["area"], "P": prop_sig["perimetro"], "R": prop_sig["radio_hidraulico"],
            "R23": prop_sig["radio_hidraulico"] ** (2 / 3), "v": v_sig, "v2_2g": v_sig ** 2 / (2 * G), "E": e_sig,
            "deltaE": delta_e, "Se": se_sig, "SeP": se_prom, "So_SeP": so_sep, "deltax": delta_x, "x": x,
        })
    return filas


def perfil_remanso_integracion_grafica(q: float, n: float, s: float, seccion: str, y1: float, y2: float, nt: int, **kw) -> list:
    """Método de integración gráfica: evalúa f(y) = (1 - Q²T/(gA³)) / (So-Se)
    en `nt+1` tirantes entre y1 y y2, e integra con la regla del trapecio
    (dx/dy = f(y), misma ecuación diferencial del flujo gradualmente variado)."""
    dy = (y2 - y1) / nt
    filas = []
    x = 0.0
    f_prev = None
    for i in range(nt + 1):
        y = y1 + i * dy
        prop = propiedades_seccion(y, seccion, **kw)
        a, p_, t = prop["area"], prop["perimetro"], prop["espejo"]
        v = velocidad(q, y, seccion, **kw)
        se = pendiente_friccion(q, y, n, seccion, **kw)
        uno_menos_fr2 = 1 - (q ** 2 * t) / (G * a ** 3)
        so_se = s - se
        f_y = uno_menos_fr2 / so_se if abs(so_se) > 1e-12 else float("nan")
        delta_x = 0.0
        if f_prev is not None:
            delta_x = (f_prev + f_y) / 2 * dy
            x += delta_x
        filas.append({
            "y": y, "A": a, "P": p_, "R": prop["radio_hidraulico"], "T": t, "v": v, "Se": se,
            "uno_menos_Q2T_gA3": uno_menos_fr2, "So_Se": so_se, "f_y": f_y, "deltax": delta_x, "x": x,
        })
        f_prev = f_y
    return filas


def _raiz_cercana(f, y0: float, lo_bound: float, hi_bound: float, y_max_iter: int = 60):
    """Busca una raíz de f cerca de y0, expandiendo una ventana centrada en
    y0 (en vez de bisección directa en todo el rango): cerca del tirante
    crítico el residuo del método de tramos fijos puede no ser monótono y
    tener más de una raíz matemática, y la físicamente válida es la más
    cercana al tirante actual."""
    delta = max(abs(y0) * 0.05, 1e-4)
    for _ in range(y_max_iter):
        lo = max(lo_bound, y0 - delta)
        hi = min(hi_bound, y0 + delta)
        if hi > lo:
            flo, fhi = f(lo), f(hi)
            if flo * fhi < 0:
                return brentq(f, lo, hi)
        if lo <= lo_bound and hi >= hi_bound:
            break
        delta *= 1.6
    raise ValueError("No se encontró un tirante siguiente válido (paso Δx demasiado grande para este tramo).")


def perfil_remanso_tramos_fijos(q: float, n: float, s: float, seccion: str, yi: float, nt: int, dx: float, y_max: float = 50.0, **kw) -> list:
    """Método de tramos fijos: a partir de `yi`, marcha `nt` pasos de
    longitud fija `dx`, resolviendo en cada uno el tirante siguiente por
    balance de energía específica (implícito: Se_promedio depende del
    tirante buscado, se resuelve numéricamente)."""
    yc = tirante_critico(q, seccion, y_max=y_max, **kw)
    filas = [{"x": 0.0, "y": yi}]
    y = yi
    x = 0.0
    for _ in range(nt):
        e_i = energia_especifica(q, y, seccion, **kw)
        se_i = pendiente_friccion(q, y, n, seccion, **kw)

        def _residuo(y_sig):
            e_sig = energia_especifica(q, y_sig, seccion, **kw)
            se_sig = pendiente_friccion(q, y_sig, n, seccion, **kw)
            se_prom = (se_i + se_sig) / 2
            return (e_sig - e_i) - (s - se_prom) * dx

        # El siguiente tirante se busca del mismo lado del crítico que el
        # actual (sub o supercrítico), para no saltar de rama por error.
        lo_bound, hi_bound = (yc + 1e-9, y_max) if y >= yc else (1e-9, yc - 1e-9)
        try:
            y_sig = _raiz_cercana(_residuo, y, lo_bound, hi_bound)
        except ValueError:
            break
        x += dx
        filas.append({"x": x, "y": y_sig})
        y = y_sig
    return filas


# ---------------------------------------------------------------------------
# Resalto hidráulico — función de momentum (M = Q²/(g·A) + primer momento del
# área respecto a la superficie libre), válida para cualquier sección al
# integrar el espejo de agua T(η); para trapezoidal/rectangular equivale a
# las fórmulas cerradas usuales, y evita tener que derivar una por sección.
# ---------------------------------------------------------------------------

def _primer_momento(y: float, seccion: str, **kw) -> float:
    """∫₀^y (y-η)·T(η) dη = A(y)·ȳ(y), con ȳ la profundidad del centroide
    del área mojada medida desde la superficie libre."""
    if y <= 0:
        return 0.0
    _, _, espejo = _geometria(seccion, **kw)
    valor, _ = quad(lambda eta: (y - eta) * espejo(eta), 0, y)
    return valor


def funcion_momentum(q: float, y: float, seccion: str, **kw) -> float:
    area, _, _ = _geometria(seccion, **kw)
    a = area(y)
    if a <= 0:
        return float("inf")
    return q ** 2 / (G * a) + _primer_momento(y, seccion, **kw)


def tirante_conjugado(q: float, y1: float, seccion: str, y_max: float = 50.0, **kw) -> float:
    """Resuelve el tirante conjugado (secuente) y2 tal que M(y1) = M(y2),
    condición de igualdad de momentum antes y después del resalto hidráulico."""
    yc = tirante_critico(q, seccion, y_max=y_max, **kw)
    m1 = funcion_momentum(q, y1, seccion, **kw)
    f = lambda y: funcion_momentum(q, y, seccion, **kw) - m1
    lo = yc if y1 < yc else 1e-6
    hi = y_max if y1 < yc else yc
    return brentq(f, lo, hi)


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
