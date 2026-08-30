from datetime import date, datetime, timedelta

from app.extensions import db


class PantryItem(db.Model):
    __tablename__ = "pantry_items"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    normalized_name = db.Column(db.String(120), nullable=False, index=True)
    quantity = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(20), nullable=False)
    category = db.Column(db.String(50), nullable=False, default="other", index=True)
    purchase_date = db.Column(db.Date, nullable=True)
    expiry_date = db.Column(db.Date, nullable=True, index=True)
    low_stock_threshold = db.Column(db.Float, nullable=False, default=0)
    storage_location = db.Column(db.String(50), nullable=True)
    status = db.Column(db.String(16), nullable=False, default="available", index=True)
    discard_count = db.Column(db.Integer, nullable=False, default=0)
    version = db.Column(db.Integer, nullable=False, default=1)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.CheckConstraint("quantity >= 0", name="ck_pantry_quantity"),
        db.CheckConstraint("low_stock_threshold >= 0", name="ck_pantry_threshold"),
        db.CheckConstraint("status IN ('available','consumed','discarded')", name="ck_pantry_status"),
        db.Index("ix_pantry_user_status_expiry", "user_id", "status", "expiry_date"),
    )

    def display_status(self, today=None):
        today = today or date.today()
        if self.status in {"consumed", "discarded"}:
            return self.status
        if self.expiry_date and self.expiry_date < today:
            return "expired"
        if self.expiry_date and self.expiry_date <= today + timedelta(days=3):
            return "expiring soon"
        if self.quantity <= self.low_stock_threshold:
            return "low stock"
        return "available"


class GroceryItem(db.Model):
    __tablename__ = "grocery_items"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    plan_id = db.Column(db.Integer, db.ForeignKey("weekly_meal_plans.id"), nullable=True, index=True)
    name = db.Column(db.String(120), nullable=False)
    normalized_name = db.Column(db.String(120), nullable=False, index=True)
    quantity = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(20), nullable=False)
    category = db.Column(db.String(50), nullable=False, default="other", index=True)
    source = db.Column(db.String(16), nullable=False, default="manual")
    status = db.Column(db.String(16), nullable=False, default="needed", index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.CheckConstraint("quantity > 0", name="ck_grocery_quantity"),
        db.CheckConstraint("source IN ('manual','plan')", name="ck_grocery_source"),
        db.CheckConstraint("status IN ('needed','checked','purchased','transferred')", name="ck_grocery_status"),
        db.Index("ix_grocery_user_status", "user_id", "status"),
    )
