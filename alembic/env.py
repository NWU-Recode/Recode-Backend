import os
import sys
import socket
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
from app.core.config import get_settings
from app.db.base import Base  # dynamic discovery inside base imports feature models

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


# Build URLs
force_pooled = os.getenv("FORCE_MIGRATIONS_POOLED", "false").lower() == "true"
raw_migrations_url = settings.get_database_url(for_migrations=not force_pooled)
raw_runtime_url = settings.get_database_url(for_migrations=False)

MIGRATIONS_URL = _ensure_driver_and_ssl(raw_migrations_url)
RUNTIME_URL = _ensure_driver_and_ssl(raw_runtime_url)

if not MIGRATIONS_URL:
    raise RuntimeError(
        "No database URL found for migrations. Set DATABASE_URL and optionally DATABASE_URL_MIGRATIONS."
    )

# DNS check on migrations host; if fails but runtime resolves, swap host (keeping port/creds)
direct_host = _hostname(MIGRATIONS_URL)
if direct_host:
    try:
        socket.getaddrinfo(direct_host, None)
    except socket.gaierror:
        runtime_host = _hostname(RUNTIME_URL)
        if runtime_host:
            try:
                socket.getaddrinfo(runtime_host, None)
                MIGRATIONS_URL = _swap_host(MIGRATIONS_URL, runtime_host)
                print(f"[alembic.env] DNS failed for '{direct_host}', using runtime host '{runtime_host}' for migrations.")
            except socket.gaierror:
                # both failed; allow later connection attempt to raise
                pass

# Alembic Config
config = context.config
# Inject URL dynamically (avoid secrets in ini)
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
            )
            with context.begin_transaction():
                context.run_migrations()

    last_error = None
    tried = set()
    for url, label in ((MIGRATIONS_URL, "migrations"), (RUNTIME_URL, "runtime fallback")):
        if not url or url in tried:
            continue
        tried.add(url)
        try:
            if url is RUNTIME_URL:
                print(f"[alembic.env] Using runtime URL as fallback for migrations: {_sanitize(url)}")
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