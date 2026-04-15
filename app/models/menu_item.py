from datetime import datetime

from app.extensions import db


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
