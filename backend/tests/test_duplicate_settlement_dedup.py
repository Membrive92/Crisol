"""PHASE-47.E1 — Un recibo de tarjeta, escrito de varias formas, es UN cobro.

El banco escribe el recibo mensual de la tarjeta con dos redacciones —`Adeudo
mensual de tarjeta 4940…` y `Recibo mes anterior`— y las fecha distinto: la
fecha de la operación y la del apunte. Encima, el extracto de la cuenta y el de
la tarjeta lo traen los dos.

Medido en la BD del usuario, sobre siete ciclos: entre **2 y 4 filas por ciclo**
para un único cobro, todos los meses, con hasta 5 días de desfase entre la
primera y la última. Venía borrándolas a mano — unas veinte en siete meses.

El `import_hash` no puede hacer este trabajo: se calcula sobre fecha, importe y
texto, que es justo lo que difiere entre las copias. Hace falta una regla que
pregunte por el HECHO, no por la fila.

El test que de verdad importa aquí es el último de la primera sección: la
financiación del recibo es también un par del mismo importe y el mismo día, y
apagarla sería peor que el problema que se arregla — desaparecería la deuda que
nace. Lo que los separa es que sólo UNO de los dos es una liquidación.
"""

from __future__ import annotations

import io
import json

import openpyxl
import pytest
from httpx import AsyncClient

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
HEADER = ["Fecha", "Concepto", "Importe", "Saldo"]
MAPPING = {"amount": "Importe", "occurred_at": "Fecha", "description": "Concepto"}

ADEUDO = "Adeudo mensual de tarjeta 4940121100185049"
RECIBO = "RECIBO MES ANTERIOR"


def _xlsx(rows: list[list[str]]) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(HEADER)
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


async def _account(client: AsyncClient, token: str, name: str = "BBVA") -> str:
    r = await client.post(
        "/accounts",
        json={"name": name, "type": "bank", "currency": "EUR"},
        headers=_auth(token),
    )
    assert r.status_code == 201, r.text
    return str(r.json()["id"])


async def _import(
    client: AsyncClient,
    token: str,
    account_id: str,
    rows: list[list[str]],
    *,
    mappings: dict[str, str] | None = None,
) -> dict:
    """Importa un lote y devuelve el resumen del job confirmado."""
    r = await client.post(
        "/imports/preview",
        files={"file": ("extracto.xlsx", _xlsx(rows), XLSX_MIME)},
        data={"account_id": account_id, "column_mappings": json.dumps(mappings or MAPPING)},
        headers=_auth(token),
    )
    assert r.status_code == 200, r.text
    preview = r.json()
    job_id = preview["job_id"]
    warnings = [w["key"] for w in preview.get("warnings") or []]
    r = await client.post(
        f"/imports/{job_id}/commit",
        json={"category_overrides": {}, "acknowledged_warnings": warnings},
        headers=_auth(token),
    )
    assert r.status_code == 200, r.text
    return dict(r.json())


async def _descriptions(client: AsyncClient, token: str, account_id: str) -> list[str]:
    r = await client.get(
        "/transactions", params={"account_id": account_id, "limit": 100}, headers=_auth(token)
    )
    assert r.status_code == 200, r.text
    return [t["description"] for t in r.json()["items"]]


# ── Lo que colapsa ───────────────────────────────────────────────────


async def test_two_wordings_of_the_same_receipt_become_one_row(client: AsyncClient) -> None:
    """Las dos redacciones del mismo recibo, con dos días de desfase → una fila.

    Es el caso real de febrero de 2026: `ADEUDO MENSUAL DE TARJETA` el día 4 y
    `RECIBO MES ANTERIOR` el día 2, ambos por 264,84 €.
    """
    token = await _register(client, "dedup_dos_redacciones@example.com")
    account = await _account(client, token)

    result = await _import(
        client,
        token,
        account,
        [
            ["2026-02-02", RECIBO, "-264,84", "1000,00"],
            ["2026-02-04", ADEUDO, "-264,84", "1000,00"],
        ],
    )

    assert result["rows_ok"] == 1
    assert result["rows_skipped"] == 1
    # Sobrevive la copia que MÁS dice: la que trae el número de tarjeta.
    assert await _descriptions(client, token, account) == [ADEUDO]


async def test_a_receipt_already_registered_is_not_inserted_again(client: AsyncClient) -> None:
    """La copia llega en OTRO fichero, meses después → tampoco entra.

    Es como ocurre de verdad: el extracto de la cuenta y el de la tarjeta se
    importan por separado, así que la regla no puede mirar sólo dentro del lote.
    """
    token = await _register(client, "dedup_otro_fichero@example.com")
    account = await _account(client, token)

    await _import(client, token, account, [["2026-02-04", ADEUDO, "-264,84", "1000,00"]])
    result = await _import(client, token, account, [["2026-02-02", RECIBO, "-264,84", "900,00"]])

    assert result["rows_ok"] == 0
    assert result["rows_skipped"] == 1
    assert await _descriptions(client, token, account) == [ADEUDO]


# ── Lo que NO puede colapsar ─────────────────────────────────────────


