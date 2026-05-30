"""Schemas Pydantic del módulo ai."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Los modelos de visión locales son inconsistentes con el formato pese a lo
# que diga el prompt: a veces devuelven números en formato español (`27,66`)
# y fechas en `DD/MM/YY`. En vez de luchar con el prompt, normalizamos en el
# parser — es determinista y barato.


def _coerce_decimal(value: Any) -> Any:
    """Normaliza un decimal en formato europeo (`27,66` → `27.66`).

    Pydantic v2 acepta strings con `.` o numéricos; le entregamos algo que ya
    sepa parsear. Para None / valores no string lo devolvemos tal cual.
    """
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return None
        # Si lleva tanto `.` como `,` asumimos que `.` es separador de miles
        # (formato español: `1.234,56`); nos quedamos sólo con la coma decimal.
        if "," in cleaned and "." in cleaned:
            cleaned = cleaned.replace(".", "")
        return cleaned.replace(",", ".")
    return value


def _coerce_datetime(value: Any) -> Any:
    """Acepta fechas en formato europeo (`19/02/26`, `19/02/2026 12:31`).

    Pydantic v2 espera ISO 8601. Si recibimos un string que parece europeo,
    lo convertimos. Si no, lo devolvemos tal cual y que Pydantic lo intente.
    """
    if not isinstance(value, str):
        return value
    s = value.strip()
    if not s:
        return None
    # Reemplaza `T` por espacio para uniformar (algunos modelos cuelan `19/02/26T12:31`).
    s_norm = s.replace("T", " ")
    formats = [
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M",
        "%d/%m/%Y",
        "%d/%m/%y %H:%M:%S",
        "%d/%m/%y %H:%M",
        "%d/%m/%y",
        "%d-%m-%Y %H:%M:%S",
        "%d-%m-%Y %H:%M",
        "%d-%m-%Y",
        "%d-%m-%y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(s_norm, fmt).isoformat()
        except ValueError:
            continue
    return value


class AiHealthResponse(BaseModel):
    """Respuesta del endpoint /ai/health."""

    status: str
    ollama: str
    model: str
    model_available: bool


class ReceiptLineItem(BaseModel):
    """Línea individual del ticket extraída por el modelo."""

    description: str = Field(min_length=1, max_length=255)
    quantity: Decimal | None = None
    unit_price: Decimal | None = None
    total: Decimal

    @field_validator("quantity", "unit_price", "total", mode="before")
    @classmethod
    def _normalize_decimals(cls, v: Any) -> Any:
        return _coerce_decimal(v)


class ReceiptExtraction(BaseModel):
    """Resultado de la extracción de un ticket por el modelo de visión.

    Estructura validada con Pydantic — si el modelo devuelve algo que no
    encaja, `ai.service.extract_receipt` lanza `AiInvalidOutputError`.
    """

    model_config = ConfigDict(extra="ignore")

    merchant: str | None = Field(default=None, max_length=255)
    occurred_at: datetime | None = None
    currency: str = Field(default="EUR", min_length=3, max_length=3)
    # `total` puede venir null cuando el modelo no consigue leerlo. La IA
    # sugiere y el usuario confirma — el formulario de confirmación exige
    # `amount`, así que no perdemos invariantes en BD si aquí permitimos null.
    total: Decimal | None = None
    tax: Decimal | None = None
    line_items: list[ReceiptLineItem] = Field(default_factory=list)
    raw_text: str | None = Field(default=None, max_length=5000)

    @field_validator("total", "tax", mode="before")
    @classmethod
    def _normalize_decimals(cls, v: Any) -> Any:
        return _coerce_decimal(v)

    @field_validator("occurred_at", mode="before")
    @classmethod
    def _normalize_date(cls, v: Any) -> Any:
        return _coerce_datetime(v)


class BankStatementRow(BaseModel):
    """Fila individual de un extracto bancario extraída por el modelo de visión.

    Se usa en el fallback de importación PDF cuando `pdfplumber` no encuentra
    tablas (PDFs escaneados). Cada fila se mapea 1:1 a una transacción.
    """

    model_config = ConfigDict(extra="ignore")

    description: str = Field(min_length=1, max_length=500)
    amount: Decimal = Field(gt=0)
    occurred_at: str = Field(min_length=1, max_length=64)

    @field_validator("amount", mode="before")
    @classmethod
    def _normalize_amount(cls, v: Any) -> Any:
        return _coerce_decimal(v)


class BankStatementPage(BaseModel):
    """Wrapper del JSON que devuelve el modelo para una página del extracto."""

    model_config = ConfigDict(extra="ignore")

    rows: list[BankStatementRow] = Field(default_factory=list)
