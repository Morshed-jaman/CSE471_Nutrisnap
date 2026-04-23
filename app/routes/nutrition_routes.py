from collections import defaultdict
from datetime import date, timedelta

from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import or_

from app.extensions import db
from app.models import FavoriteMeal, MealLog, WaterIntake
from app.services.analytics_service import (
    build_weekly_tracking_context,
    has_nutrition_values,
    parse_week_start,
    safe_float,
    week_start_for,
)
from app.services.auth_service import role_required
from app.services.nutrition_service import (
    NutritionServiceError,
    get_ai_nutrition_explanation,
    get_nutrition_data,
    get_nutrition_insights,
)
from app.services.weather_service import get_hydration_recommendation

nutrition_bp = Blueprint("nutrition", __name__)
MAX_SINGLE_WATER_ENTRY_ML = 5000
RECENT_WATER_ENTRIES_LIMIT = 15


def _meal_label(meal: MealLog) -> str:
    base = meal.title or f"{meal.meal_type.capitalize()} meal"
    return f"{base} ({meal.meal_date.strftime('%d %b')})"


def _meal_query_candidates(meal: MealLog) -> list[str]:
    candidates: list[str] = []

    def add_candidate(value: str | None):
        text = (value or "").strip()
        if text and text not in candidates:
            candidates.append(text)

    add_candidate(meal.title)
    add_candidate(meal.note)
    add_candidate(f"{meal.title or ''} {meal.note or ''}".strip())
    add_candidate(f"{meal.meal_type} meal")

    # Final fallback for weak titles/notes so user analysis still works.
    fallback_by_type = {
        "breakfast": "oatmeal with fruit",
        "lunch": "grilled chicken with rice",
        "dinner": "grilled fish with vegetables",
        "snack": "mixed nuts",
    }
    add_candidate(fallback_by_type.get((meal.meal_type or "").lower()))
    return candidates


def _meal_visibility_filter(query):
    if current_user.role == "admin":
        return query
    return query.filter(MealLog.user_id == current_user.id)


def _optional_float(value):
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _meter_payload(
    label: str,
    value,
    unit: str,
    target: float,
    lower_is_better: bool = False,
):
    numeric = _optional_float(value)
    if numeric is None:
        return {
            "label": label,
            "value": None,
            "unit": unit,
            "percent": None,
            "tone": "muted",
            "hint": "No data",
        }

    ratio = (numeric / target) * 100 if target > 0 else 0
    percent = max(6, min(int(round(ratio)), 100))

    if lower_is_better:
        if numeric <= target * 0.75:
            tone = "good"
            hint = "Great range"
        elif numeric <= target:
            tone = "ok"
            hint = "Within range"
        else:
            tone = "warn"
            hint = "Consider lowering"
    else:
        if numeric >= target:
            tone = "good"
            hint = "Target met"
        elif numeric >= target * 0.6:
            tone = "ok"
            hint = "Close to target"
        else:
            tone = "warn"
            hint = "Can improve"

    return {
        "label": label,
        "value": round(numeric, 2),
        "unit": unit,
        "percent": percent,
        "tone": tone,
        "hint": hint,
    }


def _meal_health_payload(calories, protein, carbohydrates, fats) -> dict:
    calories_value = _optional_float(calories)
    protein_value = _optional_float(protein)
    carbs_value = _optional_float(carbohydrates)
    fats_value = _optional_float(fats)

    score = 0
    strengths: list[str] = []
    warnings: list[str] = []

    if protein_value is None:
        warnings.append("Protein data missing")
    elif protein_value >= 25:
        score += 28
        strengths.append("Strong protein support")
    elif protein_value >= 15:
        score += 20
        strengths.append("Moderate protein level")
    elif protein_value >= 8:
        score += 12
        warnings.append("Protein could be higher")
    else:
        score += 5
        warnings.append("Low protein for satiety")

    if calories_value is None:
        warnings.append("Calories data missing")
    elif calories_value <= 450:
        score += 24
        strengths.append("Calorie target friendly")
    elif calories_value <= 650:
        score += 16
    elif calories_value <= 850:
        score += 10
        warnings.append("Calories are on the higher side")
    else:
        score += 4
        warnings.append("High calorie load")

    if carbs_value is None:
        warnings.append("Carbohydrates data missing")
    elif 20 <= carbs_value <= 60:
        score += 24
        strengths.append("Carbs in balanced range")
    elif 10 <= carbs_value < 20 or 60 < carbs_value <= 80:
        score += 16
    else:
        score += 8
        warnings.append("Carbohydrates are less balanced")

    if fats_value is None:
        warnings.append("Fats data missing")
    elif 8 <= fats_value <= 22:
        score += 24
        strengths.append("Fats in healthy range")
    elif 5 <= fats_value < 8 or 22 < fats_value <= 30:
        score += 16
    else:
        score += 8
        warnings.append("Fats are less balanced")

    score = max(0, min(score, 100))

    if score >= 80:
        label = "Excellent"
        tone = "good"
    elif score >= 65:
        label = "Good"
        tone = "ok"
    elif score >= 50:
        label = "Fair"
        tone = "warn"
    else:
        label = "Needs Attention"
        tone = "warn"

    return {
        "score": score,
        "label": label,
        "tone": tone,
        "strengths": strengths[:2],
        "warnings": warnings[:2],
    }


