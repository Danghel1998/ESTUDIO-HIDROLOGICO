"""Extracción de series de precipitación desde PDFs (reportes SENAMHI en PDF).

SENAMHI entrega frecuentemente los registros de estación como PDF (tabla por
años/meses, o listados). Este módulo intenta extraer tablas estructuradas y,
si no las encuentra, cae a un parseo de texto por expresiones regulares.
"""

import re

import pandas as pd
import pdfplumber

MESES_TOKENS = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "set", "sep", "oct", "nov", "dic"]


ESTRATEGIAS_TABLA = {
    "Automática (detecta líneas/bordes)": None,
    "Por texto (para tablas sin bordes visibles)": {
        "vertical_strategy": "text",
        "horizontal_strategy": "text",
    },
}


def extraer_tablas(archivo, table_settings: dict | None = None) -> list[pd.DataFrame]:
    """Extrae todas las tablas detectadas en el PDF, una por cada tabla/página.

    `archivo` es un objeto tipo archivo (p.ej. el resultado de st.file_uploader).
    `table_settings` permite forzar la estrategia de detección de columnas de
    pdfplumber (útil cuando la tabla no tiene bordes/líneas visibles y la
    detección automática desalinea celdas).
    """
    tablas = []
    with pdfplumber.open(archivo) as pdf:
        for i, page in enumerate(pdf.pages):
            extraidas = page.extract_tables(table_settings) if table_settings else page.extract_tables()
            for t in extraidas:
                if not t or len(t) < 2:
                    continue
                header, *rows = t
                header = [str(h).strip() if h else f"col_{j}" for j, h in enumerate(header)]
                df = pd.DataFrame(rows, columns=header)
                df.attrs["pagina"] = i + 1
                tablas.append(df)
    return tablas


def combinar_tablas(tablas: list[pd.DataFrame]) -> pd.DataFrame:
    """Combina en una sola tabla las tablas extraídas de distintas páginas del
    PDF, para el caso (muy común en SENAMHI) en que la serie de años viene
    partida en varias páginas con la misma estructura de columnas.

    Se agrupan las tablas por número de columnas (el grupo mayoritario gana),
    se alinean por posición de columna (usando los encabezados de la primera
    tabla del grupo como referencia) y se concatenan las filas.
    """
    if not tablas:
        return pd.DataFrame()
    if len(tablas) == 1:
        return tablas[0]

    n_cols = pd.Series([t.shape[1] for t in tablas]).mode().iloc[0]
    grupo = [t for t in tablas if t.shape[1] == n_cols]
    referencia = grupo[0].columns.tolist()

    partes = []
    for t in grupo:
        t2 = t.copy()
        t2.columns = referencia
        partes.append(t2)

    combinada = pd.concat(partes, ignore_index=True)
    # Descarta filas que sean en realidad encabezados repetidos (p.ej. "AÑO" en
    # la columna de año cuando una tabla nueva reinicia con su propio header).
    if referencia:
        primera_col = referencia[0]
        combinada = combinada[
            ~combinada[primera_col].astype(str).str.strip().str.lower().isin(
                [str(c).strip().lower() for c in referencia]
            )
        ]
    return combinada.reset_index(drop=True)


def extraer_texto(archivo) -> str:
    with pdfplumber.open(archivo) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


def parsear_pares_anio_valor(texto: str) -> pd.DataFrame:
    """Fallback: busca en el texto plano patrones 'AÑO ... VALOR' del tipo
    '1998   38.90' o 'Año 1998: 38.9 mm', devolviendo un DataFrame Año/P24h.
    Útil cuando el PDF no tiene tablas extraíbles (texto libre o escaneado)."""
    patron = re.compile(r"\b(19|20)\d{2}\b[^\d\-]{0,15}(\d{1,3}(?:[.,]\d{1,2})?)")
    filas = []
    for m in patron.finditer(texto):
        anio = int(texto[m.start():m.start() + 4])
        valor_str = m.group(2).replace(",", ".")
        try:
            valor = float(valor_str)
        except ValueError:
            continue
        if 1900 <= anio <= 2100 and 0 <= valor <= 500:
            filas.append((anio, valor))
    if not filas:
        return pd.DataFrame(columns=["Año", "P24h"])
    df = pd.DataFrame(filas, columns=["Año", "P24h"]).drop_duplicates(subset="Año", keep="first")
    return df.sort_values("Año").reset_index(drop=True)


def es_formato_mensual(df: pd.DataFrame) -> bool:
    cols = [str(c).strip().lower() for c in df.columns]
    hits = sum(1 for c in cols if any(c.startswith(m) for m in MESES_TOKENS))
    return hits >= 6
