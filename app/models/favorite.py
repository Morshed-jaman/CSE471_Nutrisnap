from datetime import datetime

from app.extensions import db


class FavoriteVendor(db.Model):
    __tablename__ = "favorite_vendors"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    vendor_id = db.Column(db.Integer, db.ForeignKey("vendors.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    user = db.relationship("User", back_populates="favorite_vendors")
    vendor = db.relationship("Vendor", back_populates="favorite_entries", lazy="joined")

    __table_args__ = (
        db.UniqueConstraint("user_id", "vendor_id", name="uq_favorite_vendor_user_target"),
    )


class FavoriteMenuItem(db.Model):
    __tablename__ = "favorite_menu_items"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    menu_item_id = db.Column(db.Integer, db.ForeignKey("menu_items.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    user = db.relationship("User", back_populates="favorite_menu_items")
    menu_item = db.relationship("MenuItem", back_populates="favorite_entries", lazy="joined")

    __table_args__ = (
        db.UniqueConstraint("user_id", "menu_item_id", name="uq_favorite_menu_user_target"),
    )


class FavoriteMeal(db.Model):
    __tablename__ = "favorite_meals"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    meal_log_id = db.Column(db.Integer, db.ForeignKey("meal_logs.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    user = db.relationship("User", back_populates="favorite_meals")
    meal_log = db.relationship("MealLog", back_populates="favorite_entries", lazy="joined")

    __table_args__ = (
        db.UniqueConstraint("user_id", "meal_log_id", name="uq_favorite_meal_user_target"),
    )
