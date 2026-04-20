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


def _env_bool(key: str, default: str = "false") -> bool:
    return os.getenv(key, default).strip().lower() in {"1", "true", "yes", "on"}


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
    _add_column_if_missing("vendors", "owner_user_id", "INTEGER")
    _add_column_if_missing("menu_items", "cloudinary_public_id", "VARCHAR(255)")


def create_app(config_class: type[Config] = Config) -> Flask:
    load_dotenv()

    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)

    app.config["CLOUDINARY_CLOUD_NAME"] = os.getenv("CLOUDINARY_CLOUD_NAME")
    app.config["CLOUDINARY_API_KEY"] = os.getenv("CLOUDINARY_API_KEY")
    app.config["CLOUDINARY_API_SECRET"] = os.getenv("CLOUDINARY_API_SECRET")
    app.config["NUTRITION_API_KEY"] = os.getenv("NUTRITION_API_KEY")
    app.config["MAIL_SERVER"] = os.getenv("MAIL_SERVER")
    app.config["MAIL_PORT"] = os.getenv("MAIL_PORT", "587")
    app.config["MAIL_USERNAME"] = os.getenv("MAIL_USERNAME")
    app.config["MAIL_PASSWORD"] = os.getenv("MAIL_PASSWORD")
    app.config["MAIL_DEFAULT_SENDER"] = os.getenv("MAIL_DEFAULT_SENDER")
    app.config["MAIL_USE_TLS"] = _env_bool("MAIL_USE_TLS", "true")
    app.config["MAIL_USE_SSL"] = _env_bool("MAIL_USE_SSL")

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

    return app
