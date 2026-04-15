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

    # ---------- Auth ----------
    jwt_secret_key: str = "change-me-in-local-env"
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 7

    # ---------- CORS ----------
    cors_origins: str = "http://localhost:3000,http://localhost:8081"

    @property
    def cors_origins_list(self) -> list[str]:
        """Devuelve los orígenes CORS como lista."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
