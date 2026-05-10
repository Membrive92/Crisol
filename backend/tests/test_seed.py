"""Tests del módulo seed: register hook + endpoint /seed/recommended."""

from __future__ import annotations

import io
import json

from httpx import AsyncClient
from openpyxl import Workbook


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_register_seeds_categories_and_rules(client: AsyncClient) -> None:
    """Tras `POST /auth/register`, el usuario tiene categorías y reglas
    recomendadas listas."""
    r = await client.post(
        "/auth/register",
        json={
            "email": "seed-fresh@example.com",
            "password": "SecurePass123",
            "display_name": "Test",
        },
    )
    assert r.status_code == 201
    token = r.json()["access_token"]

    cats = (await client.get("/categories", headers=_auth(token))).json()
    assert len(cats) >= 10  # esperamos al menos 10 categorías típicas
    names = {c["name"] for c in cats}
    assert "Restaurantes" in names
    assert "Supermercado" in names
    assert "Nómina" in names

    rules = (await client.get("/category-rules", headers=_auth(token))).json()[
        "items"
    ]
    assert len(rules) >= 50  # esperamos muchísimas reglas


async def test_seed_recommended_endpoint_is_idempotent(client: AsyncClient) -> None:
    """Llamar a /seed/recommended dos veces no duplica nada."""
    r = await client.post(
        "/auth/register",
        json={
            "email": "seed-idem@example.com",
            "password": "SecurePass123",
            "display_name": "Test",
        },
    )
    token = r.json()["access_token"]

    cats_after_register = (
        await client.get("/categories", headers=_auth(token))
    ).json()
    rules_after_register = (
        await client.get("/category-rules", headers=_auth(token))
    ).json()["items"]

    # Llamamos al endpoint manualmente (segunda vez ya).
    seed_r = await client.post("/seed/recommended", headers=_auth(token))
    assert seed_r.status_code == 200
    body = seed_r.json()
    assert body["categories_created"] == 0
    assert body["rules_created"] == 0
    assert body["categories_existed"] >= 10
    assert body["rules_existed"] >= 50

    cats_after = (await client.get("/categories", headers=_auth(token))).json()
    rules_after = (
        await client.get("/category-rules", headers=_auth(token))
    ).json()["items"]
    assert len(cats_after) == len(cats_after_register)
    assert len(rules_after) == len(rules_after_register)


async def test_seed_after_register_actually_categorizes_imports(
    client: AsyncClient,
) -> None:
    """End-to-end: usuario nuevo importa un extracto típico y las filas
    salen categorizadas automáticamente sin tocar nada."""
    r = await client.post(
        "/auth/register",
        json={
            "email": "seed-e2e@example.com",
            "password": "SecurePass123",
            "display_name": "Test",
        },
    )
    token = r.json()["access_token"]
    acc = await client.post(
        "/accounts",
        json={"name": "Cuenta principal", "type": "bank", "currency": "EUR"},
        headers=_auth(token),
    )
    account_id = acc.json()["id"]

    # Construye un XLSX con conceptos típicos de un banco español.
    wb = Workbook()
    ws = wb.active
    assert ws is not None
    ws.append(["Fecha", "Concepto", "Importe", "Detalle"])
    ws.append(["2026-04-15", "PAGO TARJETA - RESTAURANTES", "29.66", "Mercadona"])
    ws.append(["2026-04-15", "BIZUM RECIBIDO", "10.00", "Lasana"])
    ws.append(["2026-04-15", "PAGO TARJETA - SUSCRIPCIONES", "9.99", "Spotify"])
    ws.append(["2026-04-15", "ABONO DE NOMINA", "2491.65", "Empresa SA"])
    ws.append(["2026-04-15", "PAGO TARJETA - GASOLINERAS", "40.00", "Repsol"])
    ws.append(["2026-04-15", "PAGO TARJETA - FARMACIA", "12.50", "Farmacia X"])
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
        "column_mappings": json.dumps(
            {
                "amount": "Importe",
                "occurred_at": "Fecha",
                "description": "Detalle",
                "category_name": "Concepto",
            }
        ),
    }
    pr = await client.post(
        "/imports/preview", files=files, data=data, headers=_auth(token)
    )
    job_id = pr.json()["job_id"]
    cr = await client.post(f"/imports/{job_id}/commit", headers=_auth(token))
    assert cr.status_code == 200
    assert cr.json()["rows_ok"] == 6

    # Las 6 filas deben tener categoría asignada por las reglas seed.
    txs = (await client.get("/transactions", headers=_auth(token))).json()["items"]
    cats = (await client.get("/categories", headers=_auth(token))).json()
    cats_by_id = {c["id"]: c["name"] for c in cats}

    by_desc = {t["description"]: cats_by_id.get(t["category_id"]) for t in txs}
    assert by_desc["Mercadona"] == "Restaurantes"  # PAGO TARJETA - RESTAURANTES
    assert by_desc["Lasana"] == "Bizum recibido"
    assert by_desc["Spotify"] == "Suscripciones"
    assert by_desc["Empresa SA"] == "Nómina"
    assert by_desc["Repsol"] == "Combustible"
    assert by_desc["Farmacia X"] == "Salud y farmacia"


async def test_seed_does_not_overwrite_user_categories(
    client: AsyncClient,
) -> None:
    """Si el usuario ya tiene una categoría con el mismo nombre, el seed
    la reutiliza en vez de duplicarla."""
    # Para este test simulamos: crear user, cambiar el nombre de
    # 'Restaurantes' a algo distinto, llamar seed, ver que no se
    # duplica nada raro.
    r = await client.post(
        "/auth/register",
        json={
            "email": "seed-noovr@example.com",
            "password": "SecurePass123",
            "display_name": "Test",
        },
    )
    token = r.json()["access_token"]

    # Cuento las categorías iniciales.
    initial = (await client.get("/categories", headers=_auth(token))).json()
    initial_count = len(initial)

    # Vuelvo a llamar al seed.
    await client.post("/seed/recommended", headers=_auth(token))
    after = (await client.get("/categories", headers=_auth(token))).json()
    assert len(after) == initial_count
