import os
import sys
from pathlib import Path
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlalchemy.exc import OperationalError
import socket

# Ensure project root on sys.path
THIS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = THIS_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

# Load app settings & models
from app.core.config import get_settings
import os
from app.db.models import Base  # ensure this imports your Declarative Base

settings = get_settings()

# Prefer dedicated migrations URL (5432) falling back to runtime pooled URL.
force_pooled = os.getenv("FORCE_MIGRATIONS_POOLED", "false").lower() == "true"
MIGRATIONS_URL = settings.get_database_url(for_migrations=not force_pooled)
if not MIGRATIONS_URL:
    raise RuntimeError(
        "No database URL found. Provide DATABASE_URL and optionally DATABASE_URL_MIGRATIONS for Alembic."
    )

# Basic DNS sanity check; if direct host fails resolution but runtime resolves, fallback.
def _host_from_url(url: str) -> str:
    try:
        return url.split('@')[1].split('/')[0]
    except Exception:
        return ""

direct_host = _host_from_url(MIGRATIONS_URL)
if direct_host:
    try:
        socket.getaddrinfo(direct_host, None)
    except socket.gaierror:
        runtime_url = settings.get_database_url(for_migrations=False)
        runtime_host = _host_from_url(runtime_url)
        if runtime_host:
            try:
                socket.getaddrinfo(runtime_host, None)
                # replace host portion
                MIGRATIONS_URL = runtime_url
                print(f"[alembic.env] DNS failed for direct host '{direct_host}', using runtime host '{runtime_host}' for migrations.")
            except socket.gaierror:
                pass  # both failed; let later connect raise

# Alembic Config
config = context.config
# Override any value in alembic.ini
config.set_main_option("sqlalchemy.url", MIGRATIONS_URL)

# Logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Model metadata for autogenerate
target_metadata = getattr(Base, "metadata", None)

EXCLUDE_TABLES = set()  # all tables now managed by SQLAlchemy models

def include_object(object, name, type_, reflected, compare_to):
    # Skip tables explicitly excluded
    if type_ == "table" and name in EXCLUDE_TABLES:
        return False
    return True

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode'."""
    context.configure(
        url=MIGRATIONS_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        render_as_batch=True,          # safer for some DDL ops
        dialect_opts={"paramstyle": "named"},
        compare_type=True,             # detect column type changes
        compare_server_default=True,   # detect server default changes
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    """Run migrations in 'online' mode' with fallback to runtime URL if direct fails."""
    section = config.get_section(config.config_ini_section, {}).copy()
    section["sqlalchemy.url"] = MIGRATIONS_URL

    def _attempt(url: str):
        section["sqlalchemy.url"] = url
        return engine_from_config(section, prefix="sqlalchemy.", poolclass=pool.NullPool)

    attempted_urls = []
    runtime_url = settings.get_database_url(for_migrations=False)
    last_error = None
    for url, label in ((MIGRATIONS_URL, "migrations"), (runtime_url, "runtime fallback")):
        if not url or url in attempted_urls:
            continue
        try:
            connectable = _attempt(url)
            with connectable.connect() as connection:
                if url != MIGRATIONS_URL:
                    print(f"[alembic.env] Using {label} URL for migrations: {url}")
                context.configure(
                    connection=connection,
                    target_metadata=target_metadata,
                    render_as_batch=True,
                    compare_type=True,
                    compare_server_default=True,
                    include_object=include_object,
                )
                with context.begin_transaction():
                    context.run_migrations()
            return
        except OperationalError as oe:
            last_error = oe
            print(f"[alembic.env] Connection failed for {label} URL: {oe}")
            attempted_urls.append(url)
            continue
    # If we exit loop without returning, re-raise last error
    if last_error:
        raise last_error

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()