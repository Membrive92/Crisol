"""Configuración global del backend.

Todas las variables de entorno del backend se leen aquí vía Pydantic Settings.
Ningún otro archivo debe leer `os.environ` directamente.
"""

from __future__ import annotations

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Valor placeholder del secreto JWT — público (está en el repo). Si llega a
# un entorno no-dev sin sobreescribir, cualquiera podría forjar tokens.
_DEFAULT_JWT_SECRET = "DEV-ONLY-CHANGE-ME-IN-DOT-ENV-PLEASE-32B"
# Entornos donde NO se exige config endurecida (dev local + CI).
_NON_PROD_ENVS = frozenset({"development", "test"})


class Settings(BaseSettings):
    """Configuración del backend cargada desde variables de entorno / `.env`."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---------- App ----------
    app_env: str = "development"
    app_debug: bool = False
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    # ---------- Database ----------
    database_url: str = "postgresql+asyncpg://crisol:crisol@localhost:5432/crisol"
    # BD aislada para tests. Se crea automáticamente desde conftest si no
    # existe. Nunca debe coincidir con `database_url` — los tests truncan
    # tablas tras cada test y haría desaparecer datos de desarrollo.
    test_database_url: str = "postgresql+asyncpg://crisol:crisol@localhost:5432/crisol_test"

    # ---------- Auth ----------
    # Default cumple los 32 bytes mínimos para silenciar la advertencia de
    # `PyJWT`, pero NO es seguro: cada despliegue debe sobreescribirlo en `.env`
    # con algo generado por `openssl rand -hex 32` o `secrets.token_hex(32)`.
    jwt_secret_key: str = _DEFAULT_JWT_SECRET
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 7
    # TTL extendido cuando el cliente pide "Recordarme" en el login.
    jwt_refresh_token_remember_me_expire_days: int = 30

    # Cookie del refresh token (web). Mobile sigue usando expo-secure-store
    # y enviando el refresh en el body — el backend acepta ambos.
    auth_cookie_name: str = "crisol_refresh"
    auth_cookie_secure: bool = False  # ponerlo a true en prod (HTTPS).
    auth_cookie_samesite: str = "lax"  # lax | strict | none (none requiere secure).

    # ---------- WebAuthn / Passkeys ----------
    # `rp_id` es el dominio que firma las credenciales — en dev coincide con
    # el host del navegador (ej. localhost). `rp_name` es lo que ven los
    # usuarios en el diálogo del SO. `origin` es el origin completo que
    # debe coincidir con el del cliente (incl. puerto en dev).
    webauthn_rp_id: str = "localhost"
    webauthn_rp_name: str = "Crisol"
    webauthn_origin: str = "http://localhost:3030"
    webauthn_challenge_ttl_seconds: int = 300

    # ---------- Ollama (IA local) ----------
    ollama_base_url: str = "http://localhost:11434"
    ollama_vision_model: str = "qwen2.5vl:7b"
    # Modelo de texto puro para tareas tipo "sugiere categoría". Default
    # al mismo que visión (qwen2.5vl acepta texto solo), pero se puede
    # sobreescribir vía env a un modelo más liviano (qwen2.5:3b,
    # llama3.2:3b) si el host tiene poca RAM/VRAM.
    ollama_text_model: str = "qwen2.5vl:7b"
    ollama_timeout_seconds: int = 120

    # ---------- Frankfurter (exchange rates) ----------
    # frankfurter.dev es un proxy open-source del feed diario del ECB.
    # No requiere API key. No envía datos del usuario — sólo fechas y
    # códigos de moneda públicos. Compatible con el principio
    # "los datos del usuario nunca salen del equipo". El dominio
    # `frankfurter.app` original responde 301 al `.dev/v1` desde
    # primavera 2026; usamos el destino directo para evitar el hop.
    frankfurter_base_url: str = "https://api.frankfurter.dev/v1"
    frankfurter_timeout_seconds: int = 10

    # Cron nocturno que dispara `ensure_rates_for_dates([yesterday, today])`
    # — cubre el lazy fetch para usuarios que pasan días sin abrir la app.
    # Default activado en prod; tests lo sobrescriben a False vía env para
    # no acoplar el suite a un timer.
    enable_currency_cron: bool = True
    # Hora UTC del job (por defecto 03:00 — frankfurter ya tiene el feed
    # del ECB del día publicado y la mayoría de zonas horarias están en
    # ventana baja de tráfico).
    currency_cron_hour: int = 3
    currency_cron_minute: int = 0

    # Cron diario de detección de gastos fijos (PHASE-13.1, renombrado
    # PHASE-17.1). Itera todos los usuarios activos y persiste
    # candidatos como `pending`. Default activado en prod; tests lo
    # apagan vía env.
    enable_fixed_expenses_cron: bool = True
    # Por defecto 04:00 UTC — después del cron de tasas para que un
    # scan use tasas frescas si en el futuro la detección las usa.
    fixed_expenses_cron_hour: int = 4
    fixed_expenses_cron_minute: int = 0

    # ---------- MinIO (blob storage) ----------
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket_receipts: str = "receipts"
    minio_secure: bool = False

    # ---------- EDGAR (fundamentales del módulo Inversión) ----------
    # La SEC exige identificarse en el User-Agent ("Nombre email") para
    # descargar datos. Vacía por defecto: la ingesta falla con un mensaje
    # accionable en vez de arrancar y que la SEC devuelva 403 a mitad. NO se
    # persiste en ningún sitio salvo aquí — sólo viaja en la cabecera.
    edgar_identity: str = ""
    # Payloads crudos de `companyfacts` (evidencia de auditoría, Dec.18).
    # Relativa al directorio del backend. Excluida de git: 3-4 MB por empresa.
    edgar_cache_dir: str = "data/edgar_cache"
    # Ejercicios a ingerir por defecto. 5 cubre las ventanas de la capa
    # evolutiva (crecimiento, σ de márgenes) sin descargar historia inútil.
    edgar_filings_back: int = 5
    edgar_timeout_seconds: int = 60

    # ---------- Precios (módulo Inversión) ----------
    # Proveedor de cotizaciones. Sin `finnhub_api_key` las cotizaciones y la
    # búsqueda externa quedan DESACTIVADAS (la cartera funciona con datos
    # manuales; el valor de mercado sale "sin cotización"), no rompe nada.
    price_provider: str = "finnhub"
    finnhub_api_key: str = ""
    # Frescura máxima antes de refrescar on-access. 24h por defecto; poner 1
    # para refresco horario.
    price_ttl_hours: int = 24
    price_timeout_seconds: int = 15

    # ---------- CORS ----------
    cors_origins: str = "http://localhost:3000,http://localhost:8081"

    @property
    def cors_origins_list(self) -> list[str]:
        """Devuelve los orígenes CORS como lista."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @model_validator(mode="after")
    def _enforce_prod_hardening(self) -> Settings:
        """Falla AL ARRANCAR si la config es insegura fuera de dev/test.

        AUDIT-2026-05 (weak-default-jwt-secret): la app NO debe arrancar
        con el secreto JWT por defecto / corto, credenciales MinIO por
        defecto, `app_debug` o CORS wildcard en un entorno productivo. En
        `development`/`test` se omiten estas comprobaciones.
        """
        if self.app_env in _NON_PROD_ENVS:
            return self
        problems: list[str] = []
        if self.jwt_secret_key == _DEFAULT_JWT_SECRET or len(self.jwt_secret_key) < 32:
            problems.append(
                "JWT_SECRET_KEY debe sobreescribirse con >= 32 bytes "
                "(p.ej. `secrets.token_hex(32)`)"
            )
        if self.minio_access_key == "minioadmin" or self.minio_secret_key == "minioadmin":
            problems.append("MINIO_ACCESS_KEY / MINIO_SECRET_KEY no pueden ser 'minioadmin'")
        if self.app_debug:
            problems.append("APP_DEBUG debe ser false fuera de desarrollo")
        if "*" in self.cors_origins:
            problems.append("CORS_ORIGINS no puede ser un wildcard")
        if problems:
            raise ValueError(
                f"Configuración insegura para app_env={self.app_env!r}: "
                + "; ".join(problems)
                + ". Define estas variables en el entorno antes de arrancar."
            )
        return self


settings = Settings()
