import os
from pathlib import Path

from dotenv import load_dotenv


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


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")

    database_url = _normalize_database_url(os.getenv("DATABASE_URL"))

    if database_url:
        SQLALCHEMY_DATABASE_URI = database_url
    else:
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{(BASE_DIR / 'meal_logs.db').as_posix()}"

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    MAX_CONTENT_LENGTH = 8 * 1024 * 1024  # 8 MB
    ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}

    DEFAULT_ADMIN_EMAIL = os.getenv("DEFAULT_ADMIN_EMAIL", "admin@nutrisnap.local")
    DEFAULT_ADMIN_PASSWORD = os.getenv("DEFAULT_ADMIN_PASSWORD", "admin12345")
    DEFAULT_ADMIN_NAME = os.getenv("DEFAULT_ADMIN_NAME", "NutriSnap Admin")
    DEFAULT_ADMIN_PHONE = os.getenv("DEFAULT_ADMIN_PHONE", "01000000000")

    MAIL_SERVER = os.getenv("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.getenv("MAIL_PORT", "587"))
    MAIL_USERNAME = os.getenv("MAIL_USERNAME")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
    MAIL_USE_TLS = _as_bool(os.getenv("MAIL_USE_TLS"), default=True)
    MAIL_DEFAULT_SENDER = os.getenv("MAIL_DEFAULT_SENDER") or os.getenv("MAIL_USERNAME")

    WATER_TRACKER_LATITUDE = _as_float(os.getenv("WATER_TRACKER_LATITUDE"), 23.8103)
    WATER_TRACKER_LONGITUDE = _as_float(os.getenv("WATER_TRACKER_LONGITUDE"), 90.4125)
    WATER_TRACKER_FALLBACK_GOAL_ML = _as_int(os.getenv("WATER_TRACKER_FALLBACK_GOAL_ML"), 2500)
