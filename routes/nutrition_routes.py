from collections import defaultdict

from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, url_for
from sqlalchemy import or_

from extensions import db
from models import MealLog
from services.nutrition_service import (
    NutritionServiceError,
    get_nutrition_data,
    get_nutrition_insights,
)

nutrition_bp = Blueprint("nutrition", __name__)


def _safe_float(value):
    try:
        return float(value) if value is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def _meal_label(meal: MealLog) -> str:
    base = meal.title or f"{meal.meal_type.capitalize()} meal"
    return f"{base} ({meal.meal_date.strftime('%d %b')})"


def _has_nutrition(meal: MealLog) -> bool:
    return any(value is not None for value in [meal.calories, meal.protein, meal.carbohydrates, meal.fats])


@nutrition_bp.route("/nutrition-search", methods=["GET", "POST"])
def nutrition_search():
    nutrition_result = None
    insights = []
    food_name = ""

    recent_meals = MealLog.query.order_by(MealLog.created_at.desc()).limit(8).all()

    if request.method == "POST":
        food_name = (request.form.get("food_name") or "").strip()

        if not food_name:
            flash("Please enter a food name.", "danger")
            return (
                render_template(
                    "nutrition_search.html",
                    food_name=food_name,
                    recent_meals=recent_meals,
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
        "nutrition_search.html",
        food_name=food_name,
        nutrition_result=nutrition_result,
        insights=insights,
        recent_meals=recent_meals,
    )


@nutrition_bp.route("/analyze-meal/<int:id>", methods=["POST"])
def analyze_meal(id: int):
    meal = db.session.get(MealLog, id)
    if not meal:
        abort(404)

    next_url = request.form.get("next") or request.referrer or url_for("meal.meal_detail", meal_id=id)

    if _has_nutrition(meal):
        flash("Nutrition already analyzed for this meal.", "info")
        return redirect(next_url)

    food_query = (meal.title or meal.note or f"{meal.meal_type} meal").strip()

    try:
        nutrition = get_nutrition_data(food_query)
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
def nutrition_analytics():
    analyzed_meals = (
        MealLog.query.filter(
            or_(
                MealLog.calories.isnot(None),
                MealLog.protein.isnot(None),
                MealLog.carbohydrates.isnot(None),
                MealLog.fats.isnot(None),
            )
        )
        .order_by(MealLog.meal_date.desc(), MealLog.created_at.desc())
        .all()
    )

    total_calories = sum(_safe_float(meal.calories) for meal in analyzed_meals)
    total_protein = sum(_safe_float(meal.protein) for meal in analyzed_meals)
    total_carbohydrates = sum(_safe_float(meal.carbohydrates) for meal in analyzed_meals)
    total_fats = sum(_safe_float(meal.fats) for meal in analyzed_meals)

    meals_with_calories = [meal for meal in analyzed_meals if meal.calories is not None]
    average_calories = (
        total_calories / len(meals_with_calories) if meals_with_calories else 0
    )

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
        "nutrition_analytics.html",
        total_calories=round(total_calories, 2),
        total_protein=round(total_protein, 2),
        total_carbohydrates=round(total_carbohydrates, 2),
        total_fats=round(total_fats, 2),
        average_calories=round(average_calories, 2),
        recent_meals=recent_meals,
        insight_tags=insight_tags,
    )


@nutrition_bp.route("/api/nutrition-analytics-data")
def nutrition_analytics_data_api():
    analyzed_meals = (
        MealLog.query.filter(
            or_(
                MealLog.calories.isnot(None),
                MealLog.protein.isnot(None),
                MealLog.carbohydrates.isnot(None),
                MealLog.fats.isnot(None),
            )
        )
        .order_by(MealLog.meal_date.asc(), MealLog.created_at.asc())
        .all()
    )

    calories_by_meal = [
        {
            "label": _meal_label(meal),
            "value": round(_safe_float(meal.calories), 2),
        }
        for meal in analyzed_meals
    ]

    macros_distribution = {
        "protein": round(sum(_safe_float(meal.protein) for meal in analyzed_meals), 2),
        "carbohydrates": round(
            sum(_safe_float(meal.carbohydrates) for meal in analyzed_meals), 2
        ),
        "fats": round(sum(_safe_float(meal.fats) for meal in analyzed_meals), 2),
    }

    timeline_totals = defaultdict(float)
    for meal in analyzed_meals:
        timeline_totals[meal.meal_date.isoformat()] += _safe_float(meal.calories)

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
