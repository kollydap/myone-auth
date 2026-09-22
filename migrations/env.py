import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from myone_auth.core.config import get_settings
from myone_auth.models import Base  # importing the package registers every model

config = context.config

if config.config_file_name is not None:
    # Keep existing loggers alive: this env.py can be imported inside the app's process.
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata

# One source of truth for the URL. Deliberately not written into the Alembic
# config object: configparser treats "%" specially and would mangle passwords.
DATABASE_URL = get_settings().database_url.get_secret_value()


def run_migrations_offline() -> None:
    """Emit SQL to stdout without connecting (`alembic upgrade head --sql`)."""
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    # NullPool: a migration is a one-shot process, so no pool is kept around
    # (and none of it counts against the app's pool budget).
    connectable = create_async_engine(DATABASE_URL, poolclass=NullPool)
    async with connectable.connect() as connection:
        # Alembic itself is synchronous, so hand it the connection through run_sync.
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
