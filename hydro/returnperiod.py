"""Período de retorno de diseño según riesgo admisible y vida útil (Manual MTC)."""

import numpy as np

# Riesgo admisible (%) y vida útil (años) recomendados por el Manual de
# Hidrología, Hidráulica y Drenaje del MTC, Tabla "Riesgo admisible y vida
# útil según el tipo de estructura".
OBRAS_MTC = {
    "Puentes": {"riesgo": 0.25, "vida_util": 40},
    "Alcantarillas de paso de quebradas importantes y badenes": {"riesgo": 0.30, "vida_util": 25},
    "Alcantarillas de paso quebradas menores y descarga de agua de cunetas": {
        "riesgo": 0.35, "vida_util": 15
    },
    "Drenaje de la plataforma (a nivel longitudinal)": {"riesgo": 0.40, "vida_util": 15},
    "Subdrenes": {"riesgo": 0.40, "vida_util": 15},
    "Defensas ribereñas": {"riesgo": 0.25, "vida_util": 40},
}


def periodo_retorno(riesgo: float, vida_util: float) -> float:
    """T = 1 / (1 - (1-R)^(1/n))"""
    return 1.0 / (1.0 - (1.0 - riesgo) ** (1.0 / vida_util))


def riesgo_falla(tr: float, vida_util: float) -> float:
    """R = 1 - (1 - 1/T)^n"""
    return 1.0 - (1.0 - 1.0 / tr) ** vida_util
