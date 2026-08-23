"""Tests del parser CSV/XLSX/PDF (lógica pura, sin DB)."""

from __future__ import annotations

import io
import uuid
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from openpyxl import Workbook
from reportlab.lib import colors as rl_colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import PageBreak, SimpleDocTemplate, Table, TableStyle

from app.modules.personal_finance.imports.parser import (
    ParseError,
    SmartParseAmbiguousError,
    _classify_columns,
    _normalize_date,
    detect_format,
    parse_csv,
    parse_pdf,
    parse_pdf_smart,
    parse_xlsx,
)
from app.modules.personal_finance.imports.service import (
    ParsedRow,
    _parse_amount_signed,
    _parse_balance,
    _pick_balance_anchor,
    _RowError,
)
from app.modules.personal_finance.transactions.models import TransactionFlow


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


# ─────────────────────────────────────────────────────────────────────────────
# parse_pdf_smart: heurística sobre extractos bancarios reales (varias tablas)
# ─────────────────────────────────────────────────────────────────────────────


def _bank_statement_pdf() -> bytes:
    """PDF de prueba con la estructura del PDF del usuario:
    Resumen (2 cols, totales) + Desglose por categoría (2 cols) + Listado de
    movimientos (5 cols con cabecera tipo 'F. Operac., Concepto, Detalle,
    Importe (EUR)').
    """
    return _build_pdf(
        [
            # Página 1: dos tablas pequeñas (resumen + desglose) y la cabecera
            # del listado. ReportLab pone una tabla por página en el helper —
            # las metemos cada una en su propia "página" (separadas por
            # PageBreak en _build_pdf).
            [
                ["Concepto", "Importe (EUR)"],
                ["Total ingresos", "12.052,10"],
                ["Total gastos", "-11.962,30"],
                ["Balance neto", "89,80"],
            ],
            [
                ["Categoria", "Total (EUR)"],
                ["ADEUDOS", "-4.903,06"],
                ["TARJETA - RESTAURANTES", "-435,41"],
                ["NOMINA", "2.491,65"],
            ],
            [
                ["F. Operac.", "F. Contab.", "Concepto", "Detalle", "Importe (EUR)"],
                [
                    "25/02",
                    "02/03",
                    "PAGO TARJETA - RESTAURANTES",
                    "PAYPAL *PAGO 3 PLAZOS",
                    "-29,66",
                ],
                [
                    "28/02",
                    "02/03",
                    "PAGO CON TARJETA EN GASOLINERAS",
                    "E.S. LA HITA TORRE PACHECO",
                    "-40,00",
                ],
                ["13/03", "13/03", "ABONO DE NOMINA", "DNV GREENPOWERMONITOR", "2.491,65"],
                ["13/03", "13/03", "TRANSFERENCIAS", "JOSE A MEMBRIVE", "-900,00"],
                ["01/04", "02/04", "BIZUM RECIBIDO", "cena", "15,50"],
            ],
        ]
    )


def test_parse_pdf_smart_detects_transactions_table() -> None:
    rows, _header = parse_pdf_smart(_bank_statement_pdf())
    # 5 transacciones reales; los totales del resumen y el desglose se ignoran.
    assert len(rows) == 5
    # Todas las filas usan keys fijas (PHASE-39 añade `statement_balance`).
    for r in rows:
        assert set(r.keys()) == {
            "amount",
            "occurred_at",
            "description",
            "category_name",
            "statement_balance",
        }
    # Ningún total del resumen se cuela como transacción.
    descriptions = [r["description"] for r in rows]
    assert "Total ingresos" not in descriptions
    assert "ADEUDOS" not in descriptions


def test_parse_pdf_smart_uses_detalle_as_description_and_concepto_as_category() -> None:
    rows, _header = parse_pdf_smart(_bank_statement_pdf())
    first = rows[0]
    assert first["description"] == "PAYPAL *PAGO 3 PLAZOS"
    assert first["category_name"] == "PAGO TARJETA - RESTAURANTES"
    assert first["amount"] == "-29,66"


def test_parse_pdf_smart_infers_year_for_ddmm_dates() -> None:
    """Fechas DD/MM se rellenan con el año actual cuando no hay periodo
    explícito en el PDF (cubierto por el fixture)."""
    rows, _header = parse_pdf_smart(_bank_statement_pdf())
    from datetime import date

    expected_year = str(date.today().year)
    for r in rows:
        assert r["occurred_at"].endswith(f"/{expected_year}"), r["occurred_at"]