async def test_two_receipts_of_different_amounts_both_survive(client: AsyncClient) -> None:
    """Dos tarjetas liquidando el mismo día son dos cobros.

    Ocurrió en enero de 2026: 166,00 € y 43,93 € el día 7. El importe tiene que
    coincidir EXACTO, y es lo que hace específica la regla.
    """
    token = await _register(client, "dedup_dos_importes@example.com")
    account = await _account(client, token)

    result = await _import(
        client,
        token,
        account,
        [
            ["2026-01-07", ADEUDO, "-166,00", "1000,00"],
            ["2026-01-07", ADEUDO, "-43,93", "956,07"],
        ],
    )

    assert result["rows_ok"] == 2


async def test_the_same_amount_a_cycle_apart_is_two_receipts(client: AsyncClient) -> None:
    """Dos meses seguidos con idéntico importe son dos cobros, no una copia.

    Pasó de verdad: 577,16 € en marzo y en abril. Es lo que acota la ventana —
    si fuera lo bastante ancha para alcanzar al ciclo siguiente, se comería un
    recibo entero.
    """
    token = await _register(client, "dedup_dos_ciclos@example.com")
    account = await _account(client, token)

    result = await _import(
        client,
        token,
        account,
        [
            ["2026-03-30", ADEUDO, "-577,16", "1000,00"],
            ["2026-04-29", ADEUDO, "-577,16", "422,84"],
        ],
    )

    assert result["rows_ok"] == 2


async def test_the_financing_pair_is_not_a_duplicate(client: AsyncClient) -> None:
    """El abono que financia el recibo y el cargo que lo salda: los DOS entran.

    Mismo importe, mismo día, misma cuenta — la forma exacta de un duplicado. Y
    sin embargo son el hecho contrario: uno de los dos no es una liquidación,
    es el nacimiento de una deuda (PHASE-46). Colapsarlos borraría de la app un
    aplazamiento entero y dejaría un cargo sin contrapartida.

    Es el test que decide si esta regla se puede tener: la señal que los separa
    no es la fecha ni el importe, sino que sólo UNO es una liquidación.
    """
    token = await _register(client, "dedup_financiacion@example.com")
    account = await _account(client, token)

    result = await _import(
        client,
        token,
        account,
        [
            ["2026-07-04", "Recibo anterior jun-26 Otras financiaciones", "700,26", "1417,36"],
            ["2026-07-04", "Recibo mes anterior No categorizable", "-700,26", "717,10"],
        ],
    )

    assert result["rows_ok"] == 2
    assert len(await _descriptions(client, token, account)) == 2


async def test_two_identical_purchases_are_not_deduped(client: AsyncClient) -> None:
    """Dos compras iguales el mismo día son dos compras.

    La regla mira SÓLO liquidaciones. Repetir el café de la mañana no es un
    duplicado, y el `import_hash` ya distingue las filas idénticas de verdad.
    """
    token = await _register(client, "dedup_compras@example.com")
    account = await _account(client, token)

    result = await _import(
        client,
        token,
        account,
        [
            ["2026-02-04", "MERCADONA", "-12,00", "1000,00"],
            ["2026-02-05", "MERCADONA", "-12,00", "988,00"],
        ],
    )

    assert result["rows_ok"] == 2


# ── Qué copia sobrevive ──────────────────────────────────────────────


@pytest.mark.parametrize("order", [("recibo", "adeudo"), ("adeudo", "recibo")])
async def test_the_surviving_copy_does_not_depend_on_file_order(
    client: AsyncClient, order: tuple[str, str]
) -> None:
    """Gane quien gane, gana lo mismo lea el fichero como lo lea.

    Sin desempate total, la copia superviviente dependería del orden de las
    filas — y BBVA imprime unos extractos de más reciente a más antiguo y otros
    al revés. El mismo mes importado desde dos ficheros daría textos distintos.
    """
    token = await _register(client, f"dedup_orden_{order[0]}@example.com")
    account = await _account(client, token)

    rows = {
        "recibo": ["2026-02-02", RECIBO, "-264,84", "1000,00"],
        "adeudo": ["2026-02-04", ADEUDO, "-264,84", "1000,00"],
    }
    result = await _import(client, token, account, [rows[order[0]], rows[order[1]]])

    assert result["rows_ok"] == 1
    assert await _descriptions(client, token, account) == [ADEUDO]


async def test_a_refund_of_the_receipt_is_not_a_duplicate_of_it(client: AsyncClient) -> None:
    """La DEVOLUCIÓN de un recibo tiene su forma exacta y es lo contrario.

    `amount` guarda la magnitud sin signo y el signo vive en `flow`
    (ADR-0004), así que el cargo y su devolución son idénticos para una regla
    que sólo mire importe y fecha: mismo importe, dos días, y las dos
    redacciones casan con la secuencia de liquidación. Sin comparar dirección,
    el banco te devuelve 264,84 € y la app se los come.
    """
    token = await _register(client, "dedup_devolucion@example.com")
    account = await _account(client, token)

    result = await _import(
        client,
        token,
        account,
        [
            ["2026-02-04", ADEUDO, "-264,84", "735,16"],
            ["2026-02-06", f"DEVOLUCION {ADEUDO}", "+264,84", "1000,00"],
        ],
    )

    assert result["rows_ok"] == 2
    assert len(await _descriptions(client, token, account)) == 2
