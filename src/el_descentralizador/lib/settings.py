from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path


def get_env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def _as_bool(value: str) -> bool:
    return value.lower() in {"1", "true", "si", "yes", "on"}


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PACKAGE_ROOT.parent.parent


@dataclass(frozen=True)
class DatabaseSettings:
    url: str = field(
        default_factory=lambda: get_env(
            "DATABASE_URL",
            "postgresql+asyncpg://app:app@localhost:5432/app",
        )
    )
    echo: bool = field(default_factory=lambda: _as_bool(get_env("DATABASE_ECHO", "false")))
    pool_size: int = field(default_factory=lambda: int(get_env("DATABASE_POOL_SIZE", "10")))


@dataclass(frozen=True)
class RedisSettings:
    url: str = field(default_factory=lambda: get_env("REDIS_URL", "redis://localhost:6379/0"))


@dataclass(frozen=True)
class AdminSettings:
    username: str = field(default_factory=lambda: get_env("ADMIN_USERNAME", "admin"))
    password: str = field(default_factory=lambda: get_env("ADMIN_PASSWORD", "admin"))


@dataclass(frozen=True)
class SaqSettings:
    web_enabled: bool = field(default_factory=lambda: _as_bool(get_env("SAQ_WEB_ENABLED", "false")))
    use_server_lifespan: bool = field(
        default_factory=lambda: _as_bool(get_env("SAQ_USE_SERVER_LIFESPAN", "true"))
    )


@dataclass(frozen=True)
class AppSettings:
    name: str = field(default_factory=lambda: get_env("APP_NAME", "El Descentralizador"))
    debug: bool = field(default_factory=lambda: _as_bool(get_env("APP_DEBUG", "false")))
    secret_key: str = field(
        default_factory=lambda: get_env("SECRET_KEY", "change-me-in-production")
    )
    repo_url: str = field(
        default_factory=lambda: get_env(
            "REPO_URL",
            "https://github.com/roberttson/el-descentralizador",
        )
    )
    catalog_csv: Path = field(
        default_factory=lambda: Path(
            get_env(
                "CATALOG_CSV",
                str(PACKAGE_ROOT / "data" / "medios_rss_actualizado.csv"),
            )
        )
    )
    database: DatabaseSettings = field(default_factory=DatabaseSettings)
    redis: RedisSettings = field(default_factory=RedisSettings)
    admin: AdminSettings = field(default_factory=AdminSettings)
    saq: SaqSettings = field(default_factory=SaqSettings)


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    return AppSettings()
