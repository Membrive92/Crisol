"""Tests del parser CSV/XLSX (lógica pura, sin DB)."""

from __future__ import annotations

import io

import pytest
from openpyxl import Workbook

from app.modules.imports.parser import (
    ParseError,
    detect_format,
    parse_csv,
    parse_xlsx,
)


def test_detect_csv_by_extension() -> None:
    assert detect_format("file.csv", "application/octet-stream") == "csv"


def test_detect_xlsx_by_extension() -> None:
    assert detect_format("file.XLSX", None) == "xlsx"


def test_detect_unknown_format_raises() -> None:
    with pytest.raises(ParseError):
        detect_format("file.pdf", "application/pdf")


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
