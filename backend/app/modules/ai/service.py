"""Servicio del módulo ai.

Encapsula los flujos de IA para que otros módulos del dominio
(`receipts/`, futuros) usen una interfaz tipada y no toquen Ollama
directamente.
"""

from __future__ import annotations

import json

from pydantic import ValidationError

from app.modules.ai import client
from app.modules.ai.exceptions import AiInvalidOutputError
from app.modules.ai.schemas import (
    BankStatementRow,
    ReceiptExtraction,
)

RECEIPT_PROMPT = """Eres un asistente que extrae datos estructurados de tickets de compra.

Analiza la imagen y devuelve EXCLUSIVAMENTE un objeto JSON con esta forma:

{
  "merchant": "nombre del comercio (string o null)",
  "occurred_at": "fecha y hora ISO 8601 (string o null)",
  "currency": "código ISO de 3 letras (default EUR)",
  "total": "importe total en formato decimal (string)",
  "tax": "impuestos en decimal (string o null)",
  "line_items": [
    {
      "description": "descripción del artículo",
      "quantity": "cantidad (string o null)",
      "unit_price": "precio unitario (string o null)",
      "total": "total de la línea (string)"
    }
  ],
  "raw_text": "texto completo del ticket (string o null)"
}

Reglas:
- Si un campo no se puede leer, usa null.
- Importes siempre con punto como separador decimal y sin símbolo de moneda.
- Si no detectas líneas individuales, devuelve `line_items: []`.
- No incluyas comentarios ni texto fuera del JSON."""


async def extract_receipt(image: bytes) -> ReceiptExtraction:
    """Extrae los datos estructurados de un ticket fotográfico.

    Pipeline:
        1. Llama al modelo de visión local con el prompt + imagen.
        2. Parsea la respuesta como JSON.
        3. Valida con `ReceiptExtraction`.

    Raises:
        AiUnavailable / AiTimeout: ver `ai.client`.
        AiInvalidOutputError: la respuesta no es JSON válido o no encaja
            con el schema esperado.
    """
    raw = await client.generate_with_image(prompt=RECEIPT_PROMPT, image=image)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise AiInvalidOutputError(f"Respuesta no es JSON: {raw[:200]!r}") from e

    try:
        return ReceiptExtraction.model_validate(data)
    except ValidationError as e:
        raise AiInvalidOutputError(f"Schema inválido: {e}") from e


BANK_STATEMENT_PROMPT = """Eres un asistente que extrae transacciones de extractos bancarios.

Analiza la imagen de la página y devuelve EXCLUSIVAMENTE un objeto JSON:

{
  "rows": [
    {
      "description": "concepto / contraparte (string, obligatorio)",
      "amount": "importe absoluto sin signo (string decimal con punto, obligatorio)",
      "occurred_at": "fecha en formato ISO YYYY-MM-DD o DD/MM/YYYY (string, obligatorio)"
    }
  ]
}

Reglas IMPORTANTES:
- Devuelve UNA fila por CADA línea de la tabla de movimientos. NO agrupes,
  NO consolides, NO sumes filas con descripción o fecha similares aunque
  parezcan duplicadas — cada línea visible en la tabla es una transacción
  independiente y debe aparecer por separado.
- Si en la tabla aparecen 5 cargos del mismo comercio el mismo día con
  importes distintos, devuelve 5 filas. Si aparecen 3 filas idénticas
  (misma fecha, mismo concepto, mismo importe), devuelve también 3 filas.
- Si una página no contiene tabla de movimientos, devuelve `rows: []`.
- Importes siempre positivos: el signo (gasto/ingreso) lo decide después
  el usuario asignando una categoría.
- No incluyas filas resumen (totales, saldo, encabezados, "Total ingresos",
  "Total gastos", "Balance neto", desgloses por categoría).
- No incluyas comentarios ni texto fuera del JSON."""


async def extract_bank_statement_page(image: bytes) -> list[BankStatementRow]:
    """Extrae las filas de transacciones de una página de extracto bancario.

    Pipeline igual que `extract_receipt`: prompt + visión + JSON + Pydantic.
    Devuelve sólo las filas; el caller agrega entre páginas.

    A nivel de fila somos tolerantes: si una fila falla validación
    (amount=0 o faltante, fecha vacía, etc.) la saltamos en lugar de
    abortar toda la página. Eso permite que un extracto mayoritariamente
    válido sobreviva si el modelo se confunde con una línea (típicamente
    de los desgloses por categoría que se cuelan con importe 0).

    Raises:
        AiUnavailable / AiTimeout: ver `ai.client`.
        AiInvalidOutputError: la respuesta no es JSON válido a nivel de
            página (objeto top-level malformado).
    """
    # Las páginas de extracto bancario tienen mucho más texto que un
    # ticket (default 120s). qwen2.5-vl en CPU puede tardar 3-5 min por
    # página, así que damos margen amplio. Si Ollama está en GPU baja
    # mucho, pero el timeout grande no penaliza al caso rápido.
    raw = await client.generate_with_image(
        prompt=BANK_STATEMENT_PROMPT,
        image=image,
        timeout_seconds=600,
    )
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise AiInvalidOutputError(f"Respuesta no es JSON: {raw[:200]!r}") from e

    if not isinstance(data, dict):
        raise AiInvalidOutputError(f"Respuesta no es objeto JSON: {data!r}")

    raw_rows = data.get("rows") or []
    if not isinstance(raw_rows, list):
        raise AiInvalidOutputError(f"`rows` no es lista: {type(raw_rows).__name__}")

    valid_rows: list[BankStatementRow] = []
    for raw_row in raw_rows:
        try:
            valid_rows.append(BankStatementRow.model_validate(raw_row))
        except ValidationError:
            # Fila inválida (e.g. amount=0 de categorías sin gasto). La
            # saltamos en silencio para que un único item raro no haga
            # caer la importación entera.
            continue
    return valid_rows


