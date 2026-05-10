"""Tests del módulo imports (router + service)."""

from __future__ import annotations

import io
import json
from decimal import Decimal
from unittest.mock import AsyncMock, patch

from httpx import AsyncClient
from openpyxl import Workbook
from reportlab.lib import colors as rl_colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Table, TableStyle

from app.modules.ai.schemas import BankStatementRow


async def _setup_user(
    client: AsyncClient, email: str = "imp@example.com"
) -> tuple[str, str]:
    """Registra un usuario y crea una cuenta, devuelve (token, account_id)."""
    r = await client.post(
        "/auth/register",
        json={"email": email, "password": "SecurePass123", "display_name": "Imp"},
    )
    token = str(r.json()["access_token"])
    acc = await client.post(
        "/accounts",
        json={"name": "Cuenta principal", "type": "bank", "currency": "EUR"},
        headers={"Authorization": f"Bearer {token}"},
    )
    return token, acc.json()["id"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


_DEFAULT_MAPPING = {
    "amount": "Importe",
    "occurred_at": "Fecha",
    "description": "Concepto",
    "category_name": "Categoria",
}


async def _post_csv(
    client: AsyncClient,
    token: str,
    account_id: str,
    csv_text: str,
    *,
    mapping: dict[str, str] | None = None,
    currency: str = "EUR",
) -> dict[str, object]:
    files = {"file": ("import.csv", csv_text.encode("utf-8"), "text/csv")}
    data = {
        "account_id": account_id,
        "column_mappings": json.dumps(mapping or _DEFAULT_MAPPING),
        "currency": currency,
    }
    r = await client.post("/imports", files=files, data=data, headers=_auth(token))
    assert r.status_code == 201, r.text
    return r.json()  # type: ignore[no-any-return]


async def test_import_csv_creates_transactions(client: AsyncClient) -> None:
    token, account_id = await _setup_user(client)
    csv_text = (
        "Fecha,Importe,Concepto\n"
        "2026-04-15,25.50,Cafe\n"
        "2026-04-16,10.00,Almuerzo\n"
    )
    job = await _post_csv(client, token, account_id, csv_text, mapping={
        "amount": "Importe",
        "occurred_at": "Fecha",
        "description": "Concepto",
    })
    assert job["status"] == "completed"
    assert job["rows_total"] == 2
    assert job["rows_ok"] == 2
    assert job["rows_failed"] == 0
    assert job["rows_skipped"] == 0

    r = await client.get("/transactions", headers=_auth(token))
    body = r.json()
    assert body["total"] == 2
    assert all(t["source"] == "import" for t in body["items"])


async def test_import_dedupes_within_batch(client: AsyncClient) -> None:
    token, account_id = await _setup_user(client, "dedup@example.com")
    csv_text = (
        "Fecha,Importe,Concepto\n"
        "2026-04-15,10.00,Cafe\n"
        "2026-04-15,10.00,Cafe\n"
    )
    job = await _post_csv(client, token, account_id, csv_text, mapping={
        "amount": "Importe",
        "occurred_at": "Fecha",
        "description": "Concepto",
    })
    assert job["rows_ok"] == 1
    assert job["rows_skipped"] == 1


async def test_import_dedupes_against_existing(client: AsyncClient) -> None:
    token, account_id = await _setup_user(client, "dedup2@example.com")
    csv_text = "Fecha,Importe,Concepto\n2026-04-15,10.00,Cafe\n"
    job1 = await _post_csv(client, token, account_id, csv_text, mapping={
        "amount": "Importe",
        "occurred_at": "Fecha",
        "description": "Concepto",
    })
    assert job1["rows_ok"] == 1

    job2 = await _post_csv(client, token, account_id, csv_text, mapping={
        "amount": "Importe",
        "occurred_at": "Fecha",
        "description": "Concepto",
    })
    assert job2["rows_ok"] == 0
    assert job2["rows_skipped"] == 1


async def test_import_records_invalid_rows(client: AsyncClient) -> None:
    token, account_id = await _setup_user(client, "errors@example.com")
    csv_text = (
        "Fecha,Importe,Concepto\n"
        "2026-04-15,not-a-number,Cafe\n"
        "not-a-date,10.00,Cafe2\n"
        "2026-04-15,10.00,Cafe3\n"
    )
    job = await _post_csv(client, token, account_id, csv_text, mapping={
        "amount": "Importe",
        "occurred_at": "Fecha",
        "description": "Concepto",
    })
    assert job["rows_total"] == 3
    assert job["rows_ok"] == 1
    assert job["rows_failed"] == 2
    rows_with_errors = sorted(int(e["row"]) for e in job["error_log"])
    assert rows_with_errors == [1, 2]


async def test_import_assigns_category_by_name(client: AsyncClient) -> None:
    token, account_id = await _setup_user(client, "cat@example.com")
    cat = await client.post(
        "/categories",
        json={"name": "Comida", "kind": "expense"},
        headers=_auth(token),
    )
    cat_id = cat.json()["id"]

    csv_text = (
        "Fecha,Importe,Concepto,Categoria\n2026-04-15,10.00,Cafe,COMIDA\n"
    )
    job = await _post_csv(client, token, account_id, csv_text)
    assert job["rows_ok"] == 1

    r = await client.get("/transactions", headers=_auth(token))
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["category_id"] == cat_id


async def test_import_invalid_mapping_returns_422(client: AsyncClient) -> None:
    token, account_id = await _setup_user(client, "badmap@example.com")
    csv_text = "Fecha,Importe\n2026-04-15,10.00\n"
    files = {"file": ("import.csv", csv_text.encode("utf-8"), "text/csv")}
    data = {
        "account_id": account_id,
        "column_mappings": json.dumps({"description": "Concepto"}),  # falta amount/occurred_at
    }
    r = await client.post("/imports", files=files, data=data, headers=_auth(token))
    assert r.status_code == 422


async def test_import_invalid_pdf_marks_failed(client: AsyncClient) -> None:
    """PDF malformado: el job se marca como failed con error_log."""
    token, account_id = await _setup_user(client, "badfmt@example.com")
    files = {"file": ("import.pdf", b"%PDF-1.4 fake", "application/pdf")}
    data = {"account_id": account_id, "column_mappings": json.dumps(_DEFAULT_MAPPING)}
    r = await client.post("/imports", files=files, data=data, headers=_auth(token))
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "failed"
    assert body["rows_total"] == 0
    assert body["error_log"]


async def test_import_unsupported_extension_marks_failed(client: AsyncClient) -> None:
    """Extensiones que no son CSV/XLSX/PDF terminan en failed."""
    token, account_id = await _setup_user(client, "txtfmt@example.com")
    files = {"file": ("notes.txt", b"random text", "text/plain")}
    data = {"account_id": account_id, "column_mappings": json.dumps(_DEFAULT_MAPPING)}
    r = await client.post("/imports", files=files, data=data, headers=_auth(token))
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "failed"


async def test_import_pdf(client: AsyncClient) -> None:
    """PDF con tabla bordeada se procesa por el mismo pipeline que CSV."""
    token, account_id = await _setup_user(client, "pdf@example.com")

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    table = Table(
        [
            ["Fecha", "Importe", "Concepto"],
            ["2026-04-15", "25.50", "Cafe"],
            ["2026-04-16", "10.00", "Almuerzo"],
        ]
    )
    table.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, rl_colors.black)]))
    doc.build([table])
    pdf_bytes = buffer.getvalue()

    files = {"file": ("statement.pdf", pdf_bytes, "application/pdf")}
    data = {
        "account_id": account_id,
        "column_mappings": json.dumps(
            {
                "amount": "Importe",
                "occurred_at": "Fecha",
                "description": "Concepto",
            }
        ),
    }
    r = await client.post("/imports", files=files, data=data, headers=_auth(token))
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "completed"
    assert body["rows_ok"] == 2
    assert body["rows_failed"] == 0


