from datetime import datetime

from app.extensions import db


class MealLog(db.Model):
    __tablename__ = "meal_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
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

    user = db.relationship("User", back_populates="meal_logs")

    def __repr__(self) -> str:
        return (
            f"<MealLog id={self.id} user_id={self.user_id} meal_type={self.meal_type} "
            f"meal_date={self.meal_date.isoformat()}>"
        )
