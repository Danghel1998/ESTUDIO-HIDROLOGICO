"""Catálogo de estaciones hidrometeorológicas de SENAMHI.

Los datos (nombre, código, tipo, estado y coordenadas) se extrajeron del mapa
público de SENAMHI (https://www.senamhi.gob.pe/mapas/mapa-estaciones-2/) y se
guardan como copia local estática en ``hydro/data/senamhi_estaciones.csv`` —
SENAMHI no ofrece una API pública para esta información.
"""

from pathlib import Path

import pandas as pd

_CSV_PATH = Path(__file__).resolve().parent / "data" / "senamhi_estaciones.csv"

CATEGORIAS = {
    "CO": "Convencional - Climatológica Ordinaria",
    "CP": "Convencional - Climatológica Principal",
    "PLU": "Convencional - Pluviométrica",
    "EMA": "Automática - Estación Meteorológica Automática",
    "HLM": "Hidrológica - Limnimétrica",
    "HLG": "Hidrológica - Limnigráfica",
}

ESTADOS = {
    "REAL": "Tiempo real",
    "DIFERIDO": "Tiempo diferido",
    "AUTOMATICA": "Automática",
}


def cargar_estaciones() -> pd.DataFrame:
    """Devuelve el catálogo completo de estaciones SENAMHI."""
    df = pd.read_csv(_CSV_PATH, dtype={"codigo": str, "codigo_antiguo": str})
    df["codigo_antiguo"] = df["codigo_antiguo"].fillna("")
    df["categoria_desc"] = df["categoria"].map(CATEGORIAS).fillna(df["categoria"])
    df["estado_desc"] = df["estado"].map(ESTADOS).fillna(df["estado"])
    return df
