from __future__ import annotations

from advanced_alchemy.extensions.litestar import (
    AlembicAsyncConfig,
    AsyncSessionConfig,
    EngineConfig,
    SQLAlchemyAsyncConfig,
    SQLAlchemyPlugin,
)
from litestar.stores.redis import RedisStore
from litestar_granian import GranianPlugin
from litestar_htmx import HTMXPlugin
from litestar_saq import CronJob, QueueConfig, SAQConfig, SAQPlugin
from redis.asyncio import Redis

from el_descentralizador.lib.settings import get_settings


def _build_sqlalchemy_config() -> SQLAlchemyAsyncConfig:
    settings = get_settings()
    return SQLAlchemyAsyncConfig(
        connection_string=settings.database.url,
        before_send_handler="autocommit",
        session_dependency_key="db_session",
        engine_dependency_key="db_engine",
        session_maker_app_state_key="alchemy_session_maker",
        engine_app_state_key="alchemy_engine",
        session_config=AsyncSessionConfig(expire_on_commit=False),
        engine_config=EngineConfig(
            echo=settings.database.echo,
            pool_size=settings.database.pool_size,
            pool_pre_ping=True,
        ),
        alembic_config=AlembicAsyncConfig(
            script_location="src/el_descentralizador/db/migrations",
        ),
    )


sqlalchemy_config_instance = _build_sqlalchemy_config()


def sqlalchemy_config() -> SQLAlchemyAsyncConfig:
    return sqlalchemy_config_instance


def alchemy_config() -> SQLAlchemyAsyncConfig:
    configs = sqlalchemy_plugin.config
    if isinstance(configs, list):
        return configs[0]
    return configs


def create_sqlalchemy_plugin() -> SQLAlchemyPlugin:
    return SQLAlchemyPlugin(config=sqlalchemy_config_instance)


def create_saq_plugin() -> SAQPlugin:
    settings = get_settings()
    return SAQPlugin(
        config=SAQConfig(
            use_server_lifespan=settings.saq.use_server_lifespan,
            web_enabled=settings.saq.web_enabled,
            queue_configs=[
                QueueConfig(
                    name="ingestion",
                    dsn=settings.redis.url,
                    tasks=["el_descentralizador.domain.ingestion.jobs.run_ingest"],
                    scheduled_tasks=[
                        CronJob(
                            function="el_descentralizador.domain.ingestion.jobs.run_ingest",
                            cron="0 * * * *",
                            timeout=600,
                        ),
                    ],
                ),
            ],
        ),
    )


def create_redis() -> Redis:
    return Redis.from_url(get_settings().redis.url, decode_responses=False)


def create_stores(redis: Redis) -> dict[str, RedisStore]:
    return {
        "sessions": RedisStore(redis, namespace="sessions"),
        "ingestion": RedisStore(redis, namespace="ingestion"),
    }


sqlalchemy_plugin = create_sqlalchemy_plugin()
saq_plugin = create_saq_plugin()
granian_plugin = GranianPlugin()
htmx_plugin = HTMXPlugin()