def test_parse_pdf_smart_picks_f_operac_over_f_contab() -> None:
    """Si hay dos columnas de fecha, la primera (F. Operac.) gana."""
    rows, _header = parse_pdf_smart(_bank_statement_pdf())
    # 25/02 (operac) vs 02/03 (contab): debe ganar la primera.
    assert rows[0]["occurred_at"].startswith("25/02/")


def test_parse_pdf_smart_picks_importe_over_saldo() -> None:
    """Bug histórico: con cabeceras `[..., "Importe", "Saldo"]` la
    heurística debe quedarse con el importe de la transacción, NO con
    el saldo acumulado. Dato real del usuario: -60,00 € (importe) vs
    3.317,98 € (saldo) → tiene que elegir el primero."""
    payload = _build_pdf(
        [
            [
                ["Fecha", "Concepto", "Importe", "Saldo"],
                ["30/01/2026", "TRANSFERENCIA Wi", "-60,00 €", "3.317,98 €"],
                ["30/01/2026", "PAYPAL GOOGLE", "-5,17 €", "3.312,81 €"],
                ["30/01/2026", "PAGO TARJETA", "-12,49 €", "3.300,32 €"],
            ]
        ]
    )
    rows, _header = parse_pdf_smart(payload)
    assert len(rows) == 3
    # Los importes deben ser los reales (con signo) — no los saldos.
    amounts = [r["amount"] for r in rows]
    assert "-60,00 €" in amounts[0]
    assert "3.317,98" not in amounts[0]


def test_parse_pdf_smart_ambiguous_when_no_transactions_table() -> None:
    """PDF con solo tablas de resumen (sin cabeceras tipo fecha+importe
    suficientes) → SmartParseAmbiguousError, el caller cae al parser legacy."""
    payload = _build_pdf(
        [
            [
                ["Etiqueta", "Valor"],
                ["foo", "1"],
                ["bar", "2"],
            ],
        ]
    )
    with pytest.raises(SmartParseAmbiguousError):
        parse_pdf_smart(payload)


# ─────────────────────────────────────────────────────────────────────────────
# _parse_amount_signed: importe con formatos europeos, símbolos de moneda, signos
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("25.50", Decimal("25.50")),
        ("25,50", Decimal("25.50")),
        ("1.234,56", Decimal("1234.56")),
        ("1,234.56", Decimal("1234.56")),
        # Signos
        ("-29,66", Decimal("29.66")),
        ("+10.00", Decimal("10.00")),
        # Símbolos de moneda y espacios — el caso del usuario.
        ("3310,00 €", Decimal("3310.00")),
        ("€3.310,00", Decimal("3310.00")),
        ("$25.50", Decimal("25.50")),
        ("£1,234.56", Decimal("1234.56")),
        ("1234,56 EUR", Decimal("1234.56")),
        ("-1.234,56 €", Decimal("1234.56")),
        # Espacios sueltos
        (" 100,00 ", Decimal("100.00")),
    ],
)
def test_parse_amount_accepts_currency_symbols_and_signs(raw: str, expected: Decimal) -> None:
    assert _parse_amount_signed(raw)[0] == expected


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "  €  ",
        "abc",
        "0,00",
        "0",
    ],
)
def test_parse_amount_rejects_empty_or_zero(raw: str) -> None:
    with pytest.raises(_RowError):
        _parse_amount_signed(raw)


# ─────────────────────────────────────────────────────────────────────────────
# _normalize_date: celdas con doble fecha y formatos varios
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "raw,expected",
    [
        # Formatos limpios
        ("2026-04-15", "2026-04-15"),
        ("15/04/2026", "15/04/2026"),
        ("15/04/26", "15/04/2026"),
        ("15/04", "15/04/2030"),  # DD/MM se rellena con default_year=2030
        # Doble fecha (caso real: "Fecha operación + Fecha valor" en una celda)
        (
            "30/01/2026 Fecha valor 28/01/2026",
            "30/01/2026",
        ),
        ("30/01/2026  28/01/2026", "30/01/2026"),
        # ISO con texto extra
        ("Fecha 2026-04-15 valor", "2026-04-15"),
        # Con espacios en blanco
        ("  15/04/2026  ", "15/04/2026"),
        # Texto sin fecha → devuelve la cadena tal cual (el service la rechazará)
        ("sin fecha", "sin fecha"),
        ("", ""),
    ],
)
def test_normalize_date_extracts_first_date(raw: str, expected: str) -> None:
    assert _normalize_date(raw, default_year=2030) == expected


# ─────────────────────────────────────────────────────────────────────────────
# PHASE-39 — columna Saldo del extracto: rol propio + parseo + elección de ancla.
# ─────────────────────────────────────────────────────────────────────────────


