from collections import defaultdict
from datetime import date, timedelta

from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, url_for
from sqlalchemy import or_

from app.extensions import db
from app.models import MealLog
from app.services.analytics_service import (
    build_weekly_tracking_context,
    has_nutrition_values,
    parse_week_start,
    safe_float,
    week_start_for,
)
from app.services.nutrition_service import (
    NutritionServiceError,
    get_nutrition_data,
    get_nutrition_insights,
)

nutrition_bp = Blueprint("nutrition", __name__)


def _meal_label(meal: MealLog) -> str:
    base = meal.title or f"{meal.meal_type.capitalize()} meal"
    return f"{base} ({meal.meal_date.strftime('%d %b')})"


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
                    "nutrition/nutrition_search.html",
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
        "nutrition/nutrition_search.html",
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

    next_url = (
        request.form.get("next") or request.referrer or url_for("meal.meal_detail", meal_id=id)
    )

    if has_nutrition_values(meal):
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
    )


@nutrition_bp.route("/weekly-tracking")
def weekly_tracking():
    requested_start = request.args.get("start_date")
    week_start = parse_week_start(requested_start)
    weekly_context = build_weekly_tracking_context(week_start)

    current_week_start = week_start_for(date.today())
    latest_meal = MealLog.query.order_by(MealLog.meal_date.desc()).first()

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
def weekly_tracking_data_api():
    requested_start = request.args.get("start_date")
    week_start = parse_week_start(requested_start)
    context = build_weekly_tracking_context(week_start)

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
