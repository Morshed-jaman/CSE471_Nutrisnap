import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool


BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=BASE_DIR / ".env")


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _as_float(value: str | None, default: float) -> float:
    try:
        return float(value) if value not in (None, "") else default
    except (TypeError, ValueError):
        return default


def _as_int(value: str | None, default: int) -> int:
    try:
        return int(value) if value not in (None, "") else default
    except (TypeError, ValueError):
        return default


def _normalize_database_url(database_url: str | None) -> str | None:
    if not database_url:
        return None

    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)

    if database_url.startswith("sqlite:///"):
        raw_path = database_url.replace("sqlite:///", "", 1)
        has_drive = len(raw_path) >= 2 and raw_path[1] == ":"

        if raw_path != ":memory:" and not Path(raw_path).is_absolute() and not has_drive:
            absolute_sqlite_path = (BASE_DIR / raw_path).as_posix()
            return f"sqlite:///{absolute_sqlite_path}"

    return database_url


def _validate_production_database(database_url: str | None, *, is_vercel: bool) -> None:
    """Validate only deployment-safe URL properties without exposing URL contents."""
    if not is_vercel:
        return
    if not database_url:
        raise RuntimeError("DATABASE_URL must be configured for Vercel.")

    try:
        url = make_url(database_url)
        backend = url.get_backend_name()
        port = url.port
    except (TypeError, ValueError):
        raise RuntimeError("DATABASE_URL is not a valid database URL for Vercel.") from None

    if backend != "postgresql":
        raise RuntimeError("DATABASE_URL must use PostgreSQL on Vercel; SQLite is not allowed.")
    if port != 6543:
        raise RuntimeError("DATABASE_URL must use the Supabase transaction pooler on port 6543.")


def _database_engine_options(database_url: str | None) -> dict:
    options: dict = {"pool_pre_ping": True}
    if database_url and database_url.startswith(("postgresql://", "postgresql+")):
        options.update(
            poolclass=NullPool,
            connect_args={"sslmode": "require", "connect_timeout": 10},
        )
    return options


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY")

    database_url = _normalize_database_url(os.getenv("DATABASE_URL"))

    if database_url:
        SQLALCHEMY_DATABASE_URI = database_url
    else:
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{(BASE_DIR / 'meal_logs.db').as_posix()}"

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = _database_engine_options(database_url)
    AUTO_CREATE_DB = _as_bool(os.getenv("AUTO_CREATE_DB"), default=False)

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _as_bool(os.getenv("SESSION_COOKIE_SECURE"), default=bool(os.getenv("VERCEL")))
    PERMANENT_SESSION_LIFETIME = timedelta(hours=12)
    PREFERRED_URL_SCHEME = "https"

    MAX_CONTENT_LENGTH = 8 * 1024 * 1024  # 8 MB
    ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}

    MAIL_SERVER = os.getenv("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.getenv("MAIL_PORT", "587"))
    MAIL_USERNAME = os.getenv("MAIL_USERNAME")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
    MAIL_USE_TLS = _as_bool(os.getenv("MAIL_USE_TLS"), default=True)
    MAIL_DEFAULT_SENDER = os.getenv("MAIL_DEFAULT_SENDER") or os.getenv("MAIL_USERNAME")

    WATER_TRACKER_LATITUDE = _as_float(os.getenv("WATER_TRACKER_LATITUDE"), 23.8103)
    WATER_TRACKER_LONGITUDE = _as_float(os.getenv("WATER_TRACKER_LONGITUDE"), 90.4125)
    WATER_TRACKER_FALLBACK_GOAL_ML = _as_int(os.getenv("WATER_TRACKER_FALLBACK_GOAL_ML"), 2500)

    PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL")
    SSLCOMMERZ_STORE_ID = os.getenv("SSLCOMMERZ_STORE_ID")
    SSLCOMMERZ_STORE_PASSWORD = os.getenv("SSLCOMMERZ_STORE_PASSWORD")
    SSLCOMMERZ_SANDBOX = _as_bool(os.getenv("SSLCOMMERZ_SANDBOX"), default=True)
    PAYMENT_HTTP_TIMEOUT_SECONDS = _as_int(os.getenv("PAYMENT_HTTP_TIMEOUT_SECONDS"), 15)
    ORDER_DELIVERY_FEE_BDT = _as_float(os.getenv("ORDER_DELIVERY_FEE_BDT"), 60.0)
