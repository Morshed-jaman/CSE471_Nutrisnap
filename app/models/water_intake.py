from datetime import datetime, date

from app.extensions import db


class WaterIntake(db.Model):
    __tablename__ = "water_intakes"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    amount_ml = db.Column(db.Integer, nullable=False)
    intake_date = db.Column(db.Date, nullable=False, default=date.today, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    user = db.relationship("User", back_populates="water_intakes")

    def __repr__(self) -> str:
        return (
            f"<WaterIntake id={self.id} user_id={self.user_id} "
            f"amount_ml={self.amount_ml} intake_date={self.intake_date}>"
        )
