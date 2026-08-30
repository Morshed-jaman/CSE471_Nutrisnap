from pathlib import Path
import shutil

from alembic.runtime.migration import MigrationContext
from flask_migrate import upgrade
from sqlalchemy import create_engine, inspect, text

from app import create_app
from app.config import Config


REQUIRED = {
    "users", "vendors", "vendor_profiles", "menu_items", "meal_logs", "reviews",
    "favorite_vendors", "favorite_menu_items", "favorite_meals", "subscription_plans",
    "subscriptions", "cart_items", "orders", "order_items", "payment_transactions",
    "alembic_version",
    "nutrition_preferences", "weekly_meal_plans", "meal_plan_entries",
    "recipe_ingredients", "pantry_items", "grocery_items",
}


def _migration_app(path: Path):
    class MigrationConfig(Config):
        SECRET_KEY = "migration-test-only"
        TESTING = True
        AUTO_CREATE_DB = False
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{path.as_posix()}"
        SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    return create_app(MigrationConfig)


def test_fresh_database_upgrade_and_repeated_upgrade(tmp_path):
    path = tmp_path / "fresh.db"
    app = _migration_app(path)
    with app.app_context():
        upgrade(directory="migrations")
        upgrade(directory="migrations")
        assert REQUIRED <= set(inspect(app.extensions["sqlalchemy"].engine).get_table_names())
        rows = app.extensions["sqlalchemy"].session.execute(
            text("SELECT code FROM subscription_plans ORDER BY code")
        ).scalars().all()
        assert rows == ["annual", "monthly", "quarterly"]


def test_legacy_database_is_upgraded_without_losing_rows(tmp_path):
    path = tmp_path / "legacy.db"
    engine = create_engine(f"sqlite:///{path.as_posix()}")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY, name VARCHAR(120) NOT NULL, email VARCHAR(120) NOT NULL, phone VARCHAR(40) NOT NULL, password_hash VARCHAR(255) NOT NULL, role VARCHAR(20) NOT NULL, is_active BOOLEAN NOT NULL, is_subscribed BOOLEAN NOT NULL, vendor_status VARCHAR(20), expert_status VARCHAR(20), expert_credentials TEXT, expert_review_note TEXT, created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL)"))
        connection.execute(text("INSERT INTO users VALUES (1, 'Legacy', 'legacy@example.test', '0123456789', 'hash', 'user', 1, 0, NULL, NULL, NULL, NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"))
    app = _migration_app(path)
    with app.app_context():
        upgrade(directory="migrations")
        assert app.extensions["sqlalchemy"].session.execute(text("SELECT name FROM users WHERE id=1")).scalar_one() == "Legacy"
        assert REQUIRED <= set(inspect(app.extensions["sqlalchemy"].engine).get_table_names())


def test_preflight_reports_only_safe_schema_details(tmp_path):
    app = _migration_app(tmp_path / "preflight.db")
    with app.app_context():
        upgrade(directory="migrations")
    result = app.test_cli_runner().invoke(args=["db-preflight"])
    assert result.exit_code == 0
    assert "Database dialect: sqlite" in result.output
    assert "Missing required tables: none" in result.output
    assert "sqlite:///" not in result.output


def test_already_current_local_sqlite_copy_stays_at_head(tmp_path):
    source = Path(__file__).parents[1] / "meal_logs.db"
    copied = tmp_path / "local-copy.db"
    shutil.copy2(source, copied)
    app = _migration_app(copied)
    with app.app_context():
        engine = app.extensions["sqlalchemy"].engine
        with engine.connect() as connection:
            before = MigrationContext.configure(connection).get_current_revision()
        upgrade(directory="migrations")
        with engine.connect() as connection:
            after = MigrationContext.configure(connection).get_current_revision()
        assert before == "13c04f232d70"
        assert after == "8f2c1a7d4b90"


def test_planner_revision_upgrade_downgrade_upgrade(tmp_path):
    from flask_migrate import downgrade
    path = tmp_path / "roundtrip.db"
    app = _migration_app(path)
    with app.app_context():
        upgrade(directory="migrations")
        assert "pantry_items" in inspect(app.extensions["sqlalchemy"].engine).get_table_names()
        downgrade(revision="13c04f232d70", directory="migrations")
        assert "pantry_items" not in inspect(app.extensions["sqlalchemy"].engine).get_table_names()
        upgrade(directory="migrations")
        assert REQUIRED <= set(inspect(app.extensions["sqlalchemy"].engine).get_table_names())