def test_classify_columns_assigns_saldo_role_not_amount() -> None:
    """`Saldo` recibe su rol propio (`statement_balance`) y el importe sigue
    siendo la columna Importe — la regla histórica ("saldo" NUNCA matchea
    amount) se conserva intacta."""
    roles = _classify_columns(["Fecha", "Concepto", "Importe", "Saldo"])
    assert roles["occurred_at"] == 0
    assert roles["category_name"] == 1
    assert roles["amount"] == 2
    assert roles["statement_balance"] == 3


def test_parse_pdf_smart_emits_statement_balance() -> None:
    """El smart parser PDF emite la columna Saldo como campo propio de la
    fila (antes la descartaba)."""
    payload = _build_pdf(
        [
            [
                ["Fecha", "Concepto", "Importe", "Saldo"],
                ["30/01/2026", "TRANSFERENCIA Wi", "-60,00 €", "3.317,98 €"],
                ["30/01/2026", "PAYPAL GOOGLE", "-5,17 €", "3.312,81 €"],
            ]
        ]
    )
    rows, _header = parse_pdf_smart(payload)
    assert len(rows) == 2
    assert "3.317,98" in rows[0]["statement_balance"]
    assert "3.312,81" in rows[1]["statement_balance"]


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("3.317,98 €", Decimal("3317.98")),
        ("1,234.56", Decimal("1234.56")),
        ("-1.234,56", Decimal("-1234.56")),
        ("(500,00)", Decimal("-500.00")),  # negativo contable
        ("1.234,56-", Decimal("-1234.56")),  # signo al final
        ("0,00", Decimal("0.00")),  # el saldo SÍ puede ser 0
        ("+25.50", Decimal("25.50")),
        ("", None),
        ("   ", None),
        ("n/a", None),  # ilegible → None, nunca error
    ],
)
def test_parse_balance_signed_and_tolerant(raw: str, expected: Decimal | None) -> None:
    """A diferencia del importe, el saldo conserva el signo, admite 0 y
    NUNCA lanza — un valor ilegible devuelve None (es informativo)."""
    assert _parse_balance(raw) == expected


def _row(
    day: int,
    saldo: str | None,
    amount: str,
    flow_value: str,
) -> ParsedRow:
    """ParsedRow mínimo para los tests de elección de ancla."""
    return ParsedRow(
        amount=Decimal(amount),
        occurred_at=datetime(2026, 1, day),
        description=None,
        category_id=None,
        import_hash=f"hash-{day}-{saldo}",
        flow=TransactionFlow(flow_value),
        statement_balance=Decimal(saldo) if saldo is not None else None,
    )


def test_pick_balance_anchor_dates_decide_direction() -> None:
    """Con fechas distintas, la dirección la dan la primera y última fila."""
    # viejo→nuevo: el ancla es la ÚLTIMA fila.
    oldest_first = [_row(10, "1100.00", "100.00", "IN"), _row(20, "1050.00", "50.00", "OUT")]
    anchor = _pick_balance_anchor(oldest_first)
    assert anchor is not None
    assert anchor[1] == Decimal("1050.00")
    # nuevo→viejo (BBVA): el ancla es la PRIMERA fila.
    newest_first = list(reversed(oldest_first))
    anchor = _pick_balance_anchor(newest_first)
    assert anchor is not None
    assert anchor[1] == Decimal("1050.00")


def test_pick_balance_anchor_same_day_uses_chain_arithmetic() -> None:
    """Extracto de un solo día: la aritmética saldo±importe decide el orden.

    newest-first válido: saldo[i] == saldo[i+1] + movimiento[i].
    Filas (nuevo→viejo): B(saldo 100, +10) encima de A(saldo 90, −5):
    100 == 90 + 10 ✓ → ancla = fila de arriba (100)."""
    rows = [_row(15, "100.00", "10.00", "IN"), _row(15, "90.00", "5.00", "OUT")]
    anchor = _pick_balance_anchor(rows)
    assert anchor is not None
    assert anchor[1] == Decimal("100.00")

    # oldest-first válido: saldo[i+1] == saldo[i] + movimiento[i+1].
    # A(saldo 95, −5) y debajo B(saldo 195, +100): 195 == 95 + 100 ✓
    # → ancla = fila de abajo (195).
    rows = [_row(15, "95.00", "5.00", "OUT"), _row(15, "195.00", "100.00", "IN")]
    anchor = _pick_balance_anchor(rows)
    assert anchor is not None
    assert anchor[1] == Decimal("195.00")


