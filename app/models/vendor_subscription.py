from datetime import datetime

from app.extensions import db


class VendorSubscription(db.Model):
    __tablename__ = "vendor_subscriptions"
    __table_args__ = (
        db.UniqueConstraint("user_id", "vendor_id", name="uq_vendor_subscription_user_vendor"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    vendor_id = db.Column(db.Integer, db.ForeignKey("vendors.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    user = db.relationship("User", back_populates="vendor_subscriptions")
    vendor = db.relationship("Vendor", back_populates="subscriptions")

    def __repr__(self) -> str:
        return f"<VendorSubscription user_id={self.user_id} vendor_id={self.vendor_id}>"
