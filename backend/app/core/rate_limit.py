"""Rate limiting ligero en memoria (AUDIT-2026-05 no-rate-limiting-auth).

Sliding-window por `(IP, path)`. Sin dependencias externas ni Redis: la app
es self-hosted single-process, así que un bucket en memoria es suficiente.
Se DESACTIVA bajo pytest para no romper el suite (que golpea login/register
muchas veces). Para un despliegue multi-proceso, migrar a slowapi + redis.

Uso: en el decorador de ruta, `dependencies=[Depends(rate_limit(10, 60))]`.
La dependencia tiene su propio `Request`, así que no hay que tocar la firma
del endpoint.
"""

from __future__ import annotations

import sys
import time
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable

from fastapi import HTTPException, Request, status

# Bajo pytest el limiter es un no-op (el suite registra/loguea en bucle).
_ENABLED = "pytest" not in sys.modules
# Cota anti-crecimiento del dict de buckets (en la práctica hay pocas IPs).
_MAX_KEYS = 10_000
_buckets: dict[str, deque[float]] = defaultdict(deque)


def rate_limit(max_calls: int, window_seconds: int) -> Callable[[Request], Awaitable[None]]:
    """Dependencia FastAPI: limita a `max_calls` por `window_seconds` por
    `(IP, path)`. Lanza 429 al exceder."""

    async def _dependency(request: Request) -> None:
        if not _ENABLED:
            return
        if len(_buckets) > _MAX_KEYS:  # purga defensiva (improbable).
            _buckets.clear()
        client = request.client.host if request.client else "unknown"
        key = f"{client}:{request.url.path}"
        now = time.monotonic()
        bucket = _buckets[key]
        cutoff = now - window_seconds
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()
        if len(bucket) >= max_calls:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Demasiadas peticiones. Inténtalo de nuevo en un momento.",
            )
        bucket.append(now)

    return _dependency
