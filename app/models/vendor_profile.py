from datetime import datetime

from app.extensions import db
#feature 1 vendor profile 2 main


class VendorProfile(db.Model):
    __tablename__ = "vendor_profiles"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, unique=True)
    business_name = db.Column(db.String(150), nullable=False)
    business_category = db.Column(db.String(100), nullable=False)
    business_address = db.Column(db.String(255), nullable=False)
    business_description = db.Column(db.Text, nullable=True)
    cover_image_url = db.Column(db.String(500), nullable=True)
    cover_cloudinary_public_id = db.Column(db.String(255), nullable=True)
    verification_note = db.Column(db.Text, nullable=True)
    approval_status = db.Column(db.String(20), nullable=False, default="pending")
    reviewed_at = db.Column(db.DateTime, nullable=True)
    reviewed_by_admin_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    admin_review_note = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    user = db.relationship("User", back_populates="vendor_profile", foreign_keys=[user_id])
    reviewed_by_admin = db.relationship(
        "User",
        back_populates="reviewed_vendor_profiles",
        foreign_keys=[reviewed_by_admin_id],
    )

    def __repr__(self) -> str:
        return (
            f"<VendorProfile id={self.id} user_id={self.user_id} "
            f"approval_status={self.approval_status}>"
        )
