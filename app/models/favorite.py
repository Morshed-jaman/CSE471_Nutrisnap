from datetime import datetime

from app.extensions import db


class FavoriteVendor(db.Model):
    __tablename__ = "favorite_vendors"

    id = db.Column(db.Integer, primary_key=True)
    vendor_id = db.Column(db.Integer, db.ForeignKey("vendors.id"), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    vendor = db.relationship("Vendor", back_populates="favorite_entry", lazy="joined")


class FavoriteMenuItem(db.Model):
    __tablename__ = "favorite_menu_items"

    id = db.Column(db.Integer, primary_key=True)
    menu_item_id = db.Column(
        db.Integer, db.ForeignKey("menu_items.id"), nullable=False, unique=True
    )
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    menu_item = db.relationship("MenuItem", back_populates="favorite_entry", lazy="joined")


class FavoriteMeal(db.Model):
    __tablename__ = "favorite_meals"

    id = db.Column(db.Integer, primary_key=True)
    meal_log_id = db.Column(db.Integer, db.ForeignKey("meal_logs.id"), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    meal_log = db.relationship("MealLog", back_populates="favorite_entry", lazy="joined")