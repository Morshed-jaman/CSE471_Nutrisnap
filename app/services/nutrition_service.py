import os

import requests

SPOONACULAR_ENDPOINT = "https://api.spoonacular.com/recipes/guessNutrition"


class NutritionServiceError(RuntimeError):
    """Raised when nutrition data cannot be retrieved or parsed."""


def _as_float(nutrient_block):
    if nutrient_block is None:
        return None

    if isinstance(nutrient_block, dict):
        value = nutrient_block.get("value")
    else:
        value = nutrient_block

    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def get_nutrition_data(food_name: str) -> dict:
    api_key = os.getenv("NUTRITION_API_KEY")
    if not api_key:
        raise NutritionServiceError("NUTRITION_API_KEY is missing. Please set it in your .env file.")

    query = (food_name or "").strip()
    if not query:
        raise NutritionServiceError("Please provide a food name for nutrition analysis.")

    try:
        response = requests.get(
            SPOONACULAR_ENDPOINT,
            params={"apiKey": api_key, "title": query},
            timeout=12,
        )
    except requests.RequestException as exc:
        raise NutritionServiceError("Could not connect to the nutrition service.") from exc

    if response.status_code in (401, 402, 403):
        raise NutritionServiceError("Nutrition API key is invalid or quota is exceeded.")

    if response.status_code >= 500:
        raise NutritionServiceError("Nutrition service is temporarily unavailable.")

    if response.status_code >= 400:
        raise NutritionServiceError("Nutrition service rejected this request.")

    try:
        payload = response.json()
    except ValueError as exc:
        raise NutritionServiceError("Received an invalid response from nutrition service.") from exc

    calories = _as_float(payload.get("calories"))
    protein = _as_float(payload.get("protein"))
    carbohydrates = _as_float(payload.get("carbs"))
    fats = _as_float(payload.get("fat"))

    if all(value is None for value in [calories, protein, carbohydrates, fats]):
        raise NutritionServiceError("No nutrition data found for this food.")

    return {
        "calories": calories,
        "protein": protein,
        "carbohydrates": carbohydrates,
        "fats": fats,
    }


def get_nutrition_insights(calories, protein, carbohydrates, fats):
    insights = []

    def _safe(value):
        try:
            return float(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    calories = _safe(calories)
    protein = _safe(protein)
    carbohydrates = _safe(carbohydrates)
    fats = _safe(fats)

    if protein is not None and protein >= 25:
        insights.append("High Protein")

    if calories is not None and calories <= 400:
        insights.append("Low Calorie")

    if (
        calories is not None
        and protein is not None
        and carbohydrates is not None
        and fats is not None
        and protein >= 20
        and 20 <= carbohydrates <= 60
        and 8 <= fats <= 22
    ):
        insights.append("Balanced Meal")

    if not insights:
        insights.append("General Meal")

    return insights