def _water_tracker_context(user_id: int) -> dict:
    today = date.today()
    today_entries = (
        WaterIntake.query.filter(
            WaterIntake.user_id == user_id,
            WaterIntake.intake_date == today,
        )
        .order_by(WaterIntake.created_at.desc())
        .all()
    )
    recent_entries = (
        WaterIntake.query.filter(WaterIntake.user_id == user_id)
        .order_by(WaterIntake.created_at.desc())
        .limit(RECENT_WATER_ENTRIES_LIMIT)
        .all()
    )

    hydration = get_hydration_recommendation()
    today_total_ml = sum(entry.amount_ml for entry in today_entries)
    recommended_ml = hydration["recommended_ml"]
    remaining_ml = max(recommended_ml - today_total_ml, 0)
    progress_percent = round((today_total_ml / recommended_ml) * 100, 1) if recommended_ml > 0 else 0.0

    return {
        "today_entries": today_entries,
        "recent_entries": recent_entries,
        "today_date": today,
        "today_total_ml": today_total_ml,
        "recommended_ml": recommended_ml,
        "remaining_ml": remaining_ml,
        "goal_achieved": today_total_ml >= recommended_ml,
        "progress_percent": min(progress_percent, 100.0),
        "temperature_c": hydration["temperature_c"],
        "hydration_reason": hydration["reason_text"],
    }



def _parse_water_amount(raw_amount: str | None) -> int | None:
    amount_text = (raw_amount or "").strip()
    if not amount_text or not amount_text.isdigit():
        return None

    amount_ml = int(amount_text)
    if amount_ml <= 0:
        return None

    return amount_ml

def _nutrition_search_recent_meals() -> list[MealLog]:
    recent_query = MealLog.query.order_by(MealLog.created_at.desc())
    recent_query = _meal_visibility_filter(recent_query)
    return recent_query.limit(8).all()


def _nutrition_payload_from_form() -> dict:
    return {
        "calories": _optional_float(request.form.get("calories")),
        "protein": _optional_float(request.form.get("protein")),
        "carbohydrates": _optional_float(request.form.get("carbohydrates")),
        "fats": _optional_float(request.form.get("fats")),
    }


def _render_nutrition_explanation_page(
    *,
    food_name: str = "",
    nutrition_result: dict | None = None,
    insights: list[str] | None = None,
    ai_explanation: str | None = None,
    status_code: int = 200,
):
    response = render_template(
        "nutrition/nutrition_explanation.html",
        food_name=food_name,
        nutrition_result=nutrition_result,
        insights=insights or [],
        ai_explanation=ai_explanation,
        is_system_view=current_user.role == "admin",
    )
    if status_code != 200:
        return response, status_code
    return response


