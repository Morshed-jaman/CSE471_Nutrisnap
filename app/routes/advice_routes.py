from datetime import datetime

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models import AdviceQuestion
from app.services.auth_service import role_required, subscriber_required, verified_expert_required

advice_bp = Blueprint("advice", __name__)


def _clean_text(raw_value: str | None) -> str:
    return (raw_value or "").strip()


@advice_bp.route("/nutritionist-advice", methods=["GET", "POST"])
@login_required
@role_required("user")
@subscriber_required
def user_advice():
    if request.method == "POST":
        question_text = _clean_text(request.form.get("question_text"))
        if not question_text:
            flash("Please enter your nutrition question.", "danger")
            return redirect(url_for("advice.user_advice"))

        if len(question_text) > 1200:
            flash("Question is too long. Please keep it under 1200 characters.", "danger")
            return redirect(url_for("advice.user_advice"))

        try:
            db.session.add(
                AdviceQuestion(
                    user_id=current_user.id,
                    question_text=question_text,
                    status="pending",
                )
            )
            db.session.commit()
            flash("Your nutrition question was submitted successfully.", "success")
        except Exception:
            db.session.rollback()
            flash("Could not submit your question right now. Please try again.", "danger")
        return redirect(url_for("advice.user_advice"))

    questions = (
        AdviceQuestion.query.filter_by(user_id=current_user.id)
        .order_by(AdviceQuestion.created_at.desc())
        .all()
    )
    pending_count = sum(1 for question in questions if question.status == "pending")

    return render_template(
        "advice/user_advice.html",
        questions=questions,
        pending_count=pending_count,
    )


@advice_bp.route("/nutritionist-advice/history")
@login_required
@role_required("user")
@subscriber_required
def user_advice_history():
    return redirect(url_for("advice.user_advice"))


@advice_bp.route("/nutrition-expert/advice-questions")
@login_required
@role_required("nutrition_expert")
@verified_expert_required
def expert_advice_dashboard():
    pending_questions = (
        AdviceQuestion.query.filter_by(status="pending")
        .order_by(AdviceQuestion.created_at.asc())
        .all()
    )
    answered_by_me = (
        AdviceQuestion.query.filter(AdviceQuestion.expert_id == current_user.id)
        .order_by(AdviceQuestion.answered_at.desc(), AdviceQuestion.updated_at.desc())
        .all()
    )

    return render_template(
        "advice/expert_dashboard.html",
        pending_questions=pending_questions,
        answered_by_me=answered_by_me,
    )


@advice_bp.route("/nutrition-expert/advice-questions/<int:question_id>/reply", methods=["POST"])
@login_required
@role_required("nutrition_expert")
@verified_expert_required
def submit_advice_reply(question_id: int):
    question = db.session.get(AdviceQuestion, question_id)
    if not question:
        abort(404)

    if question.status == "answered":
        flash("This question has already been answered.", "info")
        return redirect(url_for("advice.expert_advice_dashboard"))

    response_text = _clean_text(request.form.get("response_text"))
    if not response_text:
        flash("Please write advice before submitting.", "danger")
        return redirect(url_for("advice.expert_advice_dashboard"))

    if len(response_text) > 2000:
        flash("Advice response is too long. Please keep it under 2000 characters.", "danger")
        return redirect(url_for("advice.expert_advice_dashboard"))

    try:
        question.response_text = response_text
        question.expert_id = current_user.id
        question.status = "answered"
        question.answered_at = datetime.utcnow()
        db.session.commit()
        flash("Advice reply submitted successfully.", "success")
    except Exception:
        db.session.rollback()
        flash("Could not submit advice response right now.", "danger")

    return redirect(url_for("advice.expert_advice_dashboard"))
