"""PHASE-47.A — El guardarraíl de "este fichero no es de esta cuenta".

En julio de 2026 el extracto de la TARJETA se importó eligiendo la cuenta del
BANCO. No falló nada: 19 filas OK, cero errores. 17 compras quedaron colgando
de la cuenta equivocada y el aplazamiento del recibo entró por partida doble.
La señal que lo destapó fue comparar el recuento de compras entre meses — no la
aplicación (`lessons.md`, PHASE-46).

Dos señales que cubren casos DISTINTOS:

- **F.1, huella de cabecera**: el fichero tiene el formato de los que importas
  en otra cuenta. Es la única que habría cazado julio, porque era la primera vez
  que ese fichero entraba.
- **F.2, solape de dedup**: parte de las filas ya existen en otra cuenta. Caza
  una RE-importación; en julio no habría dicho nada.

Ninguna prohíbe —el usuario puede tener razón—, pero confirmar exige reconocer
cada aviso: en julio no faltó información en pantalla, faltó una parada.
"""

from __future__ import annotations

import io
import json
import uuid

import openpyxl
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import settings
from app.modules.personal_finance.imports.models import ImportJob

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _xlsx(header: list[str], rows: list[list[str]]) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(header)
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


async def _register(client: AsyncClient, email: str) -> str:
    r = await client.post(
        "/auth/register",
        json={"email": email, "password": "SecurePass123", "display_name": "T"},
    )
    assert r.status_code in (200, 201), r.text
    return str(r.json()["access_token"])


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _account(client: AsyncClient, token: str, name: str, type_: str = "bank") -> str:
    r = await client.post(
        "/accounts",
        json={"name": name, "type": type_, "currency": "EUR"},
        headers=_auth(token),
    )
    assert r.status_code == 201, r.text
    return str(r.json()["id"])


async def _preview(
    client: AsyncClient,
    token: str,
    *,
    account_id: str,
    payload: bytes,
    mappings: dict[str, str],
    filename: str = "extracto.xlsx",
) -> dict:
    r = await client.post(
        "/imports/preview",
        files={"file": (filename, payload, XLSX_MIME)},
        data={"account_id": account_id, "column_mappings": json.dumps(mappings)},
        headers=_auth(token),
    )
    assert r.status_code == 200, r.text
    return dict(r.json())


async def _commit(
    client: AsyncClient, token: str, job_id: str, *, acknowledged: list[str] | None = None
):  # type: ignore[no-untyped-def]
    return await client.post(
        f"/imports/{job_id}/commit",
        json={"category_overrides": {}, "acknowledged_warnings": acknowledged or []},
        headers=_auth(token),
    )


@pytest_asyncio.fixture
async def session_factory(test_engine):  # type: ignore[no-untyped-def]
    return async_sessionmaker(bind=test_engine, expire_on_commit=False, autoflush=False)


async def _fingerprint_of(session_factory, job_id: str) -> str | None:  # type: ignore[no-untyped-def]
    """La huella persistida del job. Se lee de la BD y no de la API a
    propósito: es un detalle interno y no hay motivo para publicarlo."""
    async with session_factory() as db:
        row = await db.execute(
            select(ImportJob.header_fingerprint).where(ImportJob.id == uuid.UUID(job_id))
        )
        return row.scalar_one_or_none()


BANK_HEADER = ["Fecha", "Concepto", "Importe", "Saldo"]
CARD_HEADER = ["Fecha operacion", "Comercio", "Importe compra", "Cuotas"]
BANK_MAPPING = {"amount": "Importe", "occurred_at": "Fecha", "description": "Concepto"}
CARD_MAPPING = {
    "amount": "Importe compra",
    "occurred_at": "Fecha operacion",
    "description": "Comercio",
}


# ── F.1 · la huella tiene que DISCRIMINAR ────────────────────────────
#
# Estos dos tests son los que faltaban, y su ausencia dejó pasar el defecto que
# hacía inútil todo lo demás: la huella se calculaba sobre las CLAVES de las
# filas parseadas, y los dos smart-parsers las emiten fijas por contrato. Era la
# misma constante para todo PDF y todo XLSX de cualquier banco. Los tests de
# abajo pasaban igual, porque ninguno comparaba dos cabeceras distintas ni
# reproducía el caso real (la cuenta destino con historial propio).


