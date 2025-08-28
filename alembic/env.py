import os
import sys
from pathlib import Path
from logging.config import fileConfig
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlalchemy.exc import OperationalError

# Ensure project root on sys.path
THIS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = THIS_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

# Load app settings & models
from app.Core.config import get_settings
from app.DB.base import Base  
# Ensure all models are imported so Base.metadata is populated
import app.DB.models  # noqa: F401

settings = get_settings()

def _ensure_driver_and_ssl(url: str) -> str:
    """Force psycopg2 driver and sslmode=require for Supabase-style URLs."""
    if not url:
        return ""
    if url.startswith("postgresql://") and "+psycopg2://" not in url:
        url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
    parsed = urlparse(url)
    q = dict(parse_qsl(parsed.query, keep_blank_values=True))
    if "sslmode" not in q:
        q["sslmode"] = "require"
    return urlunparse(parsed._replace(query=urlencode(q)))


def _hostname(url: str) -> str:
    try:
        return urlparse(url).hostname or ""
    except Exception:
        return ""


def _swap_host(url: str, new_host: str) -> str:
    p = urlparse(url)
    # Preserve creds & port
    netloc = ""
    if p.username:
        netloc += p.username
        if p.password:
            netloc += f":{p.password}"
        netloc += "@"
    if p.port:
        netloc += f"{new_host}:{p.port}"
    else:
        netloc += new_host
    return urlunparse(p._replace(netloc=netloc))


def _sanitize(url: str) -> str:
    if not url:
        return url
    p = urlparse(url)
    # hide password
    if p.password:
        auth = p.username + ":***@" if p.username else "***@"
    elif p.username:
        auth = p.username + "@"
    else:
        auth = ""
    hostport = p.hostname or ""
    if p.port:
        hostport += f":{p.port}"
    netloc = auth + hostport
    return urlunparse(p._replace(netloc=netloc))


raw_url = settings.get_database_url()
MIGRATIONS_URL = _ensure_driver_and_ssl(raw_url)
if not MIGRATIONS_URL:
    raise RuntimeError("No DATABASE_URL configured.")

# Alembic Config
config = context.config
# Inject URL dynamically (avoid secrets in ini)
config.set_main_option("sqlalchemy.url", MIGRATIONS_URL)

# Logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Model metadata for autogenerate
target_metadata = getattr(Base, "metadata", None)

EXCLUDE_TABLES = {"auth.users"}  # Exclude external tables managed by Supabase

def include_object(object, name, type_, reflected, compare_to):
    # Skip tables explicitly excluded
    if type_ == "table" and name in EXCLUDE_TABLES:
        return False
    # Skip foreign key constraints that reference excluded tables
    if type_ == "foreign_key_constraint" and hasattr(object, "referred_table"):
        if hasattr(object.referred_table, "name") and object.referred_table.name in EXCLUDE_TABLES:
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
        include_schemas=False,         # Don't include any schemas other than public
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    """Run migrations in 'online' mode' with runtime fallback.

    Tries MIGRATIONS_URL first; on OperationalError falls back to RUNTIME_URL.
    """
    section_template = config.get_section(config.config_ini_section, {}).copy()

    def _attempt(url: str, label: str):
        section = section_template.copy()
        section["sqlalchemy.url"] = url
        engine = engine_from_config(section, prefix="sqlalchemy.", poolclass=pool.NullPool)
        with engine.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                render_as_batch=True,
                compare_type=True,
                compare_server_default=True,
                include_object=include_object,
                include_schemas=False,         # Don't include any schemas other than public
            )
            with context.begin_transaction():
                context.run_migrations()

    last_error = None
    tried = set()
    for url, label in ((MIGRATIONS_URL, "primary"),):
        if not url or url in tried:
            continue
        tried.add(url)
        try:
            _attempt(url, label)
            return
        except OperationalError as oe:
            last_error = oe
            print(f"[alembic.env] Connection failed for {label} URL: {oe}")
            continue
    if last_error:
        raise last_error

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()