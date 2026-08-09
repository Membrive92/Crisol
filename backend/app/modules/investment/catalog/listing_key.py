"""Clave opaca de un resultado del buscador (PHASE-44.8 E2, ADR-0008).

El cliente no manda plaza, ni divisa, ni CIK: manda **la clave que el servidor le
dio** y el servidor la vuelve a resolver. Es el movimiento de [PHASE-34] aplicado
al mercado —cambiar DÓNDE vive la verdad en vez de añadir otro guardarraíl sobre
la fuente equivocada—, y cierra por construcción el defecto que abrió esta fase:
el frontend escribía `exchange='US'`, que es un país, contra una restricción
única `(ticker, exchange)` que entonces convertía `MCD/US` y `MCD/NYSE` en dos
valores distintos.

Formatos:

| Clave | Origen | Qué sabe el servidor al re-resolverla |
|---|---|---|
| `cat:<uuid>` | ya está en el catálogo | todo: es una fila |
| `idx:<PLAZA>:<TICKER>` | índice de la SEC | la plaza real, que si no se perdería |
| `ext:<MIC>:<ISIN>` | directorio FIRDS UE/UK | la identidad registral completa |
| `typed:<TICKER>` | escotilla: lo tecleado | sólo el ticker → a EDGAR |

Módulo PURO: sin BD, sin red, sin reloj.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Literal

ListingSource = Literal["catalog", "sec_index", "external", "typed"]

#: Longitud canónica del CIK. La SEC lo publica con ceros a la izquierda
#: (`0000063908`) y el parquet de emisores lo trae como entero (`63908`). Son el
#: mismo emisor, y compararlos sin normalizar es un `False` silencioso: fue lo
#: que hizo que la deduplicación entre el catálogo y el índice no casara nunca,
#: devolviendo McDonald's dos veces — el duplicado exacto que este módulo existe
#: para evitar.
CIK_WIDTH = 10


def normalize_cik(value: str | int | None) -> str | None:
    """Cualquier forma de un CIK → la canónica de 10 dígitos, o `None`.

    Se aplica en TODA comparación de identidad. Devuelve `None` para lo que no
    sea un número: un CIK vacío o con letras no identifica a nadie, y tratarlo
    como cadena haría que dos filas rotas «coincidieran» entre sí.
    """
    if value is None:
        return None
    text = str(value).strip()
    if not text.isdigit():
        return None
    return text.zfill(CIK_WIDTH)


def is_valid_isin(value: str) -> bool:
    """Formato ISO 6166 + dígito de control (Luhn sobre la conversión letra→número).

    Se valida al parsear la clave `ext:` porque un ISIN con una errata no es
    «otro valor»: es basura que acabaría en una búsqueda del directorio vacía y
    en un 404 hablando de un instrumento que nunca existió.
    """
    if len(value) != 12 or not value[:2].isalpha() or not value[:11].isalnum():
        return False
    if not value[11].isdigit():
        return False
    digits = "".join(str(int(c, 36)) for c in value)
    total = 0
    for i, ch in enumerate(reversed(digits)):
        n = int(ch)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


class InvalidListingKeyError(ValueError):
    """La clave no tiene una forma que este servidor sepa re-resolver."""


@dataclass(frozen=True, slots=True)
class ParsedListingKey:
    """Clave ya validada. Sólo los campos de su `source` vienen informados, y
    por eso no se colapsan en uno: un UUID, un ticker y un ISIN no son la misma
    cosa aunque los tres quepan en un `str`."""

    source: ListingSource
    security_id: uuid.UUID | None = None
    ticker: str | None = None
    venue: str | None = None
    isin: str | None = None


def catalog_key(security_id: uuid.UUID) -> str:
    return f"cat:{security_id}"


def index_key(venue: str, ticker: str) -> str:
    return f"idx:{venue.upper()}:{ticker.upper()}"


def external_key(mic: str, isin: str) -> str:
    return f"ext:{mic.upper()}:{isin.upper()}"


def typed_key(ticker: str) -> str:
    return f"typed:{ticker.strip().upper()}"


def parse_listing_key(raw: str) -> ParsedListingKey:
    """Descompone la clave, o lanza `InvalidListingKeyError`.

    Deliberadamente estricta: una clave que no reconocemos se rechaza en vez de
    caer a «trátalo como un ticker». Ese fallback convertiría un error del
    cliente en una petición a EDGAR con basura, y el 404 resultante hablaría de
    un ticker que el usuario nunca escribió.
    """
    value = (raw or "").strip()
    if not value:
        raise InvalidListingKeyError("La clave del resultado viene vacía.")

    prefix, _, rest = value.partition(":")
    if not rest:
        raise InvalidListingKeyError(f"Clave sin cuerpo: {value!r}")

    if prefix == "cat":
        try:
            return ParsedListingKey(source="catalog", security_id=uuid.UUID(rest))
        except ValueError as exc:
            raise InvalidListingKeyError(f"Identificador de catálogo inválido: {rest!r}") from exc

    if prefix == "idx":
        venue, _, ticker = rest.partition(":")
        if not venue or not ticker:
            raise InvalidListingKeyError(f"Clave de índice mal formada: {value!r}")
        return ParsedListingKey(
            source="sec_index", ticker=ticker.strip().upper(), venue=venue.strip().upper()
        )

    if prefix == "ext":
        mic, _, isin = rest.partition(":")
        mic = mic.strip().upper()
        isin = isin.strip().upper()
        if len(mic) != 4 or not mic.isalnum():
            raise InvalidListingKeyError(f"MIC inválido en la clave: {mic!r}")
        if not is_valid_isin(isin):
            raise InvalidListingKeyError(f"ISIN inválido en la clave: {isin!r}")
        return ParsedListingKey(source="external", venue=mic, isin=isin)

    if prefix == "typed":
        ticker = rest.strip().upper()
        if not ticker:
            raise InvalidListingKeyError("Escotilla sin ticker.")
        return ParsedListingKey(source="typed", ticker=ticker)

    raise InvalidListingKeyError(f"Origen de resultado desconocido: {prefix!r}")
