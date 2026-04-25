"""Parsers de CSV y XLSX para importación de transacciones.

Devuelven una secuencia de filas como diccionarios `{columna: valor}`.
La detección de formato es por extensión y mime-type. Los valores se
normalizan a `str` para que la lógica de validación posterior los
parsee homogéneamente.
"""

from __future__ import annotations

import csv
import io
from typing import IO, Any

from openpyxl import load_workbook

# Mime-types aceptados. Algunos clientes envían `application/octet-stream`,
# en cuyo caso se decide por extensión.
CSV_MIME_TYPES = {
    "text/csv",
    "application/csv",
    "application/vnd.ms-excel",  # algunos navegadores lo etiquetan así
}
XLSX_MIME_TYPES = {
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel.sheet",
}


class ParseError(Exception):
    """Error al parsear un fichero subido."""


def detect_format(filename: str, content_type: str | None) -> str:
    """Devuelve `csv` o `xlsx`, o lanza `ParseError` si no se reconoce."""
    name = filename.lower()
    if name.endswith(".csv"):
        return "csv"
    if name.endswith(".xlsx"):
        return "xlsx"
    if content_type in CSV_MIME_TYPES:
        return "csv"
    if content_type in XLSX_MIME_TYPES:
        return "xlsx"
    raise ParseError(f"Formato no soportado: {filename!r} (content-type={content_type!r})")


def parse_csv(payload: bytes) -> list[dict[str, str]]:
    """Parsea un CSV. Detecta delimitador (`,`, `;`, `\\t`)."""
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = payload.decode("latin-1")
        except UnicodeDecodeError as e:
            raise ParseError("No se pudo decodificar el fichero (UTF-8 ni Latin-1)") from e

    sample = text[:2048]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel

    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    if not reader.fieldnames:
        raise ParseError("El CSV no tiene cabecera")

    rows: list[dict[str, str]] = []
    for raw in reader:
        row = {(k or "").strip(): (v or "").strip() for k, v in raw.items() if k is not None}
        rows.append(row)
    return rows


def parse_xlsx(payload: bytes) -> list[dict[str, str]]:
    """Parsea la primera hoja de un XLSX."""
    try:
        workbook = load_workbook(io.BytesIO(payload), read_only=True, data_only=True)
    except Exception as e:
        raise ParseError(f"XLSX inválido: {e}") from e

    sheet = workbook.active
    if sheet is None:
        raise ParseError("El XLSX no contiene hojas")

    iterator = sheet.iter_rows(values_only=True)
    try:
        header_row = next(iterator)
    except StopIteration as e:
        raise ParseError("El XLSX está vacío") from e

    headers = [_stringify(cell).strip() for cell in header_row]
    if not any(headers):
        raise ParseError("El XLSX no tiene cabecera")

    rows: list[dict[str, str]] = []
    for raw_row in iterator:
        if all(cell is None or str(cell).strip() == "" for cell in raw_row):
            continue
        row = {
            headers[i]: _stringify(value).strip()
            for i, value in enumerate(raw_row)
            if i < len(headers) and headers[i]
        }
        rows.append(row)
    return rows


def parse_file(payload: bytes, filename: str, content_type: str | None) -> list[dict[str, str]]:
    """Parsea según formato detectado."""
    fmt = detect_format(filename, content_type)
    if fmt == "csv":
        return parse_csv(payload)
    return parse_xlsx(payload)


def parse_stream(stream: IO[bytes], filename: str, content_type: str | None) -> list[dict[str, str]]:
    """Variante para streams ya abiertos (p.ej. `UploadFile`)."""
    return parse_file(stream.read(), filename, content_type)


def _stringify(value: Any) -> str:
    """Convierte un valor de openpyxl a string preservando ISO en datetimes."""
    if value is None:
        return ""
    # openpyxl ya devuelve datetime/date/Decimal/int/float — basta str()
    return str(value)
