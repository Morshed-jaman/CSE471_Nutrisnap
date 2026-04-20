import os
import re

import requests
from flask import current_app, has_app_context

SPOONACULAR_ENDPOINT = "https://api.spoonacular.com/recipes/guessNutrition"
SPOONACULAR_SEARCH_ENDPOINT = "https://api.spoonacular.com/recipes/complexSearch"


class NutritionServiceError(RuntimeError):
    """Raised when nutrition data cannot be retrieved or parsed."""


def _config_or_env(key: str, default: str | None = None) -> str | None:
    if has_app_context():
        config_value = current_app.config.get(key)
        if config_value not in (None, ""):
            return str(config_value)

    env_value = os.getenv(key)
    if env_value not in (None, ""):
        return env_value
    return default


def _as_float(nutrient_block):
    if nutrient_block is None:
        return None

    if isinstance(nutrient_block, dict):
        value = nutrient_block.get("value")
    else:
        value = nutrient_block

    if isinstance(value, str):
        match = re.search(r"-?\d+(\.\d+)?", value)
        value = match.group(0) if match else None

    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _call_spoonacular(url: str, api_key: str, params: dict) -> dict:
    try:
        response = requests.get(
            url,
            params={"apiKey": api_key, **params},
            timeout=15,
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
        return response.json()
    except ValueError as exc:
        raise NutritionServiceError("Received an invalid response from nutrition service.") from exc


def _normalize_payload(calories, protein, carbohydrates, fats):
    return {
        "calories": _as_float(calories),
        "protein": _as_float(protein),
        "carbohydrates": _as_float(carbohydrates),
        "fats": _as_float(fats),
    }


def _has_any_nutrition(data: dict) -> bool:
    return any(data.get(key) is not None for key in ("calories", "protein", "carbohydrates", "fats"))


def _extract_guess_nutrition(payload: dict) -> dict:
    return _normalize_payload(
        payload.get("calories"),
        payload.get("protein"),
        payload.get("carbs"),
        payload.get("fat"),
    )


def _extract_complex_search_nutrition(payload: dict) -> dict:
    results = payload.get("results") or []
    if not results:
        return _normalize_payload(None, None, None, None)

    first = results[0] or {}
    nutrients = (first.get("nutrition") or {}).get("nutrients") or []

    calories = protein = carbohydrates = fats = None
    for nutrient in nutrients:
        name = (nutrient.get("name") or "").strip().lower()
        value = nutrient.get("amount")
        if name == "calories":
            calories = value
        elif name == "protein":
            protein = value
        elif name in {"carbohydrates", "carbs"}:
            carbohydrates = value
        elif name in {"fat", "fats"}:
            fats = value

    return _normalize_payload(calories, protein, carbohydrates, fats)


def get_nutrition_data(food_name: str) -> dict:
    api_key = _config_or_env("NUTRITION_API_KEY")
    if not api_key:
        raise NutritionServiceError("NUTRITION_API_KEY is missing. Please set it in your .env file.")

    query = (food_name or "").strip()
    if not query:
        raise NutritionServiceError("Please provide a food name for nutrition analysis.")

    # 1) Direct nutrition guess by free text title
    guess_payload = _call_spoonacular(
        SPOONACULAR_ENDPOINT,
        api_key,
        {"title": query},
    )
    guess_data = _extract_guess_nutrition(guess_payload)
    if _has_any_nutrition(guess_data):
        return guess_data

    # 2) Fallback: recipe search with embedded nutrition
    search_payload = _call_spoonacular(
        SPOONACULAR_SEARCH_ENDPOINT,
        api_key,
        {
            "query": query,
            "number": 1,
            "addRecipeNutrition": True,
            "instructionsRequired": False,
        },
    )
    search_data = _extract_complex_search_nutrition(search_payload)
    if _has_any_nutrition(search_data):
        return search_data

    raise NutritionServiceError(
        "No nutrition data found for this food. Try a more specific name (e.g., 'grilled chicken breast')."
    )


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