@nutrition_bp.route("/nutrition-search", methods=["GET", "POST"])
@login_required
@role_required("user", "admin")
def nutrition_search():
    nutrition_result = None
    insights = []
    food_name = ""

    recent_meals = _nutrition_search_recent_meals()

    if request.method == "POST":
        food_name = (request.form.get("food_name") or "").strip()

        if not food_name:
            flash("Please enter a food name.", "danger")
            return (
                render_template(
                    "nutrition/nutrition_search.html",
                    food_name=food_name,
                    recent_meals=recent_meals,
                    is_system_view=current_user.role == "admin",
                ),
                400,
            )

        try:
            nutrition_result = get_nutrition_data(food_name)
            insights = get_nutrition_insights(
                nutrition_result.get("calories"),
                nutrition_result.get("protein"),
                nutrition_result.get("carbohydrates"),
                nutrition_result.get("fats"),
            )
        except NutritionServiceError as exc:
            flash(str(exc), "danger")
        except Exception:
            flash("Unexpected error occurred while fetching nutrition data.", "danger")

    return render_template(
        "nutrition/nutrition_search.html",
        food_name=food_name,
        nutrition_result=nutrition_result,
        insights=insights,
        recent_meals=recent_meals,
        is_system_view=current_user.role == "admin",
    )



@nutrition_bp.route("/nutrition-explanation", methods=["GET", "POST"])
@login_required
@role_required("user", "admin")
def nutrition_explanation():
    if request.method == "GET":
        return _render_nutrition_explanation_page()

    food_name = (request.form.get("food_name") or "").strip()
    nutrition_result = _nutrition_payload_from_form()
    insights = []
    ai_explanation = None

    if not food_name:
        flash("Please enter a food name for AI explanation.", "danger")
        return _render_nutrition_explanation_page(
            food_name=food_name,
            nutrition_result=nutrition_result,
            insights=insights,
            ai_explanation=ai_explanation,
            status_code=400,
        )

    if not any(value is not None for value in nutrition_result.values()):
        flash(
            "AI explanation is separated from Nutrition API retrieval. "
            "Provide nutrition values here or open from Nutrition Search with prefilled data.",
            "danger",
        )
        return _render_nutrition_explanation_page(
            food_name=food_name,
            nutrition_result=nutrition_result,
            insights=insights,
            ai_explanation=ai_explanation,
            status_code=400,
        )

    insights = get_nutrition_insights(
        nutrition_result.get("calories"),
        nutrition_result.get("protein"),
        nutrition_result.get("carbohydrates"),
        nutrition_result.get("fats"),
    )

    try:
        ai_explanation = get_ai_nutrition_explanation(food_name, nutrition_result)
    except NutritionServiceError as exc:
        flash(str(exc), "danger")
    except Exception:
        flash("Unexpected error occurred while generating AI nutrition explanation.", "danger")

    return _render_nutrition_explanation_page(
        food_name=food_name,
        nutrition_result=nutrition_result,
        insights=insights,
        ai_explanation=ai_explanation,
    )


@nutrition_bp.route("/water-intake", methods=["GET"])
@nutrition_bp.route("/water-tracker", methods=["GET"])
@login_required
@role_required("user")
def water_tracker():
    return render_template("nutrition/water_tracker.html", **_water_tracker_context(current_user.id))


@nutrition_bp.route("/water-intake", methods=["POST"])
@nutrition_bp.route("/water-tracker/add", methods=["POST"])
@login_required
@role_required("user")
def add_water_entry():
    amount_ml = _parse_water_amount(request.form.get("amount_ml"))
    if amount_ml is None:
        flash("Water amount must be a positive whole number in ml.", "danger")
        return redirect(url_for("nutrition.water_tracker"))

    if amount_ml > MAX_SINGLE_WATER_ENTRY_ML:
        flash(
            f"Single water entry looks too high. Please enter up to {MAX_SINGLE_WATER_ENTRY_ML} ml.",
            "danger",
        )
        return redirect(url_for("nutrition.water_tracker"))

    try:
        db.session.add(
            WaterIntake(
                user_id=current_user.id,
                amount_ml=amount_ml,
                intake_date=date.today(),
            )
        )
        db.session.commit()
        flash(f"Added {amount_ml} ml to today's water intake.", "success")
    except Exception:
        db.session.rollback()
        flash("Could not save water entry. Please try again.", "danger")

    return redirect(url_for("nutrition.water_tracker"))


@nutrition_bp.route("/water-tracker/delete/<int:entry_id>", methods=["POST"])
@login_required
@role_required("user")
def delete_water_entry(entry_id: int):
    entry = db.session.get(WaterIntake, entry_id)
    if not entry:
        abort(404)

    if entry.user_id != current_user.id:
        flash("You can delete only your own water entries.", "danger")
        return redirect(url_for("nutrition.water_tracker"))

    try:
        db.session.delete(entry)
        db.session.commit()
        flash("Water entry deleted.", "success")
    except Exception:
        db.session.rollback()
        flash("Could not delete this water entry. Please try again.", "danger")

    return redirect(url_for("nutrition.water_tracker"))