def test_pick_balance_anchor_none_without_saldo() -> None:
    """Sin ninguna fila con saldo no hay ancla."""
    rows = [_row(10, None, "100.00", "IN")]
    assert _pick_balance_anchor(rows) is None


# ── PHASE-47: una fecha de extracto es una fecha CIVIL ────────────────────


def test_una_fecha_sin_hora_se_ancla_a_medianoche_utc() -> None:
    """El parser NO puede devolver un naive: la zona la elegiría el driver.

    asyncpg interpreta un `datetime` naive como hora local DEL PROCESO al
    escribirlo en una columna `TIMESTAMPTZ`. Con el backend en Europe/Madrid,
    «13/02/2026» se persistía como `2026-02-12T23:00:00Z`, así que el dato
    dependía del ordenador que hizo el import y del horario de verano — y un
    filtro que empieza el día 13 (construido en UTC) dejaba fuera los
    movimientos de ese mismo día 13.
    """
    from app.modules.personal_finance.imports.service import _parse_datetime

    for texto in ("13/02/2026", "2026-02-13", "13-02-2026", "13.02.2026"):
        parsed = _parse_datetime(texto)
        assert parsed.tzinfo is not None, f"{texto!r} devolvió un naive"
        assert parsed.utcoffset() == timedelta(0), f"{texto!r} no quedó en UTC"
        assert (parsed.year, parsed.month, parsed.day) == (2026, 2, 13)
        assert (parsed.hour, parsed.minute, parsed.second) == (0, 0, 0)


def test_una_fecha_con_hora_conserva_la_hora_y_solo_ancla_la_zona() -> None:
    """Anclar no es convertir. Un naive con hora venía sin zona, así que
    trasladarlo asumiría que era local — que es exactamente el bug."""
    from app.modules.personal_finance.imports.service import _parse_datetime

    parsed = _parse_datetime("2026-02-13T14:30:00")
    assert parsed.utcoffset() == timedelta(0)
    assert (parsed.hour, parsed.minute) == (14, 30)


def test_un_iso_con_offset_se_traslada_a_utc() -> None:
    """Lo que SÍ trae zona se convierte, para que la columna sea homogénea:
    las 14:30 de Madrid son las 13:30 UTC, y ahí es donde deben vivir."""
    from app.modules.personal_finance.imports.service import _parse_datetime

    parsed = _parse_datetime("2026-02-13T14:30:00+01:00")
    assert parsed.utcoffset() == timedelta(0)
    assert (parsed.hour, parsed.minute) == (13, 30)
    assert parsed.day == 13


def test_el_hash_no_cambia_al_pasar_la_fecha_a_tz_aware() -> None:
    """La identidad de una fila del extracto no puede depender de su
    REPRESENTACIÓN.

    Cuando el parser pasó a emitir tz-aware, `.isoformat()` empezó a añadir
    `+00:00` y el hash de la misma fila del banco cambiaba de valor. Eso habría
    matado los ~557 `import_hash` persistidos y con ellos tres cosas a la vez:
    el dedup (reimportar duplicaría todo), la reposición de declaraciones desde
    la papelera y el guardarraíl que avisa de un fichero importado en la cuenta
    equivocada.

    Este test es el que hace segura la migración de datos: mientras pase, no
    hay que rehashear ni una fila.
    """
    from app.modules.personal_finance.imports.service import _compute_hash

    uid = uuid.UUID("11111111-2222-3333-4444-555555555555")
    kwargs = {
        "user_id": uid,
        "amount": Decimal("33.58"),
        "currency": "EUR",
        "description": "Www.amazon* sb2u90z85 Pago con tarjeta",
    }
    naive = _compute_hash(occurred_at=datetime(2026, 6, 29, 0, 0), **kwargs)  # type: ignore[arg-type]
    aware = _compute_hash(occurred_at=datetime(2026, 6, 29, 0, 0, tzinfo=UTC), **kwargs)  # type: ignore[arg-type]
    assert naive == aware, "el sufijo de zona no puede entrar en el hash"

    # Y un mismo instante escrito en otra zona colapsa al mismo hash: las 14:30
    # de Madrid son las 12:30 UTC del mismo día.
    madrid = datetime(2026, 6, 29, 14, 30, tzinfo=timezone(timedelta(hours=2)))
    assert _compute_hash(occurred_at=madrid, **kwargs) == _compute_hash(  # type: ignore[arg-type]
        occurred_at=datetime(2026, 6, 29, 12, 30, tzinfo=UTC), **kwargs  # type: ignore[arg-type]
    )
