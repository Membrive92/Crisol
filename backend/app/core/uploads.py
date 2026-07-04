"""Helpers de subida de ficheros.

AUDIT-2026-07 (LOW): `await file.read()` sin tope carga TODO el cuerpo en
memoria antes de comprobar el tamaño, así que un fichero enorme se lee entero
sólo para rechazarlo. `read_upload_capped` lee en trozos y aborta en cuanto
supera el límite.
"""

from __future__ import annotations

from fastapi import HTTPException, UploadFile, status

_CHUNK = 1024 * 1024  # 1 MiB


async def read_upload_capped(file: UploadFile, max_size: int, *, detail: str) -> bytes:
    """Lee un `UploadFile` en trozos y ABORTA (413) si supera `max_size`.

    Devuelve los bytes leídos si no se excede el límite. Nunca acumula en
    memoria más de `max_size + un_trozo`.
    """
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(_CHUNK)
        if not chunk:
            break
        total += len(chunk)
        if total > max_size:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=detail,
            )
        chunks.append(chunk)
    return b"".join(chunks)