async def test_import_xlsx(client: AsyncClient) -> None:
    token, account_id = await _setup_user(client, "xlsx@example.com")
    wb = Workbook()
    sheet = wb.active
    assert sheet is not None
    sheet.append(["Fecha", "Importe", "Concepto"])
    sheet.append(["2026-04-15", 25.5, "Cafe"])
    sheet.append(["2026-04-16", 10.0, "Almuerzo"])
    buf = io.BytesIO()
    wb.save(buf)

    files = {
        "file": (
            "import.xlsx",
            buf.getvalue(),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    }
    data = {
        "account_id": account_id,
        "column_mappings": json.dumps({
            "amount": "Importe",
            "occurred_at": "Fecha",
            "description": "Concepto",
        }),
    }
    r = await client.post("/imports", files=files, data=data, headers=_auth(token))
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["rows_ok"] == 2


async def test_import_list_and_get(client: AsyncClient) -> None:
    token, account_id = await _setup_user(client, "list@example.com")
    csv_text = "Fecha,Importe,Concepto\n2026-04-15,10.00,Cafe\n"
    job = await _post_csv(client, token, account_id, csv_text, mapping={
        "amount": "Importe",
        "occurred_at": "Fecha",
        "description": "Concepto",
    })

    r_list = await client.get("/imports", headers=_auth(token))
    assert r_list.status_code == 200
    assert r_list.json()["total"] == 1

    r_get = await client.get(f"/imports/{job['id']}", headers=_auth(token))
    assert r_get.status_code == 200
    assert r_get.json()["id"] == job["id"]


async def test_import_user_isolation(client: AsyncClient) -> None:
    token_a, account_a = await _setup_user(client, "ia@example.com")
    token_b, _account_b = await _setup_user(client, "ib@example.com")

    csv_text = "Fecha,Importe,Concepto\n2026-04-15,10.00,Cafe\n"
    job_a = await _post_csv(client, token_a, account_a, csv_text, mapping={
        "amount": "Importe",
        "occurred_at": "Fecha",
        "description": "Concepto",
    })

    r_b_list = await client.get("/imports", headers=_auth(token_b))
    assert r_b_list.json()["total"] == 0

    r_b_get = await client.get(f"/imports/{job_a['id']}", headers=_auth(token_b))
    assert r_b_get.status_code == 404


async def test_import_european_amount_formats(client: AsyncClient) -> None:
    token, account_id = await _setup_user(client, "fmt@example.com")
    csv_text = (
        "Fecha,Importe,Concepto\n"
        "2026-04-15,\"1.234,56\",Compra europea\n"
        "2026-04-16,\"1,234.56\",Compra USA\n"
    )
    job = await _post_csv(client, token, account_id, csv_text, mapping={
        "amount": "Importe",
        "occurred_at": "Fecha",
        "description": "Concepto",
    })
    assert job["rows_ok"] == 2

    r = await client.get("/transactions", headers=_auth(token))
    amounts = sorted(t["amount"] for t in r.json()["items"])
    assert amounts == ["1234.56", "1234.56"]


# ─────────────────────────────────────
# Vision PDF fallback (PDFs sin tabla)
# ─────────────────────────────────────


def _build_scanned_pdf() -> bytes:
    """PDF con sólo texto (sin tabla detectable por pdfplumber)."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    style = getSampleStyleSheet()["BodyText"]
    doc.build([Paragraph("Texto suelto sin estructura tabular.", style)])
    return buffer.getvalue()


def _build_pdf(pages: list[list[list[str]]]) -> bytes:
    """PDF con una `Table` por página (cada página = una tabla).

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


async def test_import_pdf_vision_fallback_imports_rows(client: AsyncClient) -> None:
    """PDF sin tablas → fallback a visión → rows importadas."""
    token, account_id = await _setup_user(client, "vision@example.com")
    pdf = _build_scanned_pdf()

    with (
        patch(
            "app.modules.personal_finance.imports.service.render_pdf_pages_to_png",
            return_value=[b"fake-png-page-1"],
        ),
        patch(
            "app.modules.personal_finance.imports.service.ai_service.extract_bank_statement_page",
            new_callable=AsyncMock,
            return_value=[
                BankStatementRow(
                    description="Alquiler",
                    amount=Decimal("750.00"),
                    occurred_at="2026-04-01",
                ),
                BankStatementRow(
                    description="Cafetería",
                    amount=Decimal("3.20"),
                    occurred_at="2026-04-02",
                ),
            ],
        ),
    ):
        files = {"file": ("statement.pdf", pdf, "application/pdf")}
        # El usuario manda un mapping con sus propias keys; el service lo
        # ignora cuando entra al fallback de visión y usa las claves fijas.
        data = {
            "account_id": account_id,
            "column_mappings": json.dumps(
                {
                    "amount": "Importe",
                    "occurred_at": "Fecha",
                    "description": "Concepto",
                }
            ),
        }
        r = await client.post("/imports", files=files, data=data, headers=_auth(token))

    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "completed"
    assert body["rows_ok"] == 2
    assert body["rows_failed"] == 0


async def test_import_pdf_vision_fallback_when_ai_down_fails_job(
    client: AsyncClient,
) -> None:
    """Si la visión falla, el job termina como failed con mensaje claro."""
    from app.modules.ai.exceptions import AiUnavailableError

    token, account_id = await _setup_user(client, "vision-down@example.com")
    pdf = _build_scanned_pdf()

    with (
        patch(
            "app.modules.personal_finance.imports.service.render_pdf_pages_to_png",
            return_value=[b"fake-png"],
        ),
        patch(
            "app.modules.personal_finance.imports.service.ai_service.extract_bank_statement_page",
            new_callable=AsyncMock,
            side_effect=AiUnavailableError("Ollama down"),
        ),
    ):
        files = {"file": ("statement.pdf", pdf, "application/pdf")}
        data = {"account_id": account_id, "column_mappings": json.dumps(_DEFAULT_MAPPING)}
        r = await client.post("/imports", files=files, data=data, headers=_auth(token))

    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "failed"
    assert "Visión PDF" in body["error_log"][0]["error"]


# ─────────────────────────────────────────────────────────────────────────────
# Preview / commit (PHASE-18+): wizard en dos pasos
# ─────────────────────────────────────────────────────────────────────────────


async def test_preview_csv_returns_rows_and_does_not_persist(
    client: AsyncClient,
) -> None:
    token, account_id = await _setup_user(client, "preview@example.com")
    csv_text = (
        "Fecha,Importe,Concepto\n"
        "2026-04-15,25.50,Cafe\n"
        "2026-04-16,10.00,Almuerzo\n"
    )
    files = {"file": ("import.csv", csv_text.encode("utf-8"), "text/csv")}
    data = {
        "account_id": account_id,
        "column_mappings": json.dumps(
            {"amount": "Importe", "occurred_at": "Fecha", "description": "Concepto"}
        ),
    }
    r = await client.post("/imports/preview", files=files, data=data, headers=_auth(token))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["source"] == "csv"
    assert body["total_rows"] == 2
    assert len(body["rows"]) == 2
    assert body["rows"][0]["amount"] == "25.50"
    assert body["rows"][0]["description"] == "Cafe"

    # Las transacciones NO se han persistido aún.
    r2 = await client.get("/transactions", headers=_auth(token))
    assert r2.json()["total"] == 0


async def test_preview_then_commit_persists_transactions(client: AsyncClient) -> None:
    token, account_id = await _setup_user(client, "commit@example.com")
    csv_text = (
        "Fecha,Importe,Concepto\n"
        "2026-04-15,25.50,Cafe\n"
        "2026-04-16,10.00,Almuerzo\n"
    )
    files = {"file": ("import.csv", csv_text.encode("utf-8"), "text/csv")}
    data = {
        "account_id": account_id,
        "column_mappings": json.dumps(
            {"amount": "Importe", "occurred_at": "Fecha", "description": "Concepto"}
        ),
    }
    pr = await client.post(
        "/imports/preview", files=files, data=data, headers=_auth(token)
    )
    assert pr.status_code == 200
    job_id = pr.json()["job_id"]

    cr = await client.post(f"/imports/{job_id}/commit", headers=_auth(token))
    assert cr.status_code == 200, cr.text
    body = cr.json()
    assert body["status"] == "completed"
    assert body["rows_ok"] == 2

    r = await client.get("/transactions", headers=_auth(token))
    assert r.json()["total"] == 2


async def test_commit_rejects_already_completed_job(client: AsyncClient) -> None:
    token, account_id = await _setup_user(client, "double-commit@example.com")
    csv_text = "Fecha,Importe,Concepto\n2026-04-15,25.50,Cafe\n"
    files = {"file": ("import.csv", csv_text.encode("utf-8"), "text/csv")}
    data = {
        "account_id": account_id,
        "column_mappings": json.dumps(
            {"amount": "Importe", "occurred_at": "Fecha", "description": "Concepto"}
        ),
    }
    pr = await client.post(
        "/imports/preview", files=files, data=data, headers=_auth(token)
    )
    job_id = pr.json()["job_id"]
    first = await client.post(f"/imports/{job_id}/commit", headers=_auth(token))
    assert first.status_code == 200

    second = await client.post(f"/imports/{job_id}/commit", headers=_auth(token))
    assert second.status_code == 409


async def test_commit_rejects_unknown_job(client: AsyncClient) -> None:
    token, _account_id = await _setup_user(client, "no-job@example.com")
    fake = "00000000-0000-0000-0000-000000000000"
    r = await client.post(f"/imports/{fake}/commit", headers=_auth(token))
    assert r.status_code == 404


async def test_preview_pdf_smart_returns_fixed_keys(client: AsyncClient) -> None:
    """Para un PDF con tabla de transacciones detectable, el preview
    devuelve filas con keys fijas (amount/occurred_at/description/
    category_name) y `source=pdfplumber_smart` — el mapping del usuario
    se ignora."""
    token, account_id = await _setup_user(client, "smart-pdf@example.com")
    pdf = _build_pdf(
        [
            # Tabla resumen — debe ignorarse
            [
                ["Concepto", "Importe (EUR)"],
                ["Total ingresos", "100,00"],
            ],
            # Tabla de transacciones — la heurística la detecta
            [
                ["F. Operac.", "Concepto", "Detalle", "Importe (EUR)"],
                ["15/04", "PAGO TARJETA", "AMAZON.ES", "-25,50"],
                ["16/04", "BIZUM RECIBIDO", "Lasana SG", "10,00"],
            ],
        ]
    )
    files = {"file": ("statement.pdf", pdf, "application/pdf")}
    data = {"account_id": account_id, "column_mappings": json.dumps(_DEFAULT_MAPPING)}
    r = await client.post(
        "/imports/preview", files=files, data=data, headers=_auth(token)
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["source"] == "pdfplumber_smart"
    assert body["total_rows"] == 2
    # Las filas vienen con descripciones del Detalle, no con totales.
    descriptions = [row["description"] for row in body["rows"]]
    assert "AMAZON.ES" in descriptions
    assert "Total ingresos" not in descriptions
