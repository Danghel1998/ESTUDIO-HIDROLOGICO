"""Hietograma de diseño - Método del Bloque Alterno (Ven Te Chow et al.)."""

import numpy as np
import pandas as pd


def bloque_alterno(intensidad_fn, tr_years: float, duracion_total_h: float, dt_h: float = 1.0) -> pd.DataFrame:
    """Construye el hietograma de diseño por el método del bloque alterno.

    intensidad_fn(T, D_min) -> intensidad (mm/h)
    Devuelve un DataFrame con columnas: duracion_h, duracion_min, intensidad,
    prof_acumulada, prof_incremental, y el orden temporal reordenado
    (bloque_alterno_mm) con el pico al centro.
    """
    n = int(round(duracion_total_h / dt_h))
    duraciones_h = np.arange(1, n + 1) * dt_h
    duraciones_min = duraciones_h * 60.0

    intensidades = np.array([intensidad_fn(tr_years, d) for d in duraciones_min])
    prof_acum = intensidades * duraciones_h
    prof_incr = np.diff(prof_acum, prepend=0.0)

    # Reordenar en bloques alternos: el mayor incremento al centro, y los
    # demás decrecientes alternando hacia la derecha/izquierda.
    orden = np.argsort(prof_incr)[::-1]  # de mayor a menor incremento
    posiciones = np.zeros(n, dtype=int)
    centro = n // 2
    izq = centro - 1
    der = centro
    for i, idx in enumerate(orden):
        if i == 0:
            posiciones[idx] = der
            der += 1
        elif i % 2 == 1:
            posiciones[idx] = izq
            izq -= 1
        else:
            posiciones[idx] = der
            der += 1

    bloque = np.zeros(n)
    for idx, pos in enumerate(posiciones):
        bloque[pos] = prof_incr[idx]

    df = pd.DataFrame(
        {
            "duracion_h": duraciones_h,
            "duracion_min": duraciones_min,
            "intensidad_mm_h": intensidades,
            "prof_acumulada_mm": prof_acum,
            "prof_incremental_mm": prof_incr,
            "hietograma_mm": bloque,
        }
    )
    return df


# Distribución adimensional SCS Tipo II de 24 horas (razón acumulada P/P24 por
# hora), tal como la define el NRCS National Engineering Handbook Parte 630,
# Cap. 4 (fig. 4-31/4-36). Es la misma distribución que usa por defecto el
# meteorologic model "Hypothetical Storm" de HEC-HMS (Method: SCS Type 2),
# en vez del método del bloque alterno.
_SCS_TIPO_II_T_H = np.arange(0, 25, 1.0)
_SCS_TIPO_II_RATIO = np.array([
    0.000, 0.011, 0.022, 0.035, 0.048, 0.063, 0.080, 0.099, 0.120, 0.147, 0.181, 0.235,
    0.663, 0.772, 0.820, 0.854, 0.880, 0.902, 0.921, 0.938, 0.952, 0.965, 0.977, 0.989, 1.000,
])


def scs_tipo_ii_24h(punto_profundidad_mm: float, dt_h: float = 1.0) -> pd.DataFrame:
    """Hietograma de diseño de 24 horas según la distribución adimensional SCS
    Tipo II del NRCS (NEH-4), la misma que usa el método 'Hypothetical Storm'
    de HEC-HMS con Method=SCS Type 2. `punto_profundidad_mm` es la lámina
    puntual de 24h (equivalente al 'Point Depth' de HEC-HMS, antes de
    reducción por área)."""
    n = int(round(24.0 / dt_h))
    t = np.arange(0, n + 1) * dt_h
    ratio = np.interp(t, _SCS_TIPO_II_T_H, _SCS_TIPO_II_RATIO)
    prof_acum = ratio * punto_profundidad_mm
    prof_incr = np.diff(prof_acum)

    return pd.DataFrame(
        {
            "duracion_h": t[1:],
            "duracion_min": t[1:] * 60.0,
            "hietograma_mm": prof_incr,
            "prof_acumulada_mm": prof_acum[1:],
        }
    )


def refinar_hietograma(df: pd.DataFrame, dt_fino_h: float) -> pd.DataFrame:
    """Discretiza el hietograma de diseño (bloques de dt_h_calc, p.ej. 1h) a un
    paso de cómputo más fino (dt_fino_h), tal como el 'Time Interval' de las
    Control Specifications de HEC-HMS: dentro de cada bloque original se asume
    intensidad uniforme y se reparte la lámina en pasos de igual duración,
    conservando exactamente el volumen total de cada bloque.
    """
    dt_grueso_h = float(df["duracion_h"].iloc[0])
    n_sub = max(int(round(dt_grueso_h / dt_fino_h)), 1)
    dt_fino_h = dt_grueso_h / n_sub

    n_bloques = len(df)
    hietograma_fino = np.repeat(df["hietograma_mm"].to_numpy() / n_sub, n_sub)
    duraciones_h = (np.arange(1, n_bloques * n_sub + 1)) * dt_fino_h

    return pd.DataFrame(
        {
            "duracion_h": duraciones_h,
            "duracion_min": duraciones_h * 60.0,
            "hietograma_mm": hietograma_fino,
            "prof_acumulada_mm": np.cumsum(hietograma_fino),
        }
    )
