import os

import click
from dotenv import load_dotenv
from flask import Flask, render_template
from sqlalchemy import inspect, text

from config import Config
from extensions import db
from routes.meal_routes import meal_bp
from routes.nutrition_routes import nutrition_bp
from routes.vendor_routes import vendor_bp
from seed import seed_vendor_demo_data


def _ensure_meal_log_nutrition_columns() -> None:
    inspector = inspect(db.engine)
    if "meal_logs" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("meal_logs")}
    required_columns = {
        "calories": "FLOAT",
        "protein": "FLOAT",
        "carbohydrates": "FLOAT",
        "fats": "FLOAT",
    }

    with db.engine.begin() as connection:
        for column_name, column_type in required_columns.items():
            if column_name not in existing_columns:
                connection.execute(
                    text(f"ALTER TABLE meal_logs ADD COLUMN {column_name} {column_type}")
                )


def create_app():
    load_dotenv()

    app = Flask(__name__)
    app.config.from_object(Config)

    app.config["CLOUDINARY_CLOUD_NAME"] = os.getenv("CLOUDINARY_CLOUD_NAME")
    app.config["CLOUDINARY_API_KEY"] = os.getenv("CLOUDINARY_API_KEY")
    app.config["CLOUDINARY_API_SECRET"] = os.getenv("CLOUDINARY_API_SECRET")
    app.config["NUTRITION_API_KEY"] = os.getenv("NUTRITION_API_KEY")

    db.init_app(app)
    app.register_blueprint(meal_bp)
    app.register_blueprint(vendor_bp)
    app.register_blueprint(nutrition_bp)

    @app.cli.command("seed-vendors")
    def seed_vendors_command():
        """Seed demo vendors and menu items."""
        total_vendors, total_items = seed_vendor_demo_data()
        click.echo(
            f"Seeding complete. Active vendors: {total_vendors}, available menu items: {total_items}."
        )

    @app.errorhandler(404)
    def not_found(_error):
        return render_template("404.html"), 404

    with app.app_context():
        db.create_all()
        _ensure_meal_log_nutrition_columns()

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
