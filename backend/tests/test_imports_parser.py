"""Tests del parser CSV/XLSX/PDF (lógica pura, sin DB)."""

from __future__ import annotations

import io

import pytest
from openpyxl import Workbook
from reportlab.lib import colors as rl_colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import PageBreak, SimpleDocTemplate, Table, TableStyle

from app.modules.personal_finance.imports.parser import (
    ParseError,
    detect_format,
    parse_csv,
    parse_pdf,
    parse_xlsx,
)


def _build_pdf(pages: list[list[list[str]]]) -> bytes:
    """Genera un PDF con una `Table` por página (cada página = una tabla).

    Las celdas llevan borde visible: pdfplumber detecta tablas por los
    trazos de línea, no por la estructura lógica.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    style = TableStyle([("GRID", (0, 0), (-1, -1), 0.5, rl_colors.black)])
    elements: list[object] = []
    for idx, table_rows in enumerate(pages):
        table = Table(table_rows)
        table.setStyle(style)
        elements.append(table)
        if idx < len(pages) - 1:
            elements.append(PageBreak())
    doc.build(elements)
    return buffer.getvalue()


def test_detect_csv_by_extension() -> None:
    assert detect_format("file.csv", "application/octet-stream") == "csv"


def test_detect_xlsx_by_extension() -> None:
    assert detect_format("file.XLSX", None) == "xlsx"


def test_detect_pdf_by_extension() -> None:
    assert detect_format("statement.PDF", None) == "pdf"


def test_detect_pdf_by_mime() -> None:
    assert detect_format("file.bin", "application/pdf") == "pdf"


def test_detect_unknown_format_raises() -> None:
    with pytest.raises(ParseError):
        detect_format("file.txt", "text/plain")


def test_parse_csv_basic_comma() -> None:
    payload = b"date,amount,description\n2026-04-15,25.50,Coffee\n2026-04-16,10.00,Lunch\n"
    rows = parse_csv(payload)
    assert len(rows) == 2
    assert rows[0] == {"date": "2026-04-15", "amount": "25.50", "description": "Coffee"}


def test_parse_csv_semicolon_delimiter() -> None:
    payload = b"Fecha;Importe\n2026-04-15;25,50\n"
    rows = parse_csv(payload)
    assert rows == [{"Fecha": "2026-04-15", "Importe": "25,50"}]


def test_parse_csv_utf8_bom() -> None:
    payload = b"\xef\xbb\xbfdate,amount\n2026-04-15,10.00\n"
    rows = parse_csv(payload)
    assert rows[0]["date"] == "2026-04-15"


def test_parse_csv_empty_raises() -> None:
    with pytest.raises(ParseError):
        parse_csv(b"")


def test_parse_xlsx_basic() -> None:
    wb = Workbook()
    sheet = wb.active
    assert sheet is not None
    sheet.append(["Date", "Amount", "Description"])
    sheet.append(["2026-04-15", 25.5, "Coffee"])
    sheet.append(["2026-04-16", 10.0, "Lunch"])
    buf = io.BytesIO()
    wb.save(buf)

    rows = parse_xlsx(buf.getvalue())
    assert len(rows) == 2
    assert rows[0]["Date"] == "2026-04-15"
    assert rows[0]["Description"] == "Coffee"


def test_parse_xlsx_skips_blank_rows() -> None:
    wb = Workbook()
    sheet = wb.active
    assert sheet is not None
    sheet.append(["Date", "Amount"])
    sheet.append(["2026-04-15", 10])
    sheet.append([None, None])
    sheet.append(["2026-04-16", 20])
    buf = io.BytesIO()
    wb.save(buf)

    rows = parse_xlsx(buf.getvalue())
    assert len(rows) == 2


def test_parse_xlsx_invalid_bytes_raises() -> None:
    with pytest.raises(ParseError):
        parse_xlsx(b"not an xlsx file")


def test_parse_pdf_basic_table() -> None:
    payload = _build_pdf(
        [
            [
                ["Fecha", "Importe", "Concepto"],
                ["2026-04-15", "25.50", "Coffee"],
                ["2026-04-16", "10.00", "Lunch"],
            ]
        ]
    )
    rows = parse_pdf(payload)
    assert len(rows) == 2
    assert rows[0]["Fecha"] == "2026-04-15"
    assert rows[0]["Importe"] == "25.50"
    assert rows[0]["Concepto"] == "Coffee"


def test_parse_pdf_multipage_concatenates_and_skips_repeated_header() -> None:
    header = ["Fecha", "Importe"]
    payload = _build_pdf(
        [
            [header, ["2026-04-15", "10"], ["2026-04-16", "20"]],
            [header, ["2026-04-17", "30"]],
        ]
    )
    rows = parse_pdf(payload)
    assert [r["Fecha"] for r in rows] == ["2026-04-15", "2026-04-16", "2026-04-17"]


def test_parse_pdf_no_tables_raises() -> None:
    """PDFs sin tablas (texto suelto) no deben pasar el parser."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    style = getSampleStyleSheet()["BodyText"]
    from reportlab.platypus import Paragraph

    doc.build([Paragraph("Sólo texto, sin tablas.", style)])
    with pytest.raises(ParseError):
        parse_pdf(buffer.getvalue())


def test_parse_pdf_invalid_bytes_raises() -> None:
    with pytest.raises(ParseError):
        parse_pdf(b"not a pdf")
