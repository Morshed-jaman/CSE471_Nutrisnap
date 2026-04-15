import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=BASE_DIR / ".env")


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
    SQLALCHEMY_DATABASE_URI = database_url or f"sqlite:///{(BASE_DIR / 'meal_logs.db').as_posix()}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    MAX_CONTENT_LENGTH = 8 * 1024 * 1024  # 8 MB
    ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}
