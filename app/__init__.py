import os

import click
from dotenv import load_dotenv
from flask import Flask, render_template
from sqlalchemy import inspect, text

from app.config import Config
from app.extensions import db, login_manager
from app.models import User
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


def _ensure_default_admin(app: Flask) -> None:
    admin_email = (app.config.get("DEFAULT_ADMIN_EMAIL") or "").strip().lower()
    admin_password = (app.config.get("DEFAULT_ADMIN_PASSWORD") or "").strip()
    admin_name = (app.config.get("DEFAULT_ADMIN_NAME") or "System Admin").strip()
    admin_phone = (app.config.get("DEFAULT_ADMIN_PHONE") or "0000000000").strip()

    if not admin_email or not admin_password:
        return

    existing_admin = User.query.filter_by(email=admin_email).first()
    if existing_admin:
        if existing_admin.role != "admin":
            existing_admin.role = "admin"
        if not existing_admin.password_hash:
            existing_admin.set_password(admin_password)
        db.session.commit()
        return

    admin = User(
        name=admin_name,
        email=admin_email,
        phone=admin_phone,
        role="admin",
        vendor_status=None,
        is_active=True,
    )
    admin.set_password(admin_password)
    db.session.add(admin)
    db.session.commit()


def create_app(config_class: type[Config] = Config) -> Flask:
    load_dotenv(override=True)

    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)

    app.config["CLOUDINARY_CLOUD_NAME"] = os.getenv("CLOUDINARY_CLOUD_NAME")
    app.config["CLOUDINARY_API_KEY"] = os.getenv("CLOUDINARY_API_KEY")
    app.config["CLOUDINARY_API_SECRET"] = os.getenv("CLOUDINARY_API_SECRET")
    app.config["NUTRITION_API_KEY"] = os.getenv("NUTRITION_API_KEY")
    app.config["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")
    app.config["OPENAI_MODEL"] = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    app.config["OPENAI_BASE_URL"] = os.getenv(
        "OPENAI_BASE_URL", "https://api.openai.com/v1/chat/completions"
    )
    app.config["OPENROUTER_API_KEY"] = os.getenv("OPENROUTER_API_KEY")
    app.config["OPENROUTER_SITE_URL"] = os.getenv("OPENROUTER_SITE_URL")
    app.config["OPENROUTER_SITE_NAME"] = os.getenv("OPENROUTER_SITE_NAME")

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please log in to continue."
    login_manager.login_message_category = "warning"

    register_blueprints(app)

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

    with app.app_context():
        db.create_all()
        _ensure_schema_compatibility()
        _ensure_default_admin(app)

    return app