@nutrition_bp.route("/analyze-meal/<int:id>", methods=["POST"])
@login_required
@role_required("user", "admin")
def analyze_meal(id: int):
    meal = db.session.get(MealLog, id)
    if not meal:
        abort(404)

    if current_user.role == "user" and meal.user_id != current_user.id:
        flash("You can analyze only your own meals. Save this meal to My Meal Logs first.", "danger")
        return redirect(url_for("meal.meal_detail", meal_id=id))

    next_url = (
        request.form.get("next") or request.referrer or url_for("meal.meal_detail", meal_id=id)
    )

    if has_nutrition_values(meal):
        flash("Nutrition already analyzed for this meal.", "info")
        return redirect(next_url)

    try:
        nutrition = None
        for food_query in _meal_query_candidates(meal):
            try:
                nutrition = get_nutrition_data(food_query)
                if nutrition:
                    break
            except NutritionServiceError:
                nutrition = None
                continue

        if not nutrition:
            raise NutritionServiceError(
                "Could not analyze nutrition for this meal. Edit title/note with a clearer food name and try again."
            )

        meal.calories = nutrition.get("calories")
        meal.protein = nutrition.get("protein")
        meal.carbohydrates = nutrition.get("carbohydrates")
        meal.fats = nutrition.get("fats")

        db.session.commit()
        flash("Nutrition data analyzed and saved for this meal.", "success")
    except NutritionServiceError as exc:
        db.session.rollback()
        flash(str(exc), "danger")
    except Exception:
        db.session.rollback()
        flash("Failed to analyze nutrition for this meal.", "danger")

    return redirect(next_url)


@nutrition_bp.route("/nutrition-analytics")
@login_required
@role_required("user", "admin")
def nutrition_analytics():
    analyzed_query = MealLog.query.filter(
        or_(
            MealLog.calories.isnot(None),
            MealLog.protein.isnot(None),
            MealLog.carbohydrates.isnot(None),
            MealLog.fats.isnot(None),
        )
    )
    analyzed_query = _meal_visibility_filter(analyzed_query)

    analyzed_meals = analyzed_query.order_by(MealLog.meal_date.desc(), MealLog.created_at.desc()).all()

    total_calories = sum(safe_float(meal.calories) for meal in analyzed_meals)
    total_protein = sum(safe_float(meal.protein) for meal in analyzed_meals)
    total_carbohydrates = sum(safe_float(meal.carbohydrates) for meal in analyzed_meals)
    total_fats = sum(safe_float(meal.fats) for meal in analyzed_meals)

    meals_with_calories = [meal for meal in analyzed_meals if meal.calories is not None]
    average_calories = total_calories / len(meals_with_calories) if meals_with_calories else 0

    recent_meals = analyzed_meals[:8]

    insight_tags = []
    seen_tags = set()
    for meal in recent_meals:
        for tag in get_nutrition_insights(
            meal.calories, meal.protein, meal.carbohydrates, meal.fats
        ):
            if tag not in seen_tags:
                seen_tags.add(tag)
                insight_tags.append(tag)

    if not insight_tags and not analyzed_meals:
        insight_tags.append("Add meals and analyze nutrition to unlock insights")

    return render_template(
        "nutrition/nutrition_analytics.html",
        total_calories=round(total_calories, 2),
        total_protein=round(total_protein, 2),
        total_carbohydrates=round(total_carbohydrates, 2),
        total_fats=round(total_fats, 2),
        average_calories=round(average_calories, 2),
        recent_meals=recent_meals,
        insight_tags=insight_tags,
        is_system_view=current_user.role == "admin",
    )


