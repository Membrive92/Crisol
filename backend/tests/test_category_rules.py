"""Tests del módulo category_rules: CRUD + matching en imports."""

from __future__ import annotations

import io
import json

from httpx import AsyncClient
from openpyxl import Workbook


async def _wipe_seeded(client: AsyncClient, token: str) -> None:
    """Borra todas las reglas + categorías que crea el seed al
    registrarse. Estos tests asumen entorno limpio para verificar el
    comportamiento aislado del rules engine sin que el seed interfiera.
    """
    rules = (
        await client.get("/category-rules", headers={"Authorization": f"Bearer {token}"})
    ).json()["items"]
    for r in rules:
        await client.delete(
            f"/category-rules/{r['id']}",
            headers={"Authorization": f"Bearer {token}"},
        )
    cats = (await client.get("/categories", headers={"Authorization": f"Bearer {token}"})).json()
    for c in cats:
        await client.delete(
            f"/categories/{c['id']}",
            headers={"Authorization": f"Bearer {token}"},
        )


async def _setup_user(
    client: AsyncClient, email: str = "rules@example.com"
) -> tuple[str, str, str, str]:
    r = await client.post(
        "/auth/register",
        json={"email": email, "password": "SecurePass123", "display_name": "Test"},
    )
    token = r.json()["access_token"]
    # Limpia el seed automático para que estos tests partan de cero.
    await _wipe_seeded(client, token)
    cat_food = await client.post(
        "/categories",
        json={"name": "Comida", "kind": "expense"},
        headers={"Authorization": f"Bearer {token}"},
    )
    cat_subs = await client.post(
        "/categories",
        json={"name": "Suscripciones", "kind": "expense"},
        headers={"Authorization": f"Bearer {token}"},
    )
    acc = await client.post(
        "/accounts",
        json={"name": "Cuenta principal", "type": "bank", "currency": "EUR"},
        headers={"Authorization": f"Bearer {token}"},
    )
    return token, cat_food.json()["id"], cat_subs.json()["id"], acc.json()["id"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ─────────────────────────────────────────────────────────────────────────────
# CRUD
# ─────────────────────────────────────────────────────────────────────────────


async def test_list_starts_empty(client: AsyncClient) -> None:
    token, _, _, _ = await _setup_user(client, "rules-empty@example.com")
    r = await client.get("/category-rules", headers=_auth(token))
    assert r.status_code == 200
    assert r.json() == {"items": []}


async def test_create_rule(client: AsyncClient) -> None:
    token, food_id, _, _ = await _setup_user(client, "rules-create@example.com")
    r = await client.post(
        "/category-rules",
        json={
            "pattern": "RESTAURANT",
            "match_type": "contains",
            "field": "concept",
            "category_id": food_id,
            "priority": 50,
        },
        headers=_auth(token),
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["pattern"] == "RESTAURANT"
    assert body["match_type"] == "contains"
    assert body["field"] == "concept"
    assert body["priority"] == 50
    assert body["enabled"] is True


async def test_create_rejects_invalid_regex(client: AsyncClient) -> None:
    token, food_id, _, _ = await _setup_user(client, "rules-regex@example.com")
    r = await client.post(
        "/category-rules",
        json={
            "pattern": "[unbalanced",
            "match_type": "regex",
            "field": "both",
            "category_id": food_id,
        },
        headers=_auth(token),
    )
    assert r.status_code == 422


async def test_create_rejects_foreign_category(client: AsyncClient) -> None:
    token_a, _, _, _ = await _setup_user(client, "rules-fA@example.com")
    _, food_b, _, _ = await _setup_user(client, "rules-fB@example.com")
    r = await client.post(
        "/category-rules",
        json={
            "pattern": "X",
            "match_type": "exact",
            "field": "both",
            "category_id": food_b,
        },
        headers=_auth(token_a),
    )
    assert r.status_code == 400


async def test_update_rule(client: AsyncClient) -> None:
    token, food_id, subs_id, _ = await _setup_user(client, "rules-update@example.com")
    rule_id = (
        await client.post(
            "/category-rules",
            json={
                "pattern": "RESTAURANT",
                "match_type": "contains",
                "field": "concept",
                "category_id": food_id,
            },
            headers=_auth(token),
        )
    ).json()["id"]
    r = await client.put(
        f"/category-rules/{rule_id}",
        json={"pattern": "RESTAURANTE", "category_id": subs_id, "enabled": False},
        headers=_auth(token),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["pattern"] == "RESTAURANTE"
    assert body["category_id"] == subs_id
    assert body["enabled"] is False


async def test_delete_rule(client: AsyncClient) -> None:
    token, food_id, _, _ = await _setup_user(client, "rules-del@example.com")
    rule_id = (
        await client.post(
            "/category-rules",
            json={
                "pattern": "X",
                "match_type": "contains",
                "field": "both",
                "category_id": food_id,
            },
            headers=_auth(token),
        )
    ).json()["id"]
    r = await client.delete(f"/category-rules/{rule_id}", headers=_auth(token))
    assert r.status_code == 204
    list_r = await client.get("/category-rules", headers=_auth(token))
    assert list_r.json()["items"] == []


async def test_user_isolation(client: AsyncClient) -> None:
    token_a, food_a, _, _ = await _setup_user(client, "rules-isoA@example.com")
    token_b, food_b, _, _ = await _setup_user(client, "rules-isoB@example.com")
    await client.post(
        "/category-rules",
        json={
            "pattern": "AAA",
            "match_type": "contains",
            "field": "both",
            "category_id": food_a,
        },
        headers=_auth(token_a),
    )
    await client.post(
        "/category-rules",
        json={
            "pattern": "BBB",
            "match_type": "contains",
            "field": "both",
            "category_id": food_b,
        },
        headers=_auth(token_b),
    )
    items_a = (await client.get("/category-rules", headers=_auth(token_a))).json()["items"]
    items_b = (await client.get("/category-rules", headers=_auth(token_b))).json()["items"]
    assert {i["pattern"] for i in items_a} == {"AAA"}
    assert {i["pattern"] for i in items_b} == {"BBB"}


async def test_delete_category_cascades_rule(client: AsyncClient) -> None:
    token, food_id, _, _ = await _setup_user(client, "rules-cascade@example.com")
    await client.post(
        "/category-rules",
        json={
            "pattern": "X",
            "match_type": "contains",
            "field": "both",
            "category_id": food_id,
        },
        headers=_auth(token),
    )
    await client.delete(f"/categories/{food_id}", headers=_auth(token))
    items = (await client.get("/category-rules", headers=_auth(token))).json()["items"]
    assert items == []


# ─────────────────────────────────────────────────────────────────────────────
# Matching en imports
# ─────────────────────────────────────────────────────────────────────────────


def _xlsx(rows: list[tuple[str, str, str, str]]) -> bytes:
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


_DEFAULT_MAPPING = json.dumps(
    {
        "amount": "Importe",
        "occurred_at": "Fecha",
        "description": "Detalle",
        "category_name": "Concepto",
    }
)


async def _import_xlsx(client: AsyncClient, token: str, account_id: str, payload: bytes) -> dict:
    files = {
        "file": (
            "import.xlsx",
            payload,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    }
    data = {"account_id": account_id, "column_mappings": _DEFAULT_MAPPING}
    pr = await client.post("/imports/preview", files=files, data=data, headers=_auth(token))
    job_id = pr.json()["job_id"]
    cr = await client.post(f"/imports/{job_id}/commit", headers=_auth(token))
    return cr.json()


async def test_rule_contains_matches_concept(client: AsyncClient) -> None:
    """Una regla CONTAINS sobre el concepto autocategoriza filas con
    el concepto matching."""
    token, food_id, _, account_id = await _setup_user(client, "rule-contains@example.com")
    await client.post(
        "/category-rules",
        json={
            "pattern": "RESTAURANT",
            "match_type": "contains",
            "field": "concept",
            "category_id": food_id,
        },
        headers=_auth(token),
    )
    payload = _xlsx(
        [
            ("2026-04-15", "PAGO TARJETA - RESTAURANTES", "10.00", "Mercadona"),
            ("2026-04-16", "BIZUM", "5.00", "Sin concepto"),
        ]
    )
    await _import_xlsx(client, token, account_id, payload)
    txs = (await client.get("/transactions", headers=_auth(token))).json()["items"]
    by_desc = {t["description"]: t for t in txs}
    assert by_desc["Mercadona"]["category_id"] == food_id
    # La fila de BIZUM no matchea ninguna regla → sin categoría.
    assert by_desc["Sin concepto"]["category_id"] is None


async def test_rule_contains_matches_description(client: AsyncClient) -> None:
    """Regla CONTAINS sobre description: matchea por nombre del comercio."""
    token, food_id, _, account_id = await _setup_user(client, "rule-desc@example.com")
    await client.post(
        "/category-rules",
        json={
            "pattern": "MERCADONA",
            "match_type": "contains",
            "field": "description",
            "category_id": food_id,
        },
        headers=_auth(token),
    )
    payload = _xlsx([("2026-04-15", "PAGO TARJETA", "10.00", "Mercadona Torre Pacheco")])
    await _import_xlsx(client, token, account_id, payload)
    txs = (await client.get("/transactions", headers=_auth(token))).json()["items"]
    assert txs[0]["category_id"] == food_id


async def test_rule_priority_first_match_wins(client: AsyncClient) -> None:
    """Si dos reglas matchean, gana la de menor priority."""
    token, food_id, subs_id, account_id = await _setup_user(client, "rule-priority@example.com")
    # Priority 10 → Suscripciones (más específica).
    await client.post(
        "/category-rules",
        json={
            "pattern": "AMAZON PRIME",
            "match_type": "contains",
            "field": "description",
            "category_id": subs_id,
            "priority": 10,
        },
        headers=_auth(token),
    )
    # Priority 100 → Comida (más genérica).
    await client.post(
        "/category-rules",
        json={
            "pattern": "AMAZON",
            "match_type": "contains",
            "field": "description",
            "category_id": food_id,
            "priority": 100,
        },
        headers=_auth(token),
    )
    payload = _xlsx([("2026-04-15", "PAGO TARJETA", "9.99", "Amazon Prime Video")])
    await _import_xlsx(client, token, account_id, payload)
    txs = (await client.get("/transactions", headers=_auth(token))).json()["items"]
    assert txs[0]["category_id"] == subs_id  # ganó la prioritaria


async def test_rule_disabled_does_not_match(client: AsyncClient) -> None:
    token, food_id, _, account_id = await _setup_user(client, "rule-disabled@example.com")
    rule_id = (
        await client.post(
            "/category-rules",
            json={
                "pattern": "RESTAURANT",
                "match_type": "contains",
                "field": "concept",
                "category_id": food_id,
            },
            headers=_auth(token),
        )
    ).json()["id"]
    await client.put(
        f"/category-rules/{rule_id}",
        json={"enabled": False},
        headers=_auth(token),
    )
    payload = _xlsx([("2026-04-15", "PAGO TARJETA - RESTAURANTES", "10.00", "Mercadona")])
    await _import_xlsx(client, token, account_id, payload)
    txs = (await client.get("/transactions", headers=_auth(token))).json()["items"]
    assert txs[0]["category_id"] is None


async def test_rule_matching_is_accent_insensitive(client: AsyncClient) -> None:
    """La normalización quita acentos: una regla 'CATEGORIA' matchea
    'CATEGORÍA' en el dato."""
    token, food_id, _, account_id = await _setup_user(client, "rule-acc@example.com")
    await client.post(
        "/category-rules",
        json={
            "pattern": "RESTAURACION",
            "match_type": "contains",
            "field": "concept",
            "category_id": food_id,
        },
        headers=_auth(token),
    )
    payload = _xlsx([("2026-04-15", "TARJETA RESTAURACIÓN", "10.00", "Mercadona")])
    await _import_xlsx(client, token, account_id, payload)
    txs = (await client.get("/transactions", headers=_auth(token))).json()["items"]
    assert txs[0]["category_id"] == food_id


async def test_rule_starts_with(client: AsyncClient) -> None:
    token, food_id, _, account_id = await _setup_user(client, "rule-sw@example.com")
    await client.post(
        "/category-rules",
        json={
            "pattern": "PAGO TARJETA",
            "match_type": "starts_with",
            "field": "concept",
            "category_id": food_id,
        },
        headers=_auth(token),
    )
    payload = _xlsx(
        [
            ("2026-04-15", "PAGO TARJETA - RESTAURANTES", "10.00", "X"),
            ("2026-04-16", "BIZUM PAGO TARJETA", "5.00", "Y"),
        ]
    )
    await _import_xlsx(client, token, account_id, payload)
    txs = (await client.get("/transactions", headers=_auth(token))).json()["items"]
    by_desc = {t["description"]: t for t in txs}
    # Solo el que empieza por "PAGO TARJETA" matchea.
    assert by_desc["X"]["category_id"] == food_id
    assert by_desc["Y"]["category_id"] is None


async def test_preview_uses_rule_as_suggestion(client: AsyncClient) -> None:
    """En el preview, los grupos cuyas filas matcheen una regla
    devuelven `suggested_category_id` con su categoría y
    `suggestion_source='rule'`."""
    token, food_id, _, account_id = await _setup_user(client, "rule-pre1@example.com")
    await client.post(
        "/category-rules",
        json={
            "pattern": "RESTAURANT",
            "match_type": "contains",
            "field": "concept",
            "category_id": food_id,
        },
        headers=_auth(token),
    )
    payload = _xlsx(
        [
            ("2026-04-15", "PAGO TARJETA - RESTAURANTES", "10.00", "X"),
            ("2026-04-16", "PAGO TARJETA - RESTAURANTES", "20.00", "Y"),
        ]
    )
    files = {
        "file": (
            "import.xlsx",
            payload,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    }
    pr = await client.post(
        "/imports/preview",
        files=files,
        data={"account_id": account_id, "column_mappings": _DEFAULT_MAPPING},
        headers=_auth(token),
    )
    groups = pr.json()["bank_concept_groups"]
    assert len(groups) == 1
    assert groups[0]["suggested_category_id"] == food_id
    assert groups[0]["suggestion_source"] == "rule"
    assert groups[0]["has_mixed_rule_matches"] is False


async def test_preview_marks_mixed_rule_matches(client: AsyncClient) -> None:
    """Si el mismo concepto matchea reglas distintas según la
    description, marca `has_mixed_rule_matches=True` y deja la
    sugerencia en null."""
    token, food_id, subs_id, account_id = await _setup_user(client, "rule-pre-mix@example.com")
    # Regla por description "MERCADONA" → Comida.
    await client.post(
        "/category-rules",
        json={
            "pattern": "MERCADONA",
            "match_type": "contains",
            "field": "description",
            "category_id": food_id,
        },
        headers=_auth(token),
    )
    # Regla por description "NETFLIX" → Suscripciones.
    await client.post(
        "/category-rules",
        json={
            "pattern": "NETFLIX",
            "match_type": "contains",
            "field": "description",
            "category_id": subs_id,
        },
        headers=_auth(token),
    )
    payload = _xlsx(
        [
            # Mismo concepto, descriptions distintas → reglas distintas.
            ("2026-04-15", "PAGO TARJETA", "10.00", "Mercadona Madrid"),
            ("2026-04-16", "PAGO TARJETA", "9.99", "Netflix"),
        ]
    )
    files = {
        "file": (
            "import.xlsx",
            payload,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    }
    pr = await client.post(
        "/imports/preview",
        files=files,
        data={"account_id": account_id, "column_mappings": _DEFAULT_MAPPING},
        headers=_auth(token),
    )
    groups = pr.json()["bank_concept_groups"]
    assert len(groups) == 1
    assert groups[0]["concept"] == "PAGO TARJETA"
    assert groups[0]["has_mixed_rule_matches"] is True
    assert groups[0]["suggested_category_id"] is None
    assert groups[0]["suggestion_source"] is None


async def test_preview_saved_mapping_beats_rule_in_suggestion(
    client: AsyncClient,
) -> None:
    """Equivalencia exacta gana sobre regla incluso en preview."""
    token, food_id, subs_id, account_id = await _setup_user(client, "rule-pre-bm@example.com")
    # Regla → Comida.
    await client.post(
        "/category-rules",
        json={
            "pattern": "RESTAURANT",
            "match_type": "contains",
            "field": "concept",
            "category_id": food_id,
        },
        headers=_auth(token),
    )
    # Equivalencia exacta → Suscripciones.
    await client.post(
        "/bank-mappings",
        json={
            "bank_concept": "PAGO TARJETA - RESTAURANTES",
            "category_id": subs_id,
        },
        headers=_auth(token),
    )
    payload = _xlsx([("2026-04-15", "PAGO TARJETA - RESTAURANTES", "10.00", "X")])
    files = {
        "file": (
            "import.xlsx",
            payload,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    }
    pr = await client.post(
        "/imports/preview",
        files=files,
        data={"account_id": account_id, "column_mappings": _DEFAULT_MAPPING},
        headers=_auth(token),
    )
    groups = pr.json()["bank_concept_groups"]
    assert groups[0]["suggested_category_id"] == subs_id  # bm gana
    assert groups[0]["suggestion_source"] == "saved_mapping"


async def test_bank_mapping_beats_rule(client: AsyncClient) -> None:
    """Si hay tanto bank_mapping exacto como regla matching, gana el
    mapping (orden de prioridad de la asignación)."""
    token, food_id, subs_id, account_id = await _setup_user(client, "rule-bm@example.com")
    # Mapping exacto → Suscripciones.
    await client.post(
        "/bank-mappings",
        json={
            "bank_concept": "PAGO TARJETA - RESTAURANTES",
            "category_id": subs_id,
        },
        headers=_auth(token),
    )
    # Regla sobre el mismo concepto → Comida.
    await client.post(
        "/category-rules",
        json={
            "pattern": "RESTAURANT",
            "match_type": "contains",
            "field": "concept",
            "category_id": food_id,
        },
        headers=_auth(token),
    )
    payload = _xlsx([("2026-04-15", "PAGO TARJETA - RESTAURANTES", "10.00", "X")])
    await _import_xlsx(client, token, account_id, payload)
    txs = (await client.get("/transactions", headers=_auth(token))).json()["items"]
    # Mapping exacto gana sobre la regla.
    assert txs[0]["category_id"] == subs_id
