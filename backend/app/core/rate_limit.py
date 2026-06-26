"""Rate limiting ligero en memoria (AUDIT-2026-05 no-rate-limiting-auth).

Sliding-window por clave de cliente. Sin dependencias externas ni Redis: la
app es self-hosted single-process, así que un bucket en memoria es suficiente.
Se DESACTIVA bajo pytest para no romper el suite (que golpea login/register
muchas veces). Para un despliegue multi-proceso, migrar a slowapi + redis.

Uso: en el decorador de ruta, `dependencies=[Depends(rate_limit(10, 60))]`.
La dependencia tiene su propio `Request`, así que no hay que tocar la firma
del endpoint.

AUDIT-FIX (rate-limit-client-host-tras-proxy): cuando el tráfico web pasa por
el rewrite `/api/*` de Next.js (o cualquier reverse proxy), `request.client.host`
es la IP del proxy, no la del usuario → todos los clientes comparten un único
bucket y el rate-limit pierde sentido (o castiga a usuarios legítimos). La IP
real viaja en `X-Forwarded-For` / `X-Real-IP`, pero esas cabeceras las puede
falsificar cualquier cliente, así que SÓLO se confían cuando el primer hop
(`request.client.host`) es un proxy de confianza configurado. En producción
hay que listar la IP del reverse proxy en `RATE_LIMIT_TRUSTED_PROXIES`
(coma-separado); si no se configura, el default cubre el loopback típico de un
proxy co-localizado en la misma máquina.
"""

from __future__ import annotations

import sys
import time
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable

from fastapi import HTTPException, Request, status

from app.core.config import settings

# Bajo pytest el limiter es un no-op (el suite registra/loguea en bucle).
_ENABLED = "pytest" not in sys.modules
# Cota anti-crecimiento del dict de buckets (en la práctica hay pocas IPs).
_MAX_KEYS = 10_000
_buckets: dict[str, deque[float]] = defaultdict(deque)


# Proxies de confianza cuyos `X-Forwarded-For` / `X-Real-IP` aceptamos. Se lee
# de settings si existe la opción (`RATE_LIMIT_TRUSTED_PROXIES`, coma-separado);
# si no, default a loopback — cubre el caso por defecto de un reverse proxy
# (Caddy/Traefik/Nginx) o el dev server de Next.js corriendo en la misma
# máquina que el backend. `settings` ignora variables de entorno extra
# (`extra="ignore"`), así que esta opción se puede definir en `.env` sin tocar
# `config.py`; usamos `getattr` para no acoplarnos a que el campo exista.
def _trusted_proxies() -> frozenset[str]:
    raw = getattr(settings, "rate_limit_trusted_proxies", None)
    if not raw:
        return frozenset({"127.0.0.1", "::1"})
    return frozenset(p.strip() for p in str(raw).split(",") if p.strip())


def _real_client_ip(request: Request) -> str:
    """Deriva la IP real del cliente respetando SÓLO el primer hop de confianza.

    Si la conexión entrante viene de un proxy de confianza, se toma la primera
    IP de `X-Forwarded-For` (el cliente original) o, en su defecto,
    `X-Real-IP`. Si NO viene de un proxy de confianza, se ignoran ambas
    cabeceras (un cliente directo podría falsificarlas) y se usa la IP de la
    conexión TCP.
    """
    peer = request.client.host if request.client else "unknown"
    if peer not in _trusted_proxies():
        return peer
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        # `X-Forwarded-For: cliente, proxy1, proxy2` — el cliente es el primero.
        first = forwarded.split(",")[0].strip()
        if first:
            return first
    real_ip = request.headers.get("x-real-ip")
    if real_ip and real_ip.strip():
        return real_ip.strip()
    return peer


def get_client_key(request: Request) -> str:
    """Clave base del rate-limit para una petición: `<ip_real>:<path>`.

    Usa la IP real del cliente (resolviendo el primer hop de confianza) en vez
    de `request.client.host`, que tras un proxy es siempre la del proxy.
    """
    return f"{_real_client_ip(request)}:{request.url.path}"


async def _peek_email(request: Request) -> str | None:
    """Intenta extraer el `email` del body JSON para keyear el bucket de auth
    por cuenta. Devuelve `None` si el body no es JSON o no trae email.

    Lee el body de forma no destructiva (`request.body()` cachea internamente
    el contenido en Starlette, así que el handler downstream lo vuelve a leer
    sin problema). Cualquier error se traga: el rate-limit por IP sigue
    aplicando aunque el body no se pueda inspeccionar.
    """
    try:
        body = await request.body()
        if not body:
            return None
        import json

        data = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    email = data.get("email")
    if isinstance(email, str) and email.strip():
        return email.strip().lower()
    return None


def rate_limit(
    max_calls: int, window_seconds: int, *, per_email: bool = False
) -> Callable[[Request], Awaitable[None]]:
    """Dependencia FastAPI: limita a `max_calls` por `window_seconds`.

    Por defecto el bucket es `(IP_real, path)`. Con `per_email=True` —pensado
    para login— el bucket es `(IP_real, path, email)`: así un atacante que
    rota IPs no agota el cupo de una víctima concreta, y un ataque desde una
    sola IP contra muchas cuentas tampoco se enmascara. Lanza 429 al exceder.
    """

    async def _dependency(request: Request) -> None:
        if not _ENABLED:
            return
        if len(_buckets) > _MAX_KEYS:  # purga defensiva (improbable).
            _buckets.clear()
        key = get_client_key(request)
        if per_email:
            email = await _peek_email(request)
            if email is not None:
                key = f"{key}:{email}"
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
