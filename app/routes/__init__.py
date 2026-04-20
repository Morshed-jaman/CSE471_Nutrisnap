from flask import Flask


def register_blueprints(app: Flask) -> None:
    from app.routes.advice_routes import advice_bp
    from app.routes.admin_routes import admin_bp
    from app.routes.auth_routes import auth_bp
    from app.routes.favorites_routes import favorites_bp
    from app.routes.meal_routes import meal_bp
    from app.routes.nutrition_routes import nutrition_bp
    from app.routes.vendor_routes import vendor_bp

    app.register_blueprint(meal_bp)
    app.register_blueprint(vendor_bp)
    app.register_blueprint(favorites_bp)
    app.register_blueprint(nutrition_bp)
    app.register_blueprint(advice_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
