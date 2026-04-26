"""Tests del módulo imports (router + service)."""

from __future__ import annotations

import io
import json

from httpx import AsyncClient
from openpyxl import Workbook
from reportlab.lib import colors as rl_colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle


async def _setup_user(client: AsyncClient, email: str = "imp@example.com") -> str:
    r = await client.post(
        "/auth/register",
        json={"email": email, "password": "SecurePass123", "display_name": "Imp"},
    )
    return str(r.json()["access_token"])


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
    csv_text: str,
    *,
    mapping: dict[str, str] | None = None,
    currency: str = "EUR",
) -> dict[str, object]:
    files = {"file": ("import.csv", csv_text.encode("utf-8"), "text/csv")}
    data = {
        "column_mappings": json.dumps(mapping or _DEFAULT_MAPPING),
        "currency": currency,
    }
    r = await client.post("/imports", files=files, data=data, headers=_auth(token))
    assert r.status_code == 201, r.text
    return r.json()  # type: ignore[no-any-return]


async def test_import_csv_creates_transactions(client: AsyncClient) -> None:
    token = await _setup_user(client)
    csv_text = (
        "Fecha,Importe,Concepto\n"
        "2026-04-15,25.50,Cafe\n"
        "2026-04-16,10.00,Almuerzo\n"
    )
    job = await _post_csv(client, token, csv_text, mapping={
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
    token = await _setup_user(client, "dedup@example.com")
    csv_text = (
        "Fecha,Importe,Concepto\n"
        "2026-04-15,10.00,Cafe\n"
        "2026-04-15,10.00,Cafe\n"
    )
    job = await _post_csv(client, token, csv_text, mapping={
        "amount": "Importe",
        "occurred_at": "Fecha",
        "description": "Concepto",
    })
    assert job["rows_ok"] == 1
    assert job["rows_skipped"] == 1


async def test_import_dedupes_against_existing(client: AsyncClient) -> None:
    token = await _setup_user(client, "dedup2@example.com")
    csv_text = "Fecha,Importe,Concepto\n2026-04-15,10.00,Cafe\n"
    job1 = await _post_csv(client, token, csv_text, mapping={
        "amount": "Importe",
        "occurred_at": "Fecha",
        "description": "Concepto",
    })
    assert job1["rows_ok"] == 1

    job2 = await _post_csv(client, token, csv_text, mapping={
        "amount": "Importe",
        "occurred_at": "Fecha",
        "description": "Concepto",
    })
    assert job2["rows_ok"] == 0
    assert job2["rows_skipped"] == 1


async def test_import_records_invalid_rows(client: AsyncClient) -> None:
    token = await _setup_user(client, "errors@example.com")
    csv_text = (
        "Fecha,Importe,Concepto\n"
        "2026-04-15,not-a-number,Cafe\n"
        "not-a-date,10.00,Cafe2\n"
        "2026-04-15,10.00,Cafe3\n"
    )
    job = await _post_csv(client, token, csv_text, mapping={
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
    token = await _setup_user(client, "cat@example.com")
    cat = await client.post(
        "/categories",
        json={"name": "Comida", "kind": "expense"},
        headers=_auth(token),
    )
    cat_id = cat.json()["id"]

    csv_text = (
        "Fecha,Importe,Concepto,Categoria\n2026-04-15,10.00,Cafe,COMIDA\n"
    )
    job = await _post_csv(client, token, csv_text)
    assert job["rows_ok"] == 1

    r = await client.get("/transactions", headers=_auth(token))
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["category_id"] == cat_id


async def test_import_invalid_mapping_returns_422(client: AsyncClient) -> None:
    token = await _setup_user(client, "badmap@example.com")
    csv_text = "Fecha,Importe\n2026-04-15,10.00\n"
    files = {"file": ("import.csv", csv_text.encode("utf-8"), "text/csv")}
    data = {
        "column_mappings": json.dumps({"description": "Concepto"}),  # falta amount/occurred_at
    }
    r = await client.post("/imports", files=files, data=data, headers=_auth(token))
    assert r.status_code == 422


async def test_import_invalid_pdf_marks_failed(client: AsyncClient) -> None:
    """PDF malformado: el job se marca como failed con error_log."""
    token = await _setup_user(client, "badfmt@example.com")
    files = {"file": ("import.pdf", b"%PDF-1.4 fake", "application/pdf")}
    data = {"column_mappings": json.dumps(_DEFAULT_MAPPING)}
    r = await client.post("/imports", files=files, data=data, headers=_auth(token))
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "failed"
    assert body["rows_total"] == 0
    assert body["error_log"]


async def test_import_unsupported_extension_marks_failed(client: AsyncClient) -> None:
    """Extensiones que no son CSV/XLSX/PDF terminan en failed."""
    token = await _setup_user(client, "txtfmt@example.com")
    files = {"file": ("notes.txt", b"random text", "text/plain")}
    data = {"column_mappings": json.dumps(_DEFAULT_MAPPING)}
    r = await client.post("/imports", files=files, data=data, headers=_auth(token))
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "failed"


async def test_import_pdf(client: AsyncClient) -> None:
    """PDF con tabla bordeada se procesa por el mismo pipeline que CSV."""
    token = await _setup_user(client, "pdf@example.com")

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
    token = await _setup_user(client, "xlsx@example.com")
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
    token = await _setup_user(client, "list@example.com")
    csv_text = "Fecha,Importe,Concepto\n2026-04-15,10.00,Cafe\n"
    job = await _post_csv(client, token, csv_text, mapping={
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
    token_a = await _setup_user(client, "ia@example.com")
    token_b = await _setup_user(client, "ib@example.com")

    csv_text = "Fecha,Importe,Concepto\n2026-04-15,10.00,Cafe\n"
    job_a = await _post_csv(client, token_a, csv_text, mapping={
        "amount": "Importe",
        "occurred_at": "Fecha",
        "description": "Concepto",
    })

    r_b_list = await client.get("/imports", headers=_auth(token_b))
    assert r_b_list.json()["total"] == 0

    r_b_get = await client.get(f"/imports/{job_a['id']}", headers=_auth(token_b))
    assert r_b_get.status_code == 404


async def test_import_european_amount_formats(client: AsyncClient) -> None:
    token = await _setup_user(client, "fmt@example.com")
    csv_text = (
        "Fecha,Importe,Concepto\n"
        "2026-04-15,\"1.234,56\",Compra europea\n"
        "2026-04-16,\"1,234.56\",Compra USA\n"
    )
    job = await _post_csv(client, token, csv_text, mapping={
        "amount": "Importe",
        "occurred_at": "Fecha",
        "description": "Concepto",
    })
    assert job["rows_ok"] == 2

    r = await client.get("/transactions", headers=_auth(token))
    amounts = sorted(t["amount"] for t in r.json()["items"])
    assert amounts == ["1234.56", "1234.56"]