async def test_two_different_headers_produce_different_fingerprints(
    client: AsyncClient,
    session_factory,  # type: ignore[no-untyped-def]
) -> None:
    """Dos ficheros con cabeceras distintas → huellas distintas.

    Es la premisa de la que cuelga F.1 entera. Sin este test, la señal puede
    ser una constante y el resto de la suite no se entera: un guardarraíl que
    no discrimina se lee exactamente igual que uno que no tiene nada que decir.
    """
    token = await _register(client, "guard_discrimina@example.com")
    bank = await _account(client, token, "BBVA")
    card = await _account(client, token, "Tarjeta BBVA", type_="credit_card")

    bank_job = await _preview(
        client,
        token,
        account_id=bank,
        payload=_xlsx(BANK_HEADER, [["2026-05-02", "NOMINA", "1500.00", "1500.00"]]),
        mappings=BANK_MAPPING,
    )
    card_job = await _preview(
        client,
        token,
        account_id=card,
        payload=_xlsx(CARD_HEADER, [["2026-05-10", "MERCADONA", "40.00", "1"]]),
        mappings=CARD_MAPPING,
    )

    bank_fp = await _fingerprint_of(session_factory, bank_job["job_id"])
    card_fp = await _fingerprint_of(session_factory, card_job["job_id"])

    assert bank_fp, "el extracto de cuenta no dejó huella"
    assert card_fp, "el extracto de tarjeta no dejó huella"
    assert bank_fp != card_fp, (
        "la huella NO discrimina: dos cabeceras distintas dan el mismo valor. "
        "Si se calcula sobre las claves del parser, son fijas por contrato y "
        "F.1 no puede avisar de nada."
    )


async def test_the_real_july_case_with_history_on_both_accounts(
    client: AsyncClient,
) -> None:
    """Julio de 2026, reproducido de verdad: las DOS cuentas con historial.

    El otro test de F.1 deja la cuenta destino sin ningún import previo, así que
    el aviso salta por «esta cuenta no ha visto nunca este formato» — y saltaría
    igual aunque las dos cabeceras fueran idénticas. El caso real es otro: BBVA
    llevaba meses importando SU extracto, así que la guarda `own` está activa y
    el aviso sólo puede salir si la huella distingue de verdad un formato de
    otro.
    """
    token = await _register(client, "guard_julio_real@example.com")
    bank = await _account(client, token, "BBVA")
    card = await _account(client, token, "Tarjeta BBVA", type_="credit_card")

    # Mayo y junio: cada extracto en su cuenta. Las dos acumulan su formato.
    for day, amount in (("2026-05-02", "1500.00"), ("2026-06-02", "1500.00")):
        job = await _preview(
            client,
            token,
            account_id=bank,
            payload=_xlsx(BANK_HEADER, [[day, "NOMINA", amount, "0.00"]]),
            mappings=BANK_MAPPING,
        )
        assert job["warnings"] == []
        assert (await _commit(client, token, job["job_id"])).status_code == 200
    for day, amount in (("2026-05-10", "40.00"), ("2026-06-10", "55.00")):
        job = await _preview(
            client,
            token,
            account_id=card,
            payload=_xlsx(CARD_HEADER, [[day, "MERCADONA", amount, "1"]]),
            mappings=CARD_MAPPING,
        )
        assert (await _commit(client, token, job["job_id"])).status_code == 200

    # Julio: el extracto de la TARJETA, a la cuenta del BANCO.
    july = await _preview(
        client,
        token,
        account_id=bank,
        payload=_xlsx(CARD_HEADER, [["2026-07-10", "MERCADONA", "60.00", "1"]]),
        mappings=CARD_MAPPING,
        filename="julio criedito.xlsx",
    )
    keys = [w["key"] for w in july["warnings"]]
    assert "header_matches_other_account" in keys, (
        "el caso que la fase existe para cazar pasó en silencio: BBVA tenía su "
        "propio formato registrado, así que si la huella no discrimina, la "
        "guarda `own` apaga el aviso"
    )


# ── F.1 · huella de cabecera ─────────────────────────────────────────


async def test_no_warning_when_the_format_is_the_one_this_account_always_uses(
    client: AsyncClient,
) -> None:
    """El extracto mensual de siempre no puede avisar: un guardarraíl que salta
    cada mes se aprende a ignorar, y con él el aviso que sí importa."""
    token = await _register(client, "guard_same@example.com")
    bank = await _account(client, token, "BBVA")

    first = await _preview(
        client,
        token,
        account_id=bank,
        payload=_xlsx(BANK_HEADER, [["2026-05-02", "NOMINA", "1500.00", "1500.00"]]),
        mappings=BANK_MAPPING,
    )
    assert first["warnings"] == []
    r = await _commit(client, token, first["job_id"])
    assert r.status_code == 200, r.text

    second = await _preview(
        client,
        token,
        account_id=bank,
        payload=_xlsx(BANK_HEADER, [["2026-06-02", "NOMINA", "1500.00", "3000.00"]]),
        mappings=BANK_MAPPING,
    )
    assert second["warnings"] == []


