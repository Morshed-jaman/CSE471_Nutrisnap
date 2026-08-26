import os
import re
import hashlib

import click
from dotenv import load_dotenv
from flask import Flask, render_template, request
from flask_login import AnonymousUserMixin
from sqlalchemy import inspect, text
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from werkzeug.middleware.proxy_fix import ProxyFix

from app.config import Config, _validate_production_database
from app.extensions import csrf, db, login_manager, migrate
from app.models import SubscriptionPlan, User
from app.routes import register_blueprints
from app.seed import seed_vendor_demo_data


@login_manager.user_loader
def load_user(user_id: str):
    if not user_id or not user_id.isdigit():
        return None
    return db.session.get(User, int(user_id))


def _add_column_if_missing(table_name: str, column_name: str, column_type: str) -> None:
    inspector = inspect(db.engine)
    if table_name not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns(table_name)}
    if column_name in existing_columns:
        return

    with db.engine.begin() as connection:
        connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"))


def _ensure_schema_compatibility() -> None:
    _add_column_if_missing("meal_logs", "calories", "FLOAT")
    _add_column_if_missing("meal_logs", "protein", "FLOAT")
    _add_column_if_missing("meal_logs", "carbohydrates", "FLOAT")
    _add_column_if_missing("meal_logs", "fats", "FLOAT")
    _add_column_if_missing("meal_logs", "user_id", "INTEGER")

    _add_column_if_missing("users", "is_subscribed", "BOOLEAN DEFAULT 0")
    _add_column_if_missing("users", "expert_status", "VARCHAR(20)")
    _add_column_if_missing("users", "expert_credentials", "TEXT")
    _add_column_if_missing("users", "expert_review_note", "TEXT")

    _add_column_if_missing("vendors", "owner_user_id", "INTEGER")
    _add_column_if_missing("menu_items", "cloudinary_public_id", "VARCHAR(255)")
    _add_column_if_missing("vendor_profiles", "cover_image_url", "VARCHAR(500)")
    _add_column_if_missing("vendor_profiles", "cover_cloudinary_public_id", "VARCHAR(255)")

    _add_column_if_missing("advice_questions", "expert_id", "INTEGER")
    _add_column_if_missing("advice_questions", "response_text", "TEXT")
    _add_column_if_missing("advice_questions", "status", "VARCHAR(20)")
    _add_column_if_missing("advice_questions", "answered_at", "DATETIME")

    _add_column_if_missing("water_intakes", "user_id", "INTEGER")
    _add_column_if_missing("water_intakes", "amount_ml", "INTEGER")
    _add_column_if_missing("water_intakes", "intake_date", "DATE")


def _ensure_subscription_plans() -> None:
    defaults = (
        (
            "monthly",
            "NutriSnap Plus Monthly",
            "Nutrition-expert advice, premium insights, and subscriber features for 30 days.",
            299,
            30,
        ),
        (
            "quarterly",
            "NutriSnap Plus Quarterly",
            "Three months of premium nutrition guidance at a lower monthly cost.",
            799,
            90,
        ),
        (
            "annual",
            "NutriSnap Plus Annual",
            "One year of premium nutrition guidance and expert advice.",
            2499,
            365,
        ),
    )
    changed = False
    for code, name, description, price, duration_days in defaults:
        plan = SubscriptionPlan.query.filter_by(code=code).first()
        if plan:
            continue
        db.session.add(
            SubscriptionPlan(
                code=code,
                name=name,
                description=description,
                price=price,
                duration_days=duration_days,
                is_active=True,
            )
        )
        changed = True
    if changed:
        db.session.commit()


def _clean_optional_env(key: str, default: str | None = None) -> str | None:
    value = os.getenv(key, default)
    if value is None:
        return None

    cleaned = str(value).strip()
    if not cleaned:
        return None

    if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in {'"', "'"}:
        cleaned = cleaned[1:-1].strip()

    return cleaned or None


