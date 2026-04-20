from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), nullable=False, unique=True, index=True)
    phone = db.Column(db.String(40), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="user")
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    is_subscribed = db.Column(db.Boolean, nullable=False, default=False)
    vendor_status = db.Column(db.String(20), nullable=True)
    expert_status = db.Column(db.String(20), nullable=True)
    expert_credentials = db.Column(db.Text, nullable=True)
    expert_review_note = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    meal_logs = db.relationship("MealLog", back_populates="user", lazy="select")

    vendor_profile = db.relationship(
        "VendorProfile",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
        foreign_keys="VendorProfile.user_id",
    )

    owned_vendor = db.relationship(
        "Vendor",
        back_populates="owner_user",
        uselist=False,
        foreign_keys="Vendor.owner_user_id",
    )

    reviewed_vendor_profiles = db.relationship(
        "VendorProfile",
        back_populates="reviewed_by_admin",
        foreign_keys="VendorProfile.reviewed_by_admin_id",
    )

    reviews = db.relationship("Review", back_populates="user", lazy="select")
    vendor_subscriptions = db.relationship(
        "VendorSubscription",
        back_populates="user",
        lazy="select",
        cascade="all, delete-orphan",
    )

    advice_questions = db.relationship(
        "AdviceQuestion",
        back_populates="user",
        lazy="select",
        foreign_keys="AdviceQuestion.user_id",
        cascade="all, delete-orphan",
    )
    expert_replies = db.relationship(
        "AdviceQuestion",
        back_populates="expert",
        lazy="select",
        foreign_keys="AdviceQuestion.expert_id",
    )
    water_intakes = db.relationship(
        "WaterIntake",
        back_populates="user",
        lazy="select",
        cascade="all, delete-orphan",
    )

    def set_password(self, raw_password: str) -> None:
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password: str) -> bool:
        return check_password_hash(self.password_hash, raw_password)

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    @property
    def is_vendor(self) -> bool:
        return self.role == "vendor"

    @property
    def is_vendor_approved(self) -> bool:
        return self.is_vendor and self.vendor_status == "approved"

    @property
    def is_nutrition_expert(self) -> bool:
        return self.role == "nutrition_expert"

    @property
    def is_expert_verified(self) -> bool:
        return self.is_nutrition_expert and self.expert_status == "approved"

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email} role={self.role}>"
