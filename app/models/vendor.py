from datetime import datetime

from app.extensions import db


class Vendor(db.Model):
    __tablename__ = "vendors"

    id = db.Column(db.Integer, primary_key=True)
    owner_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
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

    owner_user = db.relationship("User", back_populates="owned_vendor")

    menu_items = db.relationship(
        "MenuItem", back_populates="vendor", lazy="select", cascade="all, delete-orphan"
    )
    reviews = db.relationship(
        "Review", back_populates="vendor", lazy="select", cascade="all, delete-orphan"
    )
    subscriptions = db.relationship(
        "VendorSubscription",
        back_populates="vendor",
        lazy="select",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"<Vendor id={self.id} name={self.name} category={self.category} "
            f"owner_user_id={self.owner_user_id}>"
        )
