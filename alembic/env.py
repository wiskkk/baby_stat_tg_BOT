from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context
from db.database import DB_URL  # Берем URL из database.py
from db.models import Base

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
fileConfig(context.config.config_file_name)

def get_url():
    return DB_URL.replace("+asyncpg", "")
# Используем наш URL БД вместо sqlalchemy.url из alembic.ini
config.set_main_option("sqlalchemy.url", DB_URL)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = Base.metadata


# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Run migrations in 'online' mode."""
    # Получаем конфигурацию Alembic
    alembic_config = context.config.get_section(
        context.config.config_ini_section)
    if alembic_config is None:
        raise RuntimeError(
            "Alembic configuration section is missing or invalid.")

    # Устанавливаем SQLAlchemy URL
    alembic_config["sqlalchemy.url"] = get_url()

    # Создаем движок SQLAlchemy
    connectable = engine_from_config(
        alembic_config,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection,
                          target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