CATEGORY_SUGGEST_PROMPT_TEMPLATE = """Eres un asistente que clasifica conceptos bancarios en categorías de gasto/ingreso.

Categorías disponibles del usuario (ID — Nombre — Tipo):
{categories_block}

Conceptos del banco a clasificar (uno por línea, formato `ID|CONCEPTO|EJEMPLO_DESCRIPCION`):
{concepts_block}

Responde EXCLUSIVAMENTE con un objeto JSON:

{{
  "suggestions": [
    {{ "id": "<ID DEL CONCEPTO>", "category_id": "<ID DE LA CATEGORÍA O null>" }}
  ]
}}

Reglas:
- Para cada concepto de entrada, devuelve UNA suggestion con su `id` exacto.
- `category_id` debe ser uno de los IDs de la lista de categorías o `null`
  si ninguna encaja razonablemente (no inventes IDs).
- Considera tanto el CONCEPTO como el EJEMPLO_DESCRIPCION (a menudo el
  comercio real). Ejemplos: "PAGO TARJETA - RESTAURANTES" + "Mercadona" →
  Restaurantes; "PAGO TARJETA" + "NETFLIX" → Suscripciones.
- Para conceptos que pueden ser gastos o ingresos según el caso, elige la
  categoría con tipo más probable (usa "Tipo: ingreso" sólo cuando el
  concepto es claramente positivo, p.ej. "ABONO DE NOMINA").
- Sin texto fuera del JSON. Sin comentarios."""


async def suggest_categories_for_concepts(
    items: list[dict[str, str]],
    categories: list[dict[str, str]],
) -> dict[str, str | None]:
    """Pide al modelo de texto local que sugiera una categoría por
    concepto bancario.

    `items` — lista de dicts con keys `id`, `concept`, `description`.
        El `id` es opaco para el caller; el modelo lo devolverá en la
        respuesta y nosotros lo usamos para mapear.

    `categories` — lista de dicts con keys `id`, `name`, `kind`.

    Devuelve `{item_id: category_id | None}`. Items que el modelo no
    devolvió quedan fuera del dict (el caller los trata como "sin
    sugerencia"). Items con category_id que no pertenece al set de
    categorías válidas también se filtran (defensivo: el modelo a veces
    inventa IDs).

    Raises:
        AiUnavailable / AiTimeout: si Ollama falla.
        AiInvalidOutputError: respuesta no es JSON válido o no tiene
            la forma esperada.
    """
    if not items or not categories:
        return {}

    valid_category_ids = {c["id"] for c in categories}
    categories_block = "\n".join(f"{c['id']} — {c['name']} — {c['kind']}" for c in categories)
    concepts_block = "\n".join(
        f"{it['id']}|{it['concept']}|{it.get('description') or ''}" for it in items
    )
    prompt = CATEGORY_SUGGEST_PROMPT_TEMPLATE.format(
        categories_block=categories_block,
        concepts_block=concepts_block,
    )

    # Texto puro: 60s suelen bastar para 10-30 conceptos. Subimos a 180
    # para holgura en CPU lenta.
    raw = await client.generate_text(prompt=prompt, timeout_seconds=180)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise AiInvalidOutputError(f"Respuesta no es JSON: {raw[:200]!r}") from e

    if not isinstance(data, dict):
        raise AiInvalidOutputError(f"Respuesta no es objeto JSON: {data!r}")

    suggestions = data.get("suggestions") or []
    if not isinstance(suggestions, list):
        raise AiInvalidOutputError("`suggestions` no es lista")

    out: dict[str, str | None] = {}
    for entry in suggestions:
        if not isinstance(entry, dict):
            continue
        item_id = entry.get("id")
        cat_id = entry.get("category_id")
        if not isinstance(item_id, str):
            continue
        if cat_id is None:
            out[item_id] = None
            continue
        if not isinstance(cat_id, str):
            continue
        # Defensivo: si el modelo inventó un ID, lo descartamos como None.
        out[item_id] = cat_id if cat_id in valid_category_ids else None
    return out