@nutrition_bp.route("/weekly-tracking")
@login_required
@role_required("user", "admin")
def weekly_tracking():
    requested_start = request.args.get("start_date")
    week_start = parse_week_start(requested_start)

    target_user_id = None if current_user.role == "admin" else current_user.id
    weekly_context = build_weekly_tracking_context(week_start, user_id=target_user_id)

    current_week_start = week_start_for(date.today())

    latest_meal_query = MealLog.query.order_by(MealLog.meal_date.desc())
    latest_meal_query = _meal_visibility_filter(latest_meal_query)
    latest_meal = latest_meal_query.first()

    latest_data_week_start = None
    latest_data_week_label = None
    if latest_meal:
        latest_data_week_start_value = week_start_for(latest_meal.meal_date)
        if latest_data_week_start_value != week_start:
            latest_data_week_start = latest_data_week_start_value.isoformat()
            latest_data_week_end = latest_data_week_start_value + timedelta(days=6)
            latest_data_week_label = (
                f"{latest_data_week_start_value.strftime('%d %b %Y')} - "
                f"{latest_data_week_end.strftime('%d %b %Y')}"
            )

    return render_template(
        "nutrition/weekly_tracking.html",
        **weekly_context,
        selected_start_date=week_start.isoformat(),
        previous_week_start=(week_start - timedelta(days=7)).isoformat(),
        next_week_start=(week_start + timedelta(days=7)).isoformat(),
        current_week_start=current_week_start.isoformat(),
        is_current_week=(week_start == current_week_start),
        latest_data_week_start=latest_data_week_start,
        latest_data_week_label=latest_data_week_label,
        is_system_view=current_user.role == "admin",
    )


