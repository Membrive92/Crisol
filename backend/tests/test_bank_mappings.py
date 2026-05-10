"""Tests del módulo bank_mappings (CRUD + integración con imports)."""

from __future__ import annotations

import io
import json

from httpx import AsyncClient
from openpyxl import Workbook


async def _wipe_seeded(client: AsyncClient, token: str) -> None:
    """Borra reglas + categorías del seed automático para tests
    aislados del rules engine."""
    h = {"Authorization": f"Bearer {token}"}
    rules = (await client.get("/category-rules", headers=h)).json()["items"]
    for r in rules:
        await client.delete(f"/category-rules/{r['id']}", headers=h)
    cats = (await client.get("/categories", headers=h)).json()
    for c in cats:
        await client.delete(f"/categories/{c['id']}", headers=h)


async def _setup_user(
    client: AsyncClient, email: str = "bm@example.com"
) -> tuple[str, str, str, str]:
    """Helper: registra, limpia seed, crea dos categorías y cuenta,
    devuelve (token, cat_food_id, cat_subs_id, account_id)."""
    r = await client.post(
        "/auth/register",
        json={"email": email, "password": "SecurePass123", "display_name": "Test"},
    )
    token = r.json()["access_token"]
    # PHASE-20: el register siembra categorías + reglas. Estos tests
    # aíslan el comportamiento de bank_mappings, así que limpiamos.
    await _wipe_seeded(client, token)

    food = await client.post(
        "/categories",
        json={"name": "Comida", "kind": "expense"},
        headers={"Authorization": f"Bearer {token}"},
    )
    subs = await client.post(
        "/categories",
        json={"name": "Suscripciones", "kind": "expense"},
        headers={"Authorization": f"Bearer {token}"},
    )
    acc = await client.post(
        "/accounts",
        json={"name": "Cuenta principal", "type": "bank", "currency": "EUR"},
        headers={"Authorization": f"Bearer {token}"},
    )
    return token, food.json()["id"], subs.json()["id"], acc.json()["id"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ─────────────────────────────────────────────────────────────────────────────
# CRUD de bank-mappings
# ─────────────────────────────────────────────────────────────────────────────


async def test_list_starts_empty(client: AsyncClient) -> None:
    token, _, _, _ = await _setup_user(client, "bm-empty@example.com")
    r = await client.get("/bank-mappings", headers=_auth(token))
    assert r.status_code == 200
    assert r.json() == {"items": []}


async def test_create_and_list(client: AsyncClient) -> None:
    token, food_id, _, _ = await _setup_user(client, "bm-create@example.com")
    r = await client.post(
        "/bank-mappings",
        json={"bank_concept": "PAGO TARJETA - RESTAURANTES", "category_id": food_id},
        headers=_auth(token),
    )
    assert r.status_code == 201, r.text
    body = r.json()
    # El concepto se guarda normalizado (lowercase).
    assert body["bank_concept"] == "pago tarjeta - restaurantes"
    assert body["category_id"] == food_id

    list_r = await client.get("/bank-mappings", headers=_auth(token))
    assert len(list_r.json()["items"]) == 1


async def test_upsert_replaces_category_for_same_concept(
    client: AsyncClient,
) -> None:
    token, food_id, subs_id, _ = await _setup_user(client, "bm-upsert@example.com")
    first = await client.post(
        "/bank-mappings",
        json={"bank_concept": "PAYPAL", "category_id": food_id},
        headers=_auth(token),
    )
    second = await client.post(
        "/bank-mappings",
        json={"bank_concept": "PAYPAL", "category_id": subs_id},
        headers=_auth(token),
    )
    assert first.status_code == 201
    assert second.status_code == 201
    # Mismo id (UPSERT, no duplicate).
    assert first.json()["id"] == second.json()["id"]
    assert second.json()["category_id"] == subs_id

    items = (await client.get("/bank-mappings", headers=_auth(token))).json()["items"]
    assert len(items) == 1


async def test_create_rejects_category_from_other_user(client: AsyncClient) -> None:
    """Si el `category_id` no pertenece al usuario, 400."""
    token_a, _, _, _ = await _setup_user(client, "bm-A@example.com")
    token_b, food_b, _, _ = await _setup_user(client, "bm-B@example.com")
    # A intenta usar la categoría de B.
    r = await client.post(
        "/bank-mappings",
        json={"bank_concept": "X", "category_id": food_b},
        headers=_auth(token_a),
    )
    assert r.status_code == 400


async def test_delete_mapping(client: AsyncClient) -> None:
    token, food_id, _, _ = await _setup_user(client, "bm-del@example.com")
    created = (
        await client.post(
            "/bank-mappings",
            json={"bank_concept": "X", "category_id": food_id},
            headers=_auth(token),
        )
    ).json()
    r = await client.delete(
        f"/bank-mappings/{created['id']}", headers=_auth(token)
    )
    assert r.status_code == 204
    list_r = await client.get("/bank-mappings", headers=_auth(token))
    assert list_r.json()["items"] == []


async def test_user_isolation(client: AsyncClient) -> None:
    """Cada usuario solo ve sus propias equivalencias."""
    token_a, food_a, _, _ = await _setup_user(client, "bm-isoA@example.com")
    token_b, food_b, _, _ = await _setup_user(client, "bm-isoB@example.com")
    await client.post(
        "/bank-mappings",
        json={"bank_concept": "AAA", "category_id": food_a},
        headers=_auth(token_a),
    )
    await client.post(
        "/bank-mappings",
        json={"bank_concept": "BBB", "category_id": food_b},
        headers=_auth(token_b),
    )

    items_a = (await client.get("/bank-mappings", headers=_auth(token_a))).json()[
        "items"
    ]
    items_b = (await client.get("/bank-mappings", headers=_auth(token_b))).json()[
        "items"
    ]
    assert [i["bank_concept"] for i in items_a] == ["aaa"]
    assert [i["bank_concept"] for i in items_b] == ["bbb"]


async def test_delete_category_cascades_mapping(client: AsyncClient) -> None:
    """Si el usuario borra la categoría, la equivalencia se borra también."""
    token, food_id, _, _ = await _setup_user(client, "bm-cascade@example.com")
    await client.post(
        "/bank-mappings",
        json={"bank_concept": "X", "category_id": food_id},
        headers=_auth(token),
    )
    # Borrar la categoría.
    await client.delete(f"/categories/{food_id}", headers=_auth(token))
    items = (await client.get("/bank-mappings", headers=_auth(token))).json()["items"]
    assert items == []


# ─────────────────────────────────────────────────────────────────────────────
# Integración con imports: preview groups + commit con overrides + autoaprendizaje
# ─────────────────────────────────────────────────────────────────────────────


def _xlsx_with_concepts(rows: list[tuple[str, str, str, str]]) -> bytes:
    """rows: (fecha, concepto, importe, detalle)."""
    wb = Workbook()
    ws = wb.active
    assert ws is not None
    ws.append(["Fecha", "Concepto", "Importe", "Detalle"])
    for r in rows:
        ws.append(list(r))
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


async def test_preview_groups_rows_by_bank_concept(client: AsyncClient) -> None:
    """El preview agrupa filas por concepto único y devuelve el count."""
    token, _, _, account_id = await _setup_user(client, "bm-preview@example.com")
    payload = _xlsx_with_concepts(
        [
            ("2026-04-15", "PAGO TARJETA", "10.00", "Amazon"),
            ("2026-04-16", "PAGO TARJETA", "20.00", "Mercadona"),
            ("2026-04-17", "BIZUM RECIBIDO", "5.00", "Sin concepto"),
        ]
    )
    files = {
        "file": (
            "import.xlsx",
            payload,
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
    r = await client.post(
        "/imports/preview", files=files, data=data, headers=_auth(token)
    )
    assert r.status_code == 200, r.text
    groups = r.json()["bank_concept_groups"]
    assert len(groups) == 2
    by_concept = {g["concept"]: g for g in groups}
    assert by_concept["PAGO TARJETA"]["count"] == 2
    assert by_concept["BIZUM RECIBIDO"]["count"] == 1
    # Sin equivalencias previas → suggested_category_id es null.
    assert all(g["suggested_category_id"] is None for g in groups)


async def test_preview_returns_existing_mapping_as_suggestion(
    client: AsyncClient,
) -> None:
    """Si ya hay equivalencia guardada, el preview la sugiere."""
    token, food_id, _, account_id = await _setup_user(client, "bm-suggest@example.com")
    await client.post(
        "/bank-mappings",
        json={"bank_concept": "PAGO TARJETA", "category_id": food_id},
        headers=_auth(token),
    )
    payload = _xlsx_with_concepts(
        [("2026-04-15", "PAGO TARJETA", "10.00", "Amazon")]
    )
    files = {
        "file": (
            "import.xlsx",
            payload,
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
    r = await client.post(
        "/imports/preview", files=files, data=data, headers=_auth(token)
    )
    groups = r.json()["bank_concept_groups"]
    assert len(groups) == 1
    assert groups[0]["suggested_category_id"] == food_id


async def test_commit_with_overrides_assigns_categories_and_persists_mapping(
    client: AsyncClient,
) -> None:
    """Caso end-to-end: usuario asigna categorías en el preview,
    se importan las filas con esas categorías y la equivalencia
    queda guardada para futuras importaciones."""
    token, food_id, subs_id, account_id = await _setup_user(client, "bm-e2e@example.com")
    payload = _xlsx_with_concepts(
        [
            ("2026-04-15", "PAGO TARJETA", "10.00", "Mercadona"),
            ("2026-04-16", "PAGO TARJETA", "20.00", "Carrefour"),
            ("2026-04-17", "PAYPAL", "9.99", "Spotify"),
        ]
    )
    files = {
        "file": (
            "import.xlsx",
            payload,
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

    cr = await client.post(
        f"/imports/{job_id}/commit",
        headers=_auth(token),
        json={
            "category_overrides": {
                "PAGO TARJETA": food_id,
                "PAYPAL": subs_id,
            }
        },
    )
    assert cr.status_code == 200, cr.text
    assert cr.json()["rows_ok"] == 3

    # Las transacciones tienen las categorías asignadas.
    txs = (await client.get("/transactions", headers=_auth(token))).json()["items"]
    by_desc = {t["description"]: t for t in txs}
    assert by_desc["Mercadona"]["category_id"] == food_id
    assert by_desc["Carrefour"]["category_id"] == food_id
    assert by_desc["Spotify"]["category_id"] == subs_id

    # Y las equivalencias se han guardado: el siguiente preview las
    # sugiere automáticamente.
    next_pr = await client.post(
        "/imports/preview", files=files, data=data, headers=_auth(token)
    )
    groups = next_pr.json()["bank_concept_groups"]
    by_concept = {g["concept"]: g for g in groups}
    assert by_concept["PAGO TARJETA"]["suggested_category_id"] == food_id
    assert by_concept["PAYPAL"]["suggested_category_id"] == subs_id


async def test_commit_uses_saved_mapping_without_explicit_override(
    client: AsyncClient,
) -> None:
    """Si la equivalencia ya existía (de un import anterior o creada
    manualmente), el commit la aplica sin necesidad de mandar override."""
    token, food_id, _, account_id = await _setup_user(client, "bm-saved@example.com")
    await client.post(
        "/bank-mappings",
        json={"bank_concept": "PAGO TARJETA", "category_id": food_id},
        headers=_auth(token),
    )

    payload = _xlsx_with_concepts(
        [("2026-04-15", "PAGO TARJETA", "10.00", "Mercadona")]
    )
    files = {
        "file": (
            "import.xlsx",
            payload,
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
    # Commit SIN body — debería aplicar la equivalencia guardada.
    cr = await client.post(f"/imports/{job_id}/commit", headers=_auth(token))
    assert cr.status_code == 200
    assert cr.json()["rows_ok"] == 1

    txs = (await client.get("/transactions", headers=_auth(token))).json()["items"]
    assert txs[0]["category_id"] == food_id


async def test_commit_ignores_overrides_with_foreign_category(
    client: AsyncClient,
) -> None:
    """Override con `category_id` que pertenece a otro usuario se
    ignora silenciosamente — el flujo no aborta."""
    token_a, _food_a, _, account_a = await _setup_user(client, "bm-foreignA@example.com")
    _token_b, food_b, _, _ = await _setup_user(client, "bm-foreignB@example.com")

    payload = _xlsx_with_concepts(
        [("2026-04-15", "PAGO TARJETA", "10.00", "Mercadona")]
    )
    files = {
        "file": (
            "import.xlsx",
            payload,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    }
    data = {
        "account_id": account_a,
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
        "/imports/preview", files=files, data=data, headers=_auth(token_a)
    )
    job_id = pr.json()["job_id"]

    cr = await client.post(
        f"/imports/{job_id}/commit",
        headers=_auth(token_a),
        json={"category_overrides": {"PAGO TARJETA": food_b}},  # ajeno
    )
    assert cr.status_code == 200
    # Se importó pero sin categoría (override ignorado, sin fallback).
    txs = (await client.get("/transactions", headers=_auth(token_a))).json()[
        "items"
    ]
    assert txs[0]["category_id"] is None
