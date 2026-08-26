"""Método Racional y Racional Modificado (Témez) - Manual MTC."""

import numpy as np

# Coeficientes de escorrentía de referencia (Manual MTC) según cobertura y
# pendiente del terreno. Valores orientativos para selección rápida.
COEFICIENTES_ESCORRENTIA = {
    "Pavimento / superficie impermeable": 0.90,
    "Suelo semipermeable, sin vegetación (crítico)": 0.50,
    "Suelo permeable, cultivos": 0.30,
    "Bosque / vegetación densa, pendiente suave": 0.15,
    "Pastizales, pendiente moderada": 0.25,
}


def metodo_racional(c: float, intensidad_mm_h: float, area_km2: float) -> float:
    """Q = 0.278 * C * I * A  (m3/s)"""
    return 0.278 * c * intensidad_mm_h * area_km2


def coef_uniformidad_temez(tc_h: float) -> float:
    """K = 1 + Tc^1.25 / (Tc^1.25 + 14)"""
    return 1 + (tc_h ** 1.25) / (tc_h ** 1.25 + 14)


def factor_reductor_temez(area_km2: float) -> float:
    """kA: factor de simultaneidad/reducción por área (Témez)."""
    return 1 - (np.log10(area_km2) / 15) if area_km2 > 1 else 1.0


def metodo_racional_modificado(c: float, intensidad_mm_h: float, area_km2: float, tc_h: float) -> dict:
    k = coef_uniformidad_temez(tc_h)
    q = 0.278 * c * intensidad_mm_h * area_km2 * k
    return {"K": k, "Q": q}
