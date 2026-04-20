from datetime import datetime

from app.extensions import db


class Review(db.Model):
    __tablename__ = "reviews"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    vendor_id = db.Column(db.Integer, db.ForeignKey("vendors.id"), nullable=True, index=True)
    menu_item_id = db.Column(db.Integer, db.ForeignKey("menu_items.id"), nullable=True, index=True)
    rating = db.Column(db.Integer, nullable=False)
    review_text = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    user = db.relationship("User", back_populates="reviews")
    vendor = db.relationship("Vendor", back_populates="reviews")
    menu_item = db.relationship("MenuItem", back_populates="reviews")

    __table_args__ = (
        db.CheckConstraint("rating >= 1 AND rating <= 5", name="ck_reviews_rating_range"),
        db.CheckConstraint(
            "(vendor_id IS NOT NULL AND menu_item_id IS NULL) OR "
            "(vendor_id IS NULL AND menu_item_id IS NOT NULL)",
            name="ck_reviews_single_target",
        ),
        db.UniqueConstraint("user_id", "vendor_id", name="uq_review_user_vendor"),
        db.UniqueConstraint("user_id", "menu_item_id", name="uq_review_user_menu_item"),
    )

    def __repr__(self) -> str:
        target = f"vendor_id={self.vendor_id}" if self.vendor_id else f"menu_item_id={self.menu_item_id}"
        return f"<Review id={self.id} user_id={self.user_id} {target} rating={self.rating}>"
