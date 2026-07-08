"""Tests de regresión para los hallazgos de la auditoría del pipeline de
imports (PHASE-32 follow-up).

Cubre, por hallazgo:

  #1  El signo del extracto NO se descarta: se usa como señal de dirección
      y corrige/valida el kind de la categoría resuelta.
  #2  El hash de dedup incluye un ordinal de ocurrencia → dos líneas
      idénticas el mismo día NO colapsan, pero re-importar es idempotente.
  #3  Dos filas no reconcilian contra la misma tx `expected`.
  #4  `1.500` europeo se interpreta como 1500, no 1,50.
  #5  La corrección de dirección de transferencia sólo reasigna cuando el
      kind actual NO coincide (no degrada a la `is_transfer` más antigua).
  #6  Una colisión de `import_hash` concurrente se trata como skipped, no 500.
  #7  `valor` suelto fuera de `_DATE_HEADER_HINTS` (parser).

La mayoría se prueban de forma AISLADA (funciones puras / `_parse_row` con
mapas inyectados); #1/#2/#3 también se cubren end-to-end vía `/imports`.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.modules.personal_finance.bank_mappings.repository import get_mappings_for_concepts
from app.modules.personal_finance.categories.models import CategoryKind
from app.modules.personal_finance.imports.parser import (
    _DATE_HEADER_HINTS,
    _classify_columns,
)
from app.modules.personal_finance.imports.schemas import ImportColumnMappings
from app.modules.personal_finance.imports.service import (
    _compute_hash,
    _direction_ambiguous_concepts,
    _parse_amount,
    _parse_amount_signed,
    _parse_row,
    _persist_user_category_overrides,
)
from app.modules.personal_finance.transactions.models import Transaction

# ─────────────────────────────────────────────────────────────────────────────
# Finding #4 — desambiguación miles vs. decimal en `_parse_amount`
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "raw,expected",
    [
        # El caso del hallazgo: 3 dígitos tras un único punto → miles.
        ("1.500", Decimal("1500.00")),
        ("1.234", Decimal("1234.00")),
        ("100.000", Decimal("100000.00")),
        # 1-2 dígitos tras el punto → decimal anglosajón (sin cambios).
        ("25.50", Decimal("25.50")),
        ("25.5", Decimal("25.50")),
        # Casos ya soportados (no deben romperse).
        ("1.234,56", Decimal("1234.56")),  # punto miles + coma decimal
        ("1,234.56", Decimal("1234.56")),  # coma miles + punto decimal
        ("25,50", Decimal("25.50")),  # coma decimal es-ES
        ("3310,00 €", Decimal("3310.00")),
        # >3 dígitos tras el punto → decimal (no es agrupación de miles).
        ("1234.5678", Decimal("1234.57")),
    ],
)
def test_parse_amount_disambiguates_thousands_vs_decimal(raw: str, expected: Decimal) -> None:
    assert _parse_amount(raw) == expected


# ─────────────────────────────────────────────────────────────────────────────
# Finding #1 — el signo del extracto se conserva como dirección
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "raw,expected_amount,expected_sign",
    [
        ("-29,66", Decimal("29.66"), -1),  # cargo
        ("+10.00", Decimal("10.00"), 1),  # abono explícito
        ("100,00", Decimal("100.00"), 0),  # sin signo
        ("-1.234,56 EUR", Decimal("1234.56"), -1),
        ("+1.500", Decimal("1500.00"), 1),  # combina con finding #4
    ],
)
def test_parse_amount_signed_preserves_bank_sign(
    raw: str, expected_amount: Decimal, expected_sign: int
) -> None:
    amount, sign = _parse_amount_signed(raw)
    assert amount == expected_amount
    assert sign == expected_sign


def _row(amount: str, *, category: str = "") -> dict[str, str]:
    return {
        "Importe": amount,
        "Fecha": "2026-06-23",
        "Concepto": "Pago",
        "Categoria": category,
    }


_MAPPING = ImportColumnMappings(
    amount="Importe",
    occurred_at="Fecha",
    description="Concepto",
    category_name="Categoria",
)


def test_parse_row_reassigns_to_sibling_when_bank_sign_contradicts_kind() -> None:
    """Un abono (+) cuyo bank-mapping apunta a la categoría de GASTO debe
    reasignarse a la categoría hermana (mismo nombre, kind INCOME)."""
    user_id = uuid.uuid4()
    expense_cat = uuid.uuid4()
    income_cat = uuid.uuid4()
    category_kinds = {expense_cat: CategoryKind.EXPENSE, income_cat: CategoryKind.INCOME}
    # Hermanas: mismo nombre "nomina", distinto kind.
    siblings = {
        ("nomina", CategoryKind.EXPENSE): expense_cat,
        ("nomina", CategoryKind.INCOME): income_cat,
    }
    # bank_mappings manda "nomina" (concepto) a la categoría de GASTO (mal).
    bank_mappings = {"nomina": expense_cat}

    parsed, review = _parse_row(
        _row("+1.500,00", category="Nomina"),
        mappings=_MAPPING,
        user_id=user_id,
        currency="EUR",
        category_lookup={},
        default_category_id=None,
        bank_mappings=bank_mappings,
        category_kinds=category_kinds,
        sibling_by_name_kind=siblings,
    )
    # El signo + del extracto fuerza la categoría INCOME hermana.
    assert parsed.category_id == income_cat
    assert review is None


def test_parse_row_flags_for_review_when_no_sibling() -> None:
    """Si el signo contradice el kind y NO hay hermana, deja la categoría
    pero marca la fila para revisión (no persiste un signo erróneo en
    silencio)."""
    user_id = uuid.uuid4()
    expense_cat = uuid.uuid4()
    category_kinds = {expense_cat: CategoryKind.EXPENSE}
    bank_mappings = {"reembolso": expense_cat}

    parsed, review = _parse_row(
        _row("+50,00", category="Reembolso"),
        mappings=_MAPPING,
        user_id=user_id,
        currency="EUR",
        category_lookup={},
        default_category_id=None,
        bank_mappings=bank_mappings,
        category_kinds=category_kinds,
        sibling_by_name_kind={},  # sin hermana income
    )
    assert parsed.category_id == expense_cat  # no se pierde la categoría
    assert review is not None
    assert "revisa" in review.lower()


def test_parse_row_no_change_when_sign_matches_kind() -> None:
    """Un cargo (-) con categoría de gasto NO se toca ni se marca."""
    user_id = uuid.uuid4()
    expense_cat = uuid.uuid4()
    category_kinds = {expense_cat: CategoryKind.EXPENSE}
    bank_mappings = {"compra": expense_cat}

    parsed, review = _parse_row(
        _row("-30,00", category="Compra"),
        mappings=_MAPPING,
        user_id=user_id,
        currency="EUR",
        category_lookup={},
        default_category_id=None,
        bank_mappings=bank_mappings,
        category_kinds=category_kinds,
        sibling_by_name_kind={("compra", CategoryKind.EXPENSE): expense_cat},
    )
    assert parsed.category_id == expense_cat
    assert review is None


def test_parse_row_unsigned_amount_keeps_resolved_category() -> None:
    """Sin signo en el extracto (sign=0) NO forzamos nada: compatibilidad
    con CSV que sólo traen la magnitud."""
    user_id = uuid.uuid4()
    expense_cat = uuid.uuid4()
    income_cat = uuid.uuid4()
    category_kinds = {expense_cat: CategoryKind.EXPENSE, income_cat: CategoryKind.INCOME}
    bank_mappings = {"x": expense_cat}

    parsed, review = _parse_row(
        _row("100,00", category="X"),  # sin signo
        mappings=_MAPPING,
        user_id=user_id,
        currency="EUR",
        category_lookup={},
        default_category_id=None,
        bank_mappings=bank_mappings,
        category_kinds=category_kinds,
        sibling_by_name_kind={
            ("x", CategoryKind.EXPENSE): expense_cat,
            ("x", CategoryKind.INCOME): income_cat,
        },
    )
    assert parsed.category_id == expense_cat
    assert review is None


# ─────────────────────────────────────────────────────────────────────────────
# Finding #5 — transferencia: sólo reasignar si el kind NO coincide
# ─────────────────────────────────────────────────────────────────────────────


def test_parse_row_transfer_keeps_specific_category_when_kind_matches() -> None:
    """Si la categoría de transferencia resuelta YA tiene el kind que dicta
    la dirección, NO se degrada a la `is_transfer` más antigua del kind."""
    user_id = uuid.uuid4()
    # Categoría específica correcta (income) + la "más antigua" income.
    specific_income_transfer = uuid.uuid4()
    oldest_income_transfer = uuid.uuid4()
    oldest_expense_transfer = uuid.uuid4()
    transfer_cat_ids = {
        specific_income_transfer,
        oldest_income_transfer,
        oldest_expense_transfer,
    }
    # `transfer_by_kind` apunta a las MÁS ANTIGUAS de cada kind.
    transfer_by_kind = {
        CategoryKind.INCOME: oldest_income_transfer,
        CategoryKind.EXPENSE: oldest_expense_transfer,
    }
    category_kinds = {
        specific_income_transfer: CategoryKind.INCOME,
        oldest_income_transfer: CategoryKind.INCOME,
        oldest_expense_transfer: CategoryKind.EXPENSE,
    }
    bank_mappings = {"transferencia recibida": specific_income_transfer}

    parsed, _review = _parse_row(
        {
            "Importe": "+5000,00",
            "Fecha": "2026-06-23",
            "Concepto": "TRANSFERENCIA RECIBIDA DE JOSE",
            "Categoria": "Transferencia recibida",
        },
        mappings=_MAPPING,
        user_id=user_id,
        currency="EUR",
        category_lookup={},
        default_category_id=None,
        bank_mappings=bank_mappings,
        transfer_cat_ids=transfer_cat_ids,
        transfer_by_kind=transfer_by_kind,
        category_kinds=category_kinds,
        sibling_by_name_kind={},
    )
    # El kind income YA coincide con la dirección "recibida" → se queda la
    # categoría específica, NO la más antigua.
    assert parsed.category_id == specific_income_transfer


def test_parse_row_transfer_reassigns_when_kind_wrong() -> None:
    """Si la categoría de transferencia resuelta tiene el kind EQUIVOCADO
    para la dirección, se reasigna a la hermana del kind correcto
    (regresión PHASE-32)."""
    user_id = uuid.uuid4()
    wrong_expense_transfer = uuid.uuid4()
    correct_income_transfer = uuid.uuid4()
    transfer_cat_ids = {wrong_expense_transfer, correct_income_transfer}
    transfer_by_kind = {
        CategoryKind.INCOME: correct_income_transfer,
        CategoryKind.EXPENSE: wrong_expense_transfer,
    }
    category_kinds = {
        wrong_expense_transfer: CategoryKind.EXPENSE,
        correct_income_transfer: CategoryKind.INCOME,
    }
    # bank-mapping mal aprendido: "recibida" → categoría de GASTO.
    bank_mappings = {"transferencia recibida": wrong_expense_transfer}

    parsed, _review = _parse_row(
        {
            "Importe": "5000,00",
            "Fecha": "2026-06-23",
            "Concepto": "TRANSFERENCIA RECIBIDA DE JOSE",
            "Categoria": "Transferencia recibida",
        },
        mappings=_MAPPING,
        user_id=user_id,
        currency="EUR",
        category_lookup={},
        default_category_id=None,
        bank_mappings=bank_mappings,
        transfer_cat_ids=transfer_cat_ids,
        transfer_by_kind=transfer_by_kind,
        category_kinds=category_kinds,
        sibling_by_name_kind={},
    )
    assert parsed.category_id == correct_income_transfer


def test_parse_row_transfer_direction_from_sign_when_no_text_hint() -> None:
    """PHASE-32 HIGH#5 — una transferencia cuyo texto NO lleva
    RECIBIDA/REALIZADA (muchos bancos: BIZUM, ABONO, TRASPASO…) se corrige
    igualmente por el SIGNO del extracto: un abono (+) mapeado a la categoría
    de transferencia de GASTO se reasigna a la de INGRESO."""
    user_id = uuid.uuid4()
    transfer_expense = uuid.uuid4()
    transfer_income = uuid.uuid4()
    transfer_cat_ids = {transfer_expense, transfer_income}
    transfer_by_kind = {
        CategoryKind.EXPENSE: transfer_expense,
        CategoryKind.INCOME: transfer_income,
    }
    category_kinds = {
        transfer_expense: CategoryKind.EXPENSE,
        transfer_income: CategoryKind.INCOME,
    }
    # Mapping aprendido AL REVÉS: un bizum entrante → transfer GASTO.
    bank_mappings = {"bizum de jose": transfer_expense}

    parsed, review = _parse_row(
        {
            "Importe": "+75,00",  # abono (signo +)
            "Fecha": "2026-06-23",
            "Concepto": "Bizum de Jose",  # sin RECIBIDA/REALIZADA
            "Categoria": "Bizum de Jose",
        },
        mappings=_MAPPING,
        user_id=user_id,
        currency="EUR",
        category_lookup={},
        default_category_id=None,
        bank_mappings=bank_mappings,
        transfer_cat_ids=transfer_cat_ids,
        transfer_by_kind=transfer_by_kind,
        category_kinds=category_kinds,
        sibling_by_name_kind={},
    )
    # El signo (+) decide la dirección INCOME aunque el texto no la dijera.
    assert parsed.category_id == transfer_income
    assert review is None


def test_parse_row_transfer_flags_review_when_sibling_kind_missing() -> None:
    """PHASE-32 HIGH#4 — si la dirección (por signo o texto) contradice el
    kind de la categoría de transferencia resuelta pero NO existe categoría
    de transferencia del kind correcto, se DEJA la categoría pero se marca la
    fila para revisión — nunca se persiste un signo invertido en silencio
    (bug 'BBVA a 0 con ingreso neto')."""
    user_id = uuid.uuid4()
    transfer_expense = uuid.uuid4()
    transfer_cat_ids = {transfer_expense}
    # Sólo existe la de GASTO; falta la hermana de INGRESO.
    transfer_by_kind = {CategoryKind.EXPENSE: transfer_expense}
    category_kinds = {transfer_expense: CategoryKind.EXPENSE}
    bank_mappings = {"bizum de jose": transfer_expense}

    parsed, review = _parse_row(
        {
            "Importe": "+90,00",  # abono → dirección INCOME
            "Fecha": "2026-06-23",
            "Concepto": "Bizum de Jose",
            "Categoria": "Bizum de Jose",
        },
        mappings=_MAPPING,
        user_id=user_id,
        currency="EUR",
        category_lookup={},
        default_category_id=None,
        bank_mappings=bank_mappings,
        transfer_cat_ids=transfer_cat_ids,
        transfer_by_kind=transfer_by_kind,
        category_kinds=category_kinds,
        sibling_by_name_kind={},
    )
    # No hay hermana INCOME: la categoría se queda (EXPENSE) PERO se marca.
    assert parsed.category_id == transfer_expense
    assert review is not None
    assert "revisa" in review.lower()


# ─────────────────────────────────────────────────────────────────────────────
# Finding #2 — el hash incluye ordinal de ocurrencia
# ─────────────────────────────────────────────────────────────────────────────


def test_compute_hash_occurrence_zero_is_backward_compatible() -> None:
    uid = uuid.uuid4()
    when = datetime(2026, 6, 23)
    base = dict(user_id=uid, amount=Decimal("3.50"), currency="EUR", occurred_at=when)
    default = _compute_hash(description="Cafe", **base)
    explicit_zero = _compute_hash(description="Cafe", occurrence=0, **base)
    assert default == explicit_zero  # imports históricos siguen idempotentes


def test_compute_hash_distinct_per_occurrence() -> None:
    uid = uuid.uuid4()
    when = datetime(2026, 6, 23)
    base = dict(
        user_id=uid,
        amount=Decimal("3.50"),
        currency="EUR",
        occurred_at=when,
        description="Cafe",
    )
    h0 = _compute_hash(occurrence=0, **base)
    h1 = _compute_hash(occurrence=1, **base)
    h2 = _compute_hash(occurrence=2, **base)
    assert len({h0, h1, h2}) == 3  # tres ocurrencias → tres hashes


# ─────────────────────────────────────────────────────────────────────────────
# Finding #7 — `valor` suelto fuera de los hints de fecha (parser)
# ─────────────────────────────────────────────────────────────────────────────


def test_standalone_valor_not_a_date_hint() -> None:
    assert "valor" not in _DATE_HEADER_HINTS


def test_valoracion_header_not_classified_as_date() -> None:
    """`Valoración` ya no se confunde con una columna de fecha (regresión
    del bug: `valor` hacía match por substring)."""
    roles = _classify_columns(["Concepto", "Importe", "Valoracion", "Saldo"])
    assert "occurred_at" not in roles


def test_fecha_valor_header_still_detected_as_date() -> None:
    roles = _classify_columns(["Concepto", "Importe", "Fecha valor", "Saldo"])
    assert roles.get("occurred_at") == 2


def test_operation_date_wins_over_value_date() -> None:
    roles = _classify_columns(["Fecha", "Concepto", "Importe", "Fecha valor", "Saldo"])
    assert roles.get("occurred_at") == 0


# ─────────────────────────────────────────────────────────────────────────────
# Integración (DB + HTTP) — findings #1, #2, #3
# ─────────────────────────────────────────────────────────────────────────────


async def _register(client: AsyncClient, email: str) -> tuple[str, str]:
    r = await client.post(
        "/auth/register",
        json={"email": email, "password": "SecurePass123", "display_name": "Audit"},
    )
    token = r.json()["access_token"]
    acc = await client.post(
        "/accounts",
        json={"name": "Cuenta", "type": "bank", "currency": "EUR"},
        headers={"Authorization": f"Bearer {token}"},
    )
    return token, acc.json()["id"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _post_csv(client: AsyncClient, token: str, account_id: str, csv_text: str) -> dict:
    files = {"file": ("import.csv", csv_text.encode("utf-8"), "text/csv")}
    data = {
        "account_id": account_id,
        "currency": "EUR",
        "column_mappings": json.dumps(
            {"amount": "importe", "occurred_at": "fecha", "description": "descripcion"}
        ),
    }
    r = await client.post("/imports", files=files, data=data, headers=_auth(token))
    assert r.status_code == 201, r.text
    return r.json()


async def test_import_two_identical_same_day_lines_both_persist(
    client: AsyncClient, test_engine
) -> None:
    """Finding #2 end-to-end: dos cafés idénticos el mismo día se importan
    ambos (no colapsan por hash)."""
    token, account_id = await _register(client, "audit-dup@example.com")
    csv_text = (
        "fecha,importe,descripcion\n" "2026-06-23,-3.50,Cafe bar\n" "2026-06-23,-3.50,Cafe bar\n"
    )
    job = await _post_csv(client, token, account_id, csv_text)
    assert job["rows_ok"] == 2
    assert job["rows_skipped"] == 0


async def test_reimport_same_file_is_idempotent(client: AsyncClient, test_engine) -> None:
    """Finding #2: re-importar el MISMO fichero no duplica (mismos
    ordinales → mismos hashes → skipped)."""
    token, account_id = await _register(client, "audit-idem@example.com")
    csv_text = (
        "fecha,importe,descripcion\n" "2026-06-23,-3.50,Cafe bar\n" "2026-06-23,-3.50,Cafe bar\n"
    )
    first = await _post_csv(client, token, account_id, csv_text)
    assert first["rows_ok"] == 2
    second = await _post_csv(client, token, account_id, csv_text)
    assert second["rows_ok"] == 0
    assert second["rows_skipped"] == 2

    factory = async_sessionmaker(bind=test_engine, expire_on_commit=False)
    async with factory() as db:
        count = len(
            (
                await db.execute(
                    select(Transaction.id).where(Transaction.account_id == uuid.UUID(account_id))
                )
            ).all()
        )
    assert count == 2  # no se duplicó al re-importar


async def test_import_persists_amount_magnitude_with_signed_statement(
    client: AsyncClient, test_engine
) -> None:
    """Finding #1: el importe se persiste SIEMPRE positivo aunque el
    extracto traiga signo (el signo es señal de dirección, no se guarda en
    `amount`)."""
    token, account_id = await _register(client, "audit-sign@example.com")
    csv_text = "fecha,importe,descripcion\n2026-06-23,-29.66,Compra super\n"
    job = await _post_csv(client, token, account_id, csv_text)
    assert job["rows_ok"] == 1

    factory = async_sessionmaker(bind=test_engine, expire_on_commit=False)
    async with factory() as db:
        tx = (
            await db.execute(
                select(Transaction).where(Transaction.account_id == uuid.UUID(account_id))
            )
        ).scalar_one()
    assert tx.amount == Decimal("29.66")  # magnitud positiva


# ─────────────────────────────────────────────────────────────────────────────
# PHASE-37 (bugfix) — guard de dirección ambigua en el autoaprendizaje
# ("BIZUM" que entra y sale no debe fijar una equivalencia aprendida)
# ─────────────────────────────────────────────────────────────────────────────


def _amt_row(amount: str, concept: str) -> dict[str, str]:
    return {"Importe": amount, "Fecha": "2026-06-23", "Concepto": "x", "Categoria": concept}


def test_direction_ambiguous_detects_concept_with_both_signs() -> None:
    """Un concepto con cargo (−) y abono (+) en el lote es ambiguo."""
    rows = [
        _amt_row("-30,00", "BIZUM"),
        _amt_row("+25,00", "BIZUM"),
        _amt_row("-10,00", "GASOLINA"),  # una sola dirección
    ]
    assert _direction_ambiguous_concepts(rows, _MAPPING) == {"bizum"}


def test_direction_ambiguous_ignores_single_direction_concept() -> None:
    """Un reembolso recurrente (solo abonos) NO es ambiguo — se sigue
    aprendiendo con normalidad, sin falsos positivos."""
    rows = [_amt_row("+25,00", "DEVOLUCION AMZN"), _amt_row("+30,00", "DEVOLUCION AMZN")]
    assert _direction_ambiguous_concepts(rows, _MAPPING) == set()


def test_direction_ambiguous_ignores_unsigned_rows() -> None:
    """Sin signo en el extracto (sign 0) no hay evidencia de dirección."""
    rows = [_amt_row("25,00", "BIZUM"), _amt_row("30,00", "BIZUM")]
    assert _direction_ambiguous_concepts(rows, _MAPPING) == set()


def test_direction_ambiguous_empty_without_category_mapping() -> None:
    mapping = ImportColumnMappings(
        amount="Importe", occurred_at="Fecha", description="Concepto", category_name=None
    )
    assert _direction_ambiguous_concepts([_amt_row("-1,00", "x")], mapping) == set()


async def _create_category(client: AsyncClient, token: str, name: str) -> dict:
    r = await client.post(
        "/categories",
        json={"name": name, "kind": "income"},
        headers=_auth(token),
    )
    assert r.status_code == 201, r.text
    return r.json()


async def test_persist_overrides_skips_learning_ambiguous_concept(
    client: AsyncClient, test_engine
) -> None:
    """El override de un concepto ambiguo se APLICA a esta importación
    (`valid`) pero NO se persiste como equivalencia aprendida (`skip_learn`),
    para no envenenar futuras. Un concepto normal sí se aprende."""
    token, _account_id = await _register(client, "audit-ambiguous@example.com")
    cat = await _create_category(client, token, "Bizum recibido")
    user_id = uuid.UUID(cat["user_id"])
    cat_id = uuid.UUID(cat["id"])

    factory = async_sessionmaker(bind=test_engine, expire_on_commit=False)
    async with factory() as db:
        valid = await _persist_user_category_overrides(
            db,
            user_id,
            {"BIZUM": cat_id, "NOMINA": cat_id},
            skip_learn=frozenset({"bizum"}),
        )
        await db.commit()
        learned = await get_mappings_for_concepts(db, user_id, ["bizum", "nomina"])

    # Ambiguo: aplicado a esta importación pero NO aprendido.
    assert valid["bizum"] == cat_id
    assert "bizum" not in learned
    # Normal: aprendido para futuras importaciones.
    assert valid["nomina"] == cat_id
    assert learned.get("nomina") == cat_id
