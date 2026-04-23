from datetime import date, datetime, timedelta

from app.models import MealLog


def safe_float(value):
    try:
        return float(value) if value is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def has_nutrition_values(meal: MealLog) -> bool:
    return any(
        value is not None
        for value in [meal.calories, meal.protein, meal.carbohydrates, meal.fats]
    )


def week_start_for(day_value: date) -> date:
    return day_value - timedelta(days=day_value.weekday())


def parse_week_start(raw_start_date: str | None) -> date:
    if not raw_start_date:
        return week_start_for(date.today())

    try:
        parsed = datetime.strptime(raw_start_date, "%Y-%m-%d").date()
    except ValueError:
        return week_start_for(date.today())

    return week_start_for(parsed)


def build_weekly_insights(
    total_calories: float,
    total_protein: float,
    total_carbohydrates: float,
    total_fats: float,
    total_meals: int,
    analyzed_meals: int,
) -> list[str]:
    insights: list[str] = []

    if total_meals == 0:
        return ["Needs More Tracking"]

    if analyzed_meals < max(2, total_meals // 2):
        insights.append("Needs More Tracking")

    if total_protein > 0 and total_protein >= total_carbohydrates * 0.75:
        insights.append("High Protein Week")

    avg_calories_per_day = total_calories / 7
    if 0 < avg_calories_per_day < 1600:
        insights.append("Low Calorie Week")

    macro_sum = total_protein + total_carbohydrates + total_fats
    if macro_sum > 0:
        protein_ratio = total_protein / macro_sum
        carbs_ratio = total_carbohydrates / macro_sum
        fats_ratio = total_fats / macro_sum

        if (
            0.2 <= protein_ratio <= 0.45
            and 0.3 <= carbs_ratio <= 0.55
            and 0.15 <= fats_ratio <= 0.4
        ):
            insights.append("Balanced Intake")

    if not insights:
        insights.append("Steady Nutrition Week")

    return insights[:3]


def build_weekly_tracking_context(week_start: date, user_id: int | None = None) -> dict:
    week_end = week_start + timedelta(days=6)

    query = MealLog.query.filter(
        MealLog.meal_date >= week_start,
        MealLog.meal_date <= week_end,
    )
    if user_id is not None:
        query = query.filter(MealLog.user_id == user_id)

    weekly_meals = query.order_by(MealLog.meal_date.desc(), MealLog.created_at.desc()).all()

    daily_map = {
        week_start + timedelta(days=offset): {
            "date": week_start + timedelta(days=offset),
            "label": (week_start + timedelta(days=offset)).strftime("%A"),
            "short_label": (week_start + timedelta(days=offset)).strftime("%a"),
            "display_date": (week_start + timedelta(days=offset)).strftime("%d %b"),
            "meal_count": 0,
            "analyzed_count": 0,
            "calories": 0.0,
            "protein": 0.0,
            "carbohydrates": 0.0,
            "fats": 0.0,
        }
        for offset in range(7)
    }

    total_calories = 0.0
    total_protein = 0.0
    total_carbohydrates = 0.0
    total_fats = 0.0
    total_meals = 0
    analyzed_meals = 0

    for meal in weekly_meals:
        day_bucket = daily_map.get(meal.meal_date)
        if not day_bucket:
            continue

        day_bucket["meal_count"] += 1
        total_meals += 1

        has_nutrition = has_nutrition_values(meal)
        if has_nutrition:
            day_bucket["analyzed_count"] += 1
            analyzed_meals += 1

        calories = safe_float(meal.calories)
        protein = safe_float(meal.protein)
        carbohydrates = safe_float(meal.carbohydrates)
        fats = safe_float(meal.fats)

        day_bucket["calories"] += calories
        day_bucket["protein"] += protein
        day_bucket["carbohydrates"] += carbohydrates
        day_bucket["fats"] += fats

        total_calories += calories
        total_protein += protein
        total_carbohydrates += carbohydrates
        total_fats += fats

    daily_breakdown = []
    for offset in range(7):
        key = week_start + timedelta(days=offset)
        day_data = daily_map[key]
        day_data["calories"] = round(day_data["calories"], 2)
        day_data["protein"] = round(day_data["protein"], 2)
        day_data["carbohydrates"] = round(day_data["carbohydrates"], 2)
        day_data["fats"] = round(day_data["fats"], 2)
        daily_breakdown.append(day_data)

    avg_calories_per_day = round(total_calories / 7, 2)
    avg_meals_per_day = round(total_meals / 7, 2)

    weekly_insights = build_weekly_insights(
        total_calories,
        total_protein,
        total_carbohydrates,
        total_fats,
        total_meals,
        analyzed_meals,
    )

    chart_payload = {
        "labels": [f"{day['short_label']} {day['display_date']}" for day in daily_breakdown],
        "calories_by_day": [day["calories"] for day in daily_breakdown],
        "meals_by_day": [day["meal_count"] for day in daily_breakdown],
        "macros_distribution": {
            "protein": round(total_protein, 2),
            "carbohydrates": round(total_carbohydrates, 2),
            "fats": round(total_fats, 2),
        },
    }

    return {
        "week_start": week_start,
        "week_end": week_end,
        "week_range_label": f"{week_start.strftime('%d %b %Y')} - {week_end.strftime('%d %b %Y')}",
        "total_calories": round(total_calories, 2),
        "total_protein": round(total_protein, 2),
        "total_carbohydrates": round(total_carbohydrates, 2),
        "total_fats": round(total_fats, 2),
        "total_meals": total_meals,
        "analyzed_meals": analyzed_meals,
        "avg_calories_per_day": avg_calories_per_day,
        "avg_meals_per_day": avg_meals_per_day,
        "daily_breakdown": daily_breakdown,
        "weekly_meals": weekly_meals,
        "weekly_insights": weekly_insights,
        "chart_payload": chart_payload,
    }