def create_app(config_class: type[Config] = Config) -> Flask:
    # Process-level values (including a temporary migration DATABASE_URL) must win.
    load_dotenv(override=False)

    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)
    _validate_production_database(
        app.config.get("SQLALCHEMY_DATABASE_URI"),
        is_vercel=bool(os.getenv("VERCEL")),
    )
    if not app.config.get("SECRET_KEY"):
        raise RuntimeError("SECRET_KEY must be configured before NutriSnap can start.")
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    app.config["CLOUDINARY_CLOUD_NAME"] = _clean_optional_env("CLOUDINARY_CLOUD_NAME")
    app.config["CLOUDINARY_API_KEY"] = _clean_optional_env("CLOUDINARY_API_KEY")
    app.config["CLOUDINARY_API_SECRET"] = _clean_optional_env("CLOUDINARY_API_SECRET")
    app.config["NUTRITION_API_KEY"] = _clean_optional_env("NUTRITION_API_KEY")
    app.config["OPENAI_API_KEY"] = _clean_optional_env("OPENAI_API_KEY")
    app.config["OPENAI_MODEL"] = _clean_optional_env("OPENAI_MODEL", "gpt-4o-mini") or "gpt-4o-mini"
    app.config["OPENAI_BASE_URL"] = _clean_optional_env(
        "OPENAI_BASE_URL", "https://api.openai.com/v1/chat/completions"
    )
    app.config["OPENROUTER_API_KEY"] = _clean_optional_env("OPENROUTER_API_KEY")
    app.config["OPENROUTER_SITE_URL"] = _clean_optional_env("OPENROUTER_SITE_URL")
    app.config["OPENROUTER_SITE_NAME"] = _clean_optional_env("OPENROUTER_SITE_NAME")

    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please log in to continue."
    login_manager.login_message_category = "warning"

    register_blueprints(app)

    @app.cli.command("db-preflight")
    def database_preflight_command():
        """Read-only migration and required-table check; never prints the URL."""
        from alembic.runtime.migration import MigrationContext
        from alembic.script import ScriptDirectory

        required = {
            "users", "vendors", "vendor_profiles", "menu_items", "meal_logs", "reviews",
            "favorite_vendors", "favorite_menu_items", "favorite_meals",
            "subscription_plans", "subscriptions", "cart_items", "orders", "order_items",
            "payment_transactions", "alembic_version",
        }
        inspector = inspect(db.engine)
        with db.engine.connect() as connection:
            current_revision = MigrationContext.configure(connection).get_current_revision()
        expected = ScriptDirectory.from_config(migrate.get_config()).get_current_head()
        missing = sorted(required - set(inspector.get_table_names()))
        click.echo(f"Database dialect: {db.engine.dialect.name}")
        hostname = db.engine.url.host
        fingerprint = hashlib.sha256(hostname.encode()).hexdigest()[:12] if hostname else "local"
        click.echo(f"Database host fingerprint: {fingerprint}")
        click.echo(f"Current migration revision: {current_revision or 'none'}")
        click.echo(f"Expected migration head: {expected}")
        click.echo(f"Missing required tables: {', '.join(missing) if missing else 'none'}")
        if current_revision != expected or missing:
            raise click.ClickException("Database schema is not ready.")

    @app.cli.command("create-admin")
    @click.option("--email", prompt=True)
    @click.option("--name", prompt=True)
    @click.option("--phone", prompt=True)
    def create_admin_command(email: str, name: str, phone: str):
        """Create one administrator without environment credential fallbacks."""
        email, name, phone = email.strip().lower(), name.strip(), phone.strip()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
            raise click.ClickException("A valid email address is required.")
        if len(name) < 2 or not re.fullmatch(r"[0-9+() -]{7,40}", phone):
            raise click.ClickException("A valid name and phone number are required.")
        existing = User.query.filter_by(email=email).first()
        if existing:
            if existing.role == "admin":
                click.echo("An administrator with that email already exists; no changes made.")
                return
            raise click.ClickException("That email belongs to a non-administrator; no changes made.")
        password = click.prompt("Password", hide_input=True, confirmation_prompt=True)
        if (len(password) < 12 or not re.search(r"[A-Z]", password)
                or not re.search(r"[a-z]", password) or not re.search(r"\d", password)
                or not re.search(r"[^A-Za-z0-9]", password)):
            raise click.ClickException(
                "Password must be at least 12 characters and include upper, lower, number, and symbol."
            )
        admin = User(name=name, email=email, phone=phone, role="admin", is_active=True)
        admin.set_password(password)
        db.session.add(admin)
        try:
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
            raise click.ClickException("Administrator creation failed; no changes were saved.")
        click.echo("Administrator created successfully.")

    @app.cli.command("seed-vendors")
    def seed_vendors_command():
        """Seed demo vendors and menu items."""
        total_vendors, total_items = seed_vendor_demo_data()
        click.echo(
            f"Seeding complete. Active vendors: {total_vendors}, available menu items: {total_items}."
        )

    @app.errorhandler(404)
    def not_found(_error):
        return render_template("errors/404.html"), 404

    @app.errorhandler(OperationalError)
    def database_unavailable(error):
        db.session.rollback()
        original = getattr(error, "orig", None)
        error_code = getattr(original, "pgcode", None) or getattr(original, "sqlstate", None)
        if not isinstance(error_code, str) or not re.fullmatch(r"[A-Z0-9]{5}", error_code):
            error_code = "unavailable"
        app.logger.error(
            "Database request failure route=%s category=OperationalError pgcode=%s",
            request.path,
            error_code,
        )
        response = app.make_response(
            (render_template("errors/500.html", current_user=AnonymousUserMixin()), 503)
        )
        response.headers["Retry-After"] = "30"
        return response

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        category = type(getattr(error, "original_exception", None) or error).__name__
        app.logger.error("Unexpected request failure route=%s category=%s", request.path, category)
        return render_template("errors/500.html"), 500

    with app.app_context():
        if app.config.get("AUTO_CREATE_DB", False):
            db.create_all()
            _ensure_schema_compatibility()
            _ensure_subscription_plans()

    return app