async def test_a_shared_format_warns_once_per_account_and_then_never_again(
    client: AsyncClient,
) -> None:
    """Dos cuentas del mismo banco comparten formato: avisa la PRIMERA vez y
    calla a partir de ahí.

    El coste está medido y es el que se acepta a propósito. Estrenar un formato
    conocido en una cuenta nueva tiene exactamente la misma forma que el error
    de julio —un fichero cuyo formato vive en otra cuenta— y desde la cabecera
    no hay manera de distinguirlos: el aviso salta una vez, el usuario lo
    reconoce, y esa cuenta ya no lo vuelve a ver. Lo que la guarda `own` impide
    es lo intolerable: recibirlo en CADA importación de por vida.

    Este test existe porque romper el código destapó que el otro —una sola
    cuenta reimportando su formato— no cubría la guarda: sin una segunda cuenta
    con la misma huella, la lista de «otras» sale vacía y el aviso no puede
    saltar por ningún camino.
    """
    token = await _register(client, "guard_two_same@example.com")
    payroll = await _account(client, token, "BBVA Nómina")
    savings = await _account(client, token, "BBVA Ahorro")

    first = await _preview(
        client,
        token,
        account_id=payroll,
        payload=_xlsx(BANK_HEADER, [["2026-05-02", "NOMINA", "1500.00", "1500.00"]]),
        mappings=BANK_MAPPING,
    )
    assert first["warnings"] == []
    assert (await _commit(client, token, first["job_id"])).status_code == 200

    # La cuenta de ahorro estrena el formato: avisa una vez.
    strange = await _preview(
        client,
        token,
        account_id=savings,
        payload=_xlsx(BANK_HEADER, [["2026-05-03", "TRASPASO", "100.00", "100.00"]]),
        mappings=BANK_MAPPING,
    )
    assert [w["key"] for w in strange["warnings"]] == ["header_matches_other_account"]
    assert (
        await _commit(
            client, token, strange["job_id"], acknowledged=["header_matches_other_account"]
        )
    ).status_code == 200

    # Y a partir de ahí, ninguna de las dos vuelve a verlo.
    for account_id, day in ((payroll, "2026-06-02"), (savings, "2026-06-03")):
        again = await _preview(
            client,
            token,
            account_id=account_id,
            payload=_xlsx(BANK_HEADER, [[day, "NOMINA", "1500.00", "1600.00"]]),
            mappings=BANK_MAPPING,
        )
        assert again["warnings"] == [], f"volvió a avisar en {account_id}"


async def test_warns_when_the_format_belongs_to_another_account(
    client: AsyncClient,
) -> None:
    """El caso de julio: el extracto de la tarjeta, a la cuenta del banco.

    Sin duplicados de por medio (es la primera vez que entra ese fichero), así
    que sólo la huella de cabecera puede decir algo.
    """
    token = await _register(client, "guard_cross@example.com")
    bank = await _account(client, token, "BBVA")
    card = await _account(client, token, "Tarjeta BBVA", type_="credit_card")

    # Mayo y junio: el extracto de la tarjeta entra donde debe.
    for day, amount in (("2026-05-10", "40.00"), ("2026-06-10", "55.00")):
        preview = await _preview(
            client,
            token,
            account_id=card,
            payload=_xlsx(CARD_HEADER, [[day, "MERCADONA", amount, "1"]]),
            mappings=CARD_MAPPING,
        )
        assert preview["warnings"] == []
        assert (await _commit(client, token, preview["job_id"])).status_code == 200

    # Julio: el mismo formato, pero eligiendo la cuenta del banco.
    july = await _preview(
        client,
        token,
        account_id=bank,
        payload=_xlsx(CARD_HEADER, [["2026-07-10", "MERCADONA", "60.00", "1"]]),
        mappings=CARD_MAPPING,
        filename="julio criedito.xlsx",
    )
    keys = [w["key"] for w in july["warnings"]]
    assert "header_matches_other_account" in keys
    warning = next(w for w in july["warnings"] if w["key"] == "header_matches_other_account")
    assert warning["account_id"] == card
    assert "Tarjeta BBVA" in warning["message"]


