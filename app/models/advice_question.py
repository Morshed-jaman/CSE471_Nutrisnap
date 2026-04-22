from datetime import datetime

from app.extensions import db


class AdviceQuestion(db.Model):
    __tablename__ = "advice_questions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    expert_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    question_text = db.Column(db.Text, nullable=False)
    response_text = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=False, default="pending", index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    answered_at = db.Column(db.DateTime, nullable=True)

    user = db.relationship("User", back_populates="advice_questions", foreign_keys=[user_id])
    expert = db.relationship("User", back_populates="expert_replies", foreign_keys=[expert_id])

    def __repr__(self) -> str:
        return (
            f"<AdviceQuestion id={self.id} user_id={self.user_id} "
            f"status={self.status} expert_id={self.expert_id}>"
        )
