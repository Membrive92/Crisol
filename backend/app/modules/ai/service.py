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
from app.modules.ai.schemas import ReceiptExtraction

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
