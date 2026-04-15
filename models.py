from datetime import datetime

from extensions import db


class MealLog(db.Model):
    __tablename__ = "meal_logs"

    id = db.Column(db.Integer, primary_key=True)
    image_url = db.Column(db.String(500), nullable=False)
    cloudinary_public_id = db.Column(db.String(255), nullable=True)
    meal_type = db.Column(db.String(20), nullable=False)
    meal_date = db.Column(db.Date, nullable=False)
    title = db.Column(db.String(150), nullable=True)
    note = db.Column(db.Text, nullable=True)
    calories = db.Column(db.Float, nullable=True)
    protein = db.Column(db.Float, nullable=True)
    carbohydrates = db.Column(db.Float, nullable=True)
    fats = db.Column(db.Float, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def __repr__(self) -> str:
        return (
            f"<MealLog id={self.id} meal_type={self.meal_type} "
            f"meal_date={self.meal_date.isoformat()}>"
        )


class Vendor(db.Model):
    __tablename__ = "vendors"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    category = db.Column(db.String(80), nullable=False)
    description = db.Column(db.Text, nullable=True)
    image_url = db.Column(db.String(500), nullable=True)
    contact_email = db.Column(db.String(120), nullable=True)
    phone = db.Column(db.String(40), nullable=True)
    address = db.Column(db.String(255), nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    menu_items = db.relationship(
        "MenuItem", back_populates="vendor", lazy="select", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Vendor id={self.id} name={self.name} category={self.category}>"


class MenuItem(db.Model):
    __tablename__ = "menu_items"

    id = db.Column(db.Integer, primary_key=True)
    vendor_id = db.Column(db.Integer, db.ForeignKey("vendors.id"), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=True)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    image_url = db.Column(db.String(500), nullable=True)
    calories = db.Column(db.Numeric(8, 2), nullable=True)
    protein = db.Column(db.Numeric(8, 2), nullable=True)
    carbohydrates = db.Column(db.Numeric(8, 2), nullable=True)
    fats = db.Column(db.Numeric(8, 2), nullable=True)
    is_available = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    vendor = db.relationship("Vendor", back_populates="menu_items")

    def __repr__(self) -> str:
        return (
            f"<MenuItem id={self.id} name={self.name} vendor_id={self.vendor_id} "
            f"price={self.price}>"
        )
