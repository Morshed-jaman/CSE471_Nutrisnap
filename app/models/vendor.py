from datetime import datetime

from app.extensions import db


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
    favorite_entry = db.relationship(
        "FavoriteVendor", back_populates="vendor", uselist=False, cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Vendor id={self.id} name={self.name} category={self.category}>"