async def test_commit_is_blocked_until_the_warning_is_acknowledged(
    client: AsyncClient,
) -> None:
    """409 con los avisos pendientes dentro; con el tick, pasa.

    Es la diferencia entre informar y parar: en julio la información habría
    estado en pantalla y el usuario habría pulsado Confirmar igual.
    """
    token = await _register(client, "guard_block@example.com")
    bank = await _account(client, token, "BBVA")
    card = await _account(client, token, "Tarjeta BBVA", type_="credit_card")

    seed = await _preview(
        client,
        token,
        account_id=card,
        payload=_xlsx(CARD_HEADER, [["2026-05-10", "MERCADONA", "40.00", "1"]]),
        mappings=CARD_MAPPING,
    )
    assert (await _commit(client, token, seed["job_id"])).status_code == 200

    july = await _preview(
        client,
        token,
        account_id=bank,
        payload=_xlsx(CARD_HEADER, [["2026-07-10", "MERCADONA", "60.00", "1"]]),
        mappings=CARD_MAPPING,
    )
    assert july["warnings"]

    blocked = await _commit(client, token, july["job_id"])
    assert blocked.status_code == 409, blocked.text
    detail = blocked.json()["detail"]
    assert [w["key"] for w in detail["warnings"]] == ["header_matches_other_account"]

    ok = await _commit(client, token, july["job_id"], acknowledged=["header_matches_other_account"])
    assert ok.status_code == 200, ok.text
    assert ok.json()["rows_ok"] == 1


# ── F.2 · solape de dedup, a los dos lados del umbral ────────────────


async def _seed_ten_rows_in(client: AsyncClient, token: str, account_id: str) -> list[list[str]]:
    """Diez movimientos ya importados en `account_id`, y las filas que los
    reproducen para un fichero posterior."""
    rows = [[f"2026-05-{day:02d}", f"COMPRA {day}", f"{day}.00", "0.00"] for day in range(1, 11)]
    preview = await _preview(
        client,
        token,
        account_id=account_id,
        payload=_xlsx(BANK_HEADER, rows),
        mappings=BANK_MAPPING,
    )
    assert (await _commit(client, token, preview["job_id"])).status_code == 200
    return rows


async def test_overlap_below_the_threshold_does_not_warn(client: AsyncClient) -> None:
    """Un solape del 10 % (1 de 10) está por debajo del 20 % y no avisa.

    El test cae a los DOS lados del umbral con su hermano de abajo: un test que
    sólo comprueba que el guardarraíl salta no prueba lo que el guardarraíl
    protege ([PHASE-44.14]).
    """
    assert settings.import_cross_overlap_pct == 20
    token = await _register(client, "guard_below@example.com")
    bank = await _account(client, token, "BBVA")
    other = await _account(client, token, "Santander")
    seeded = await _seed_ten_rows_in(client, token, other)

    # 1 fila repetida + 9 nuevas: 10 % de solape. Cabecera DISTINTA para que
    # F.1 no contamine la medición de F.2.
    mixed = [seeded[0]] + [
        [f"2026-06-{day:02d}", f"NUEVA {day}", f"{day}.00", "0.00"] for day in range(1, 10)
    ]
    preview = await _preview(
        client,
        token,
        account_id=bank,
        payload=_xlsx(
            ["Fecha", "Concepto", "Importe", "Saldo", "Extra"], [[*r, ""] for r in mixed]
        ),
        mappings=BANK_MAPPING,
    )
    assert "rows_exist_in_other_account" not in [w["key"] for w in preview["warnings"]]


async def test_overlap_above_the_threshold_warns(client: AsyncClient) -> None:
    """Un solape del 100 % (10 de 10) supera el 20 % y avisa, con el recuento."""
    token = await _register(client, "guard_above@example.com")
    bank = await _account(client, token, "BBVA")
    other = await _account(client, token, "Santander")
    seeded = await _seed_ten_rows_in(client, token, other)

    preview = await _preview(
        client,
        token,
        account_id=bank,
        payload=_xlsx(
            ["Fecha", "Concepto", "Importe", "Saldo", "Extra"], [[*r, ""] for r in seeded]
        ),
        mappings=BANK_MAPPING,
    )
    warning = next(
        (w for w in preview["warnings"] if w["key"] == "rows_exist_in_other_account"), None
    )
    assert warning is not None, preview["warnings"]
    assert warning["matched_rows"] == 10
    assert warning["total_rows"] == 10
    assert "Santander" in warning["message"]


async def test_the_chosen_account_own_duplicates_never_warn(client: AsyncClient) -> None:
    """Reimportar el mismo fichero en SU cuenta es el dedup normal, no un
    error de cuenta: avisar ahí sería confundir dos cosas distintas."""
    token = await _register(client, "guard_own@example.com")
    bank = await _account(client, token, "BBVA")
    seeded = await _seed_ten_rows_in(client, token, bank)

    preview = await _preview(
        client,
        token,
        account_id=bank,
        payload=_xlsx(BANK_HEADER, seeded),
        mappings=BANK_MAPPING,
    )
    assert preview["warnings"] == []