@nutrition_bp.route("/healthy-indicator")
@login_required
@role_required("user", "admin")
def healthy_indicator():
    analyzed_query = MealLog.query.filter(
        or_(
            MealLog.calories.isnot(None),
            MealLog.protein.isnot(None),
            MealLog.carbohydrates.isnot(None),
            MealLog.fats.isnot(None),
        )
    )
    analyzed_query = _meal_visibility_filter(analyzed_query)
    analyzed_meals = analyzed_query.order_by(MealLog.meal_date.desc(), MealLog.created_at.desc()).all()

    can_manage_favorites = current_user.role == "user"
    favorite_meal_ids = set()
    if can_manage_favorites:
        favorite_meal_ids = {favorite.meal_log_id for favorite in FavoriteMeal.query.all()}

    tag_counts = defaultdict(int)
    meal_cards = []
    for meal in analyzed_meals:
        tags = get_nutrition_insights(meal.calories, meal.protein, meal.carbohydrates, meal.fats)
        for tag in tags:
            tag_counts[tag] += 1

        health_payload = _meal_health_payload(
            meal.calories,
            meal.protein,
            meal.carbohydrates,
            meal.fats,
        )

        meal_cards.append(
            {
                "meal": meal,
                "tags": tags,
                "health": health_payload,
                "meters": [
                    _meter_payload("Calories", meal.calories, "kcal", target=500, lower_is_better=True),
                    _meter_payload("Protein", meal.protein, "g", target=30),
                    _meter_payload(
                        "Carbohydrates",
                        meal.carbohydrates,
                        "g",
                        target=60,
                        lower_is_better=True,
                    ),
                    _meter_payload("Fats", meal.fats, "g", target=22, lower_is_better=True),
                    {
                        "label": "Sugar",
                        "value": None,
                        "unit": "g",
                        "percent": None,
                        "tone": "muted",
                        "hint": "Not stored in meal model",
                    },
                    {
                        "label": "Sodium",
                        "value": None,
                        "unit": "mg",
                        "percent": None,
                        "tone": "muted",
                        "hint": "Not stored in meal model",
                    },
                ],
            }
        )

    health_scores = [card["health"]["score"] for card in meal_cards]
    average_health_score = round(sum(health_scores) / len(health_scores), 1) if health_scores else 0.0
    excellent_count = sum(1 for score in health_scores if score >= 80)
    good_count = sum(1 for score in health_scores if 65 <= score < 80)
    fair_count = sum(1 for score in health_scores if 50 <= score < 65)
    attention_count = sum(1 for score in health_scores if score < 50)

    top_health_card = max(meal_cards, key=lambda card: card["health"]["score"], default=None)
    focus_cards = sorted(
        [card for card in meal_cards if card["health"]["score"] < 65],
        key=lambda card: card["health"]["score"],
    )[:3]

    summary_recommendations: list[str] = []
    if analyzed_meals:
        if average_health_score < 65:
            summary_recommendations.append(
                "Overall meal quality can improve. Prioritize balanced macros in your next uploads."
            )

        if tag_counts.get("High Protein", 0) < max(1, len(analyzed_meals) // 3):
            summary_recommendations.append(
                "Add more lean protein choices to improve satiety and muscle support."
            )

        if tag_counts.get("Balanced Meal", 0) < max(1, len(analyzed_meals) // 3):
            summary_recommendations.append(
                "Aim for more balanced meals by combining protein, moderate carbs, and controlled fats."
            )

        if not summary_recommendations:
            summary_recommendations.append(
                "Healthy consistency looks strong. Keep maintaining this pattern."
            )

    return render_template(
        "meals/healthy_indicator.html",
        meal_cards=meal_cards,
        total_analyzed=len(analyzed_meals),
        tag_counts=dict(tag_counts),
        favorite_meal_ids=favorite_meal_ids,
        can_manage_favorites=can_manage_favorites,
        average_health_score=average_health_score,
        excellent_count=excellent_count,
        good_count=good_count,
        fair_count=fair_count,
        attention_count=attention_count,
        top_health_card=top_health_card,
        focus_cards=focus_cards,
        summary_recommendations=summary_recommendations,
    )


@nutrition_bp.route("/api/nutrition-analytics-data")
@login_required
@role_required("user", "admin")
def nutrition_analytics_data_api():
    analyzed_query = MealLog.query.filter(
        or_(
            MealLog.calories.isnot(None),
            MealLog.protein.isnot(None),
            MealLog.carbohydrates.isnot(None),
            MealLog.fats.isnot(None),
        )
    )
    analyzed_query = _meal_visibility_filter(analyzed_query)

    analyzed_meals = analyzed_query.order_by(MealLog.meal_date.asc(), MealLog.created_at.asc()).all()

    calories_by_meal = [
        {
            "label": _meal_label(meal),
            "value": round(safe_float(meal.calories), 2),
        }
        for meal in analyzed_meals
    ]

    macros_distribution = {
        "protein": round(sum(safe_float(meal.protein) for meal in analyzed_meals), 2),
        "carbohydrates": round(
            sum(safe_float(meal.carbohydrates) for meal in analyzed_meals), 2
        ),
        "fats": round(sum(safe_float(meal.fats) for meal in analyzed_meals), 2),
    }

    timeline_totals = defaultdict(float)
    for meal in analyzed_meals:
        timeline_totals[meal.meal_date.isoformat()] += safe_float(meal.calories)

    timeline_data = [
        {"date": date_key, "calories": round(calories, 2)}
        for date_key, calories in sorted(timeline_totals.items())
    ]

    return jsonify(
        {
            "calories_by_meal": calories_by_meal,
            "macros_distribution": macros_distribution,
            "timeline_data": timeline_data,
        }
    )


@nutrition_bp.route("/api/weekly-tracking-data")
@login_required
@role_required("user", "admin")
def weekly_tracking_data_api():
    requested_start = request.args.get("start_date")
    week_start = parse_week_start(requested_start)
    target_user_id = None if current_user.role == "admin" else current_user.id
    context = build_weekly_tracking_context(week_start, user_id=target_user_id)

    return jsonify(
        {
            "week_start": context["week_start"].isoformat(),
            "week_end": context["week_end"].isoformat(),
            "week_range_label": context["week_range_label"],
            "summary": {
                "total_calories": context["total_calories"],
                "total_protein": context["total_protein"],
                "total_carbohydrates": context["total_carbohydrates"],
                "total_fats": context["total_fats"],
                "total_meals": context["total_meals"],
                "analyzed_meals": context["analyzed_meals"],
                "avg_calories_per_day": context["avg_calories_per_day"],
                "avg_meals_per_day": context["avg_meals_per_day"],
            },
            "daily_breakdown": [
                {
                    "date": day["date"].isoformat(),
                    "label": day["label"],
                    "short_label": day["short_label"],
                    "display_date": day["display_date"],
                    "meal_count": day["meal_count"],
                    "analyzed_count": day["analyzed_count"],
                    "calories": day["calories"],
                    "protein": day["protein"],
                    "carbohydrates": day["carbohydrates"],
                    "fats": day["fats"],
                }
                for day in context["daily_breakdown"]
            ],
            "chart_payload": context["chart_payload"],
            "weekly_insights": context["weekly_insights"],
        }
    )
