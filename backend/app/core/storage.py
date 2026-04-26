"""Cliente MinIO para almacenamiento de blobs (recibos, etc).

Único lugar del backend que conoce las credenciales de MinIO. Otros
módulos importan `storage.put_object` / `storage.get_object` y reciben
o entregan bytes.
"""

from __future__ import annotations

import io
import uuid
from datetime import UTC, datetime

from minio import Minio
from minio.error import S3Error

from app.core.config import settings


class StorageError(Exception):
    """Error al subir o leer un blob."""


_client: Minio | None = None
_buckets_ensured: set[str] = set()


def get_client() -> Minio:
    """Devuelve el singleton del cliente MinIO."""
    global _client
    if _client is None:
        _client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
    return _client


def _ensure_bucket(bucket: str) -> None:
    """Crea el bucket si no existe (idempotente, cacheado en memoria)."""
    if bucket in _buckets_ensured:
        return
    client = get_client()
    try:
        if not client.bucket_exists(bucket):
            client.make_bucket(bucket)
    except S3Error as e:
        raise StorageError(f"No se pudo crear/verificar el bucket {bucket}: {e}") from e
    _buckets_ensured.add(bucket)


def put_receipt(user_id: uuid.UUID, payload: bytes, content_type: str) -> str:
    """Sube los bytes de un recibo y devuelve la `object_key`.

    El path es `<user_id>/<YYYYMMDD>/<uuid>.<ext>` para facilitar
    auditorías y prefijos por usuario.
    """
    bucket = settings.minio_bucket_receipts
    _ensure_bucket(bucket)

    extension = _ext_from_content_type(content_type)
    today = datetime.now(UTC).strftime("%Y%m%d")
    key = f"{user_id}/{today}/{uuid.uuid4()}{extension}"

    client = get_client()
    try:
        client.put_object(
            bucket,
            key,
            io.BytesIO(payload),
            length=len(payload),
            content_type=content_type or "application/octet-stream",
        )
    except S3Error as e:
        raise StorageError(f"Subida fallida: {e}") from e

    return key


def get_receipt(object_key: str) -> bytes:
    """Descarga el blob como bytes."""
    bucket = settings.minio_bucket_receipts
    _ensure_bucket(bucket)
    client = get_client()
    try:
        response = client.get_object(bucket, object_key)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()
    except S3Error as e:
        raise StorageError(f"Descarga fallida ({object_key}): {e}") from e


def delete_receipt(object_key: str) -> None:
    """Elimina el blob (best-effort: ignora si no existe)."""
    bucket = settings.minio_bucket_receipts
    client = get_client()
    try:
        client.remove_object(bucket, object_key)
    except S3Error:
        return


_CONTENT_TYPE_EXT = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/heic": ".heic",
    "image/heif": ".heif",
}


def _ext_from_content_type(content_type: str | None) -> str:
    return _CONTENT_TYPE_EXT.get((content_type or "").lower(), ".bin")
