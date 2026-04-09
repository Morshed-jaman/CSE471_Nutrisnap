import os

import click
from dotenv import load_dotenv
from flask import Flask, render_template

from config import Config
from extensions import db
from routes.meal_routes import meal_bp
from routes.vendor_routes import vendor_bp
from seed import seed_vendor_demo_data


def create_app():
    load_dotenv()

    app = Flask(__name__)
    app.config.from_object(Config)

    app.config["CLOUDINARY_CLOUD_NAME"] = os.getenv("CLOUDINARY_CLOUD_NAME")
    app.config["CLOUDINARY_API_KEY"] = os.getenv("CLOUDINARY_API_KEY")
    app.config["CLOUDINARY_API_SECRET"] = os.getenv("CLOUDINARY_API_SECRET")

    db.init_app(app)
    app.register_blueprint(meal_bp)
    app.register_blueprint(vendor_bp)

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

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
