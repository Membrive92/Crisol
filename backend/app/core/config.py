"""Configuración global del backend.

Todas las variables de entorno del backend se leen aquí vía Pydantic Settings.
Ningún otro archivo debe leer `os.environ` directamente.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


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
    database_url: str = "postgresql+asyncpg://finanzas:finanzas@localhost:5432/finanzas"
    # BD aislada para tests. Se crea automáticamente desde conftest si no
    # existe. Nunca debe coincidir con `database_url` — los tests truncan
    # tablas tras cada test y haría desaparecer datos de desarrollo.
    test_database_url: str = (
        "postgresql+asyncpg://finanzas:finanzas@localhost:5432/finanzas_test"
    )

    # ---------- Auth ----------
    # Default cumple los 32 bytes mínimos para silenciar la advertencia de
    # `PyJWT`, pero NO es seguro: cada despliegue debe sobreescribirlo en `.env`
    # con algo generado por `openssl rand -hex 32` o `secrets.token_hex(32)`.
    jwt_secret_key: str = "DEV-ONLY-CHANGE-ME-IN-DOT-ENV-PLEASE-32B"
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 7
    # TTL extendido cuando el cliente pide "Recordarme" en el login.
    jwt_refresh_token_remember_me_expire_days: int = 30

    # Cookie del refresh token (web). Mobile sigue usando expo-secure-store
    # y enviando el refresh en el body — el backend acepta ambos.
    auth_cookie_name: str = "finanzas_refresh"
    auth_cookie_secure: bool = False  # ponerlo a true en prod (HTTPS).
    auth_cookie_samesite: str = "lax"  # lax | strict | none (none requiere secure).

    # ---------- WebAuthn / Passkeys ----------
    # `rp_id` es el dominio que firma las credenciales — en dev coincide con
    # el host del navegador (ej. localhost). `rp_name` es lo que ven los
    # usuarios en el diálogo del SO. `origin` es el origin completo que
    # debe coincidir con el del cliente (incl. puerto en dev).
    webauthn_rp_id: str = "localhost"
    webauthn_rp_name: str = "Finanzas"
    webauthn_origin: str = "http://localhost:3030"
    webauthn_challenge_ttl_seconds: int = 300

    # ---------- Ollama (IA local) ----------
    ollama_base_url: str = "http://localhost:11434"
    ollama_vision_model: str = "qwen2.5vl:7b"
    ollama_timeout_seconds: int = 120

    # ---------- Frankfurter (exchange rates) ----------
    # frankfurter.app es un proxy open-source del feed diario del ECB.
    # No requiere API key. No envía datos del usuario — sólo fechas y
    # códigos de moneda públicos. Compatible con el principio
    # "los datos del usuario nunca salen del equipo".
    frankfurter_base_url: str = "https://api.frankfurter.app"
    frankfurter_timeout_seconds: int = 10

    # ---------- MinIO (blob storage) ----------
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket_receipts: str = "receipts"
    minio_secure: bool = False

    # ---------- CORS ----------
    cors_origins: str = "http://localhost:3000,http://localhost:8081"

    @property
    def cors_origins_list(self) -> list[str]:
        """Devuelve los orígenes CORS como lista."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
