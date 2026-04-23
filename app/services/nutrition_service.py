import os
import re

import requests
from dotenv import load_dotenv
from flask import current_app, has_app_context

SPOONACULAR_ENDPOINT = "https://api.spoonacular.com/recipes/guessNutrition"
SPOONACULAR_SEARCH_ENDPOINT = "https://api.spoonacular.com/recipes/complexSearch"
DEFAULT_AI_CHAT_COMPLETIONS_ENDPOINT = "https://api.openai.com/v1/chat/completions"
OPENROUTER_CHAT_COMPLETIONS_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"


class NutritionServiceError(RuntimeError):
    """Raised when nutrition data cannot be retrieved or parsed."""


def _clean_env_value(value: str | None) -> str | None:
    if value is None:
        return None
#env values mainly

    cleaned = str(value).strip()
    if not cleaned:
        return None

    if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in {'"', "'"}:
        cleaned = cleaned[1:-1].strip()

    return cleaned or None


def _config_or_env(key: str, default: str | None = None) -> str | None:
    if has_app_context():
        config_value = _clean_env_value(current_app.config.get(key))
        if config_value is not None:
            return config_value

    env_value = _clean_env_value(os.getenv(key))
    if env_value is not None:
        return env_value

    # Recover from stale process env after runtime .env changes.
    load_dotenv(override=True)
    env_value = _clean_env_value(os.getenv(key))
    if env_value is not None:
        return env_value

    return default


def _uses_openrouter(endpoint: str) -> bool:
    return "openrouter.ai" in (endpoint or "").lower()


def _ai_provider_name(endpoint: str) -> str:
    return "OpenRouter" if _uses_openrouter(endpoint) else "OpenAI"


def _looks_like_openrouter_key(api_key: str | None) -> bool:
    return bool(api_key and api_key.startswith("sk-or-"))


def _looks_like_openai_key(api_key: str | None) -> bool:
    return bool(api_key and api_key.startswith("sk-") and not _looks_like_openrouter_key(api_key))


def _resolve_ai_credentials(endpoint: str) -> tuple[str, str]:
    provider_name = _ai_provider_name(endpoint)
    openai_api_key = _config_or_env("OPENAI_API_KEY")
    openrouter_api_key = _config_or_env("OPENROUTER_API_KEY")

    if _uses_openrouter(endpoint):
        api_key = openrouter_api_key or openai_api_key
        if not api_key:
            raise NutritionServiceError(
                "OpenRouter is selected, but OPENROUTER_API_KEY is missing. "
                "Set OPENROUTER_API_KEY in your .env file and reload the app."
            )
        if _looks_like_openai_key(api_key):
            raise NutritionServiceError(
                "OpenRouter endpoint is configured, but the API key looks like an OpenAI key. "
                "Use OPENROUTER_API_KEY for the OpenRouter endpoint."
            )
        return provider_name, api_key

    api_key = openai_api_key
    if not api_key:
        if _looks_like_openrouter_key(openrouter_api_key):
            raise NutritionServiceError(
                "OpenAI endpoint is configured, but only an OpenRouter key is set. "
                "Either add OPENAI_API_KEY or switch OPENAI_BASE_URL to the OpenRouter endpoint."
            )
        raise NutritionServiceError(
            "OpenAI is selected, but OPENAI_API_KEY is missing. "
            "Set OPENAI_API_KEY in your .env file and reload the app."
        )
    if _looks_like_openrouter_key(api_key):
        raise NutritionServiceError(
            "OpenAI endpoint is configured, but OPENAI_API_KEY currently contains an OpenRouter key. "
            "Add a real OpenAI key or switch OPENAI_BASE_URL to the OpenRouter endpoint."
        )

    return provider_name, api_key


def _build_ai_headers(api_key: str, endpoint: str) -> dict:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    if _uses_openrouter(endpoint):
        site_url = _config_or_env("OPENROUTER_SITE_URL")
        site_name = _config_or_env("OPENROUTER_SITE_NAME")
        if site_url:
            headers["HTTP-Referer"] = site_url
        if site_name:
            headers["X-OpenRouter-Title"] = site_name

    return headers


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


def get_ai_nutrition_explanation(food_name: str, nutrition_data: dict) -> str:
    model_name = _config_or_env("OPENAI_MODEL", DEFAULT_OPENAI_MODEL) or DEFAULT_OPENAI_MODEL
    endpoint = (
        _config_or_env("OPENAI_BASE_URL", DEFAULT_AI_CHAT_COMPLETIONS_ENDPOINT)
        or DEFAULT_AI_CHAT_COMPLETIONS_ENDPOINT
    )
    provider_name, api_key = _resolve_ai_credentials(endpoint)
    query = (food_name or "").strip()
    if not query:
        raise NutritionServiceError("Please provide a food name for AI explanation.")

    normalized_nutrition = _normalize_payload(
        nutrition_data.get("calories"),
        nutrition_data.get("protein"),
        nutrition_data.get("carbohydrates"),
        nutrition_data.get("fats"),
    )

    if not _has_any_nutrition(normalized_nutrition):
        raise NutritionServiceError(
            "No nutrition data available to explain. Analyze nutrition first."
        )

    def _display(value, unit: str = "") -> str:
        if value is None:
            return "N/A"
        rounded = round(float(value), 2)
        if unit:
            return f"{rounded} {unit}"
        return str(rounded)

    user_message = (
        "Food: "
        f"{query}\n"
        "Nutrition data:\n"
        f"- Calories: {_display(normalized_nutrition.get('calories'))}\n"
        f"- Protein: {_display(normalized_nutrition.get('protein'), 'g')}\n"
        f"- Carbohydrates: {_display(normalized_nutrition.get('carbohydrates'), 'g')}\n"
        f"- Fats: {_display(normalized_nutrition.get('fats'), 'g')}\n"
        "Give a short and easy-to-understand explanation of nutritional benefits."
    )

    payload = {
        "model": model_name,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a nutrition assistant for general education. "
                    "Write in simple language, keep it to 2-3 short sentences, and avoid medical claims."
                ),
            },
            {
                "role": "user",
                "content": user_message,
            },
        ],
        "temperature": 0.4,
        "max_tokens": 180,
    }

    try:
        response = requests.post(
            endpoint,
            headers=_build_ai_headers(api_key, endpoint),
            json=payload,
            timeout=25,
        )
    except requests.RequestException as exc:
        raise NutritionServiceError("Could not connect to the AI explanation service.") from exc

    if response.status_code in (401, 403):
        raise NutritionServiceError(
            f"{provider_name} rejected the API key or model access. "
            f"Check the selected endpoint and confirm the account can use model '{model_name}'."
        )

    if response.status_code == 429:
        raise NutritionServiceError(
            f"{provider_name} API rate limit or quota exceeded. Please try again later."
        )

    if response.status_code >= 500:
        raise NutritionServiceError(f"{provider_name} service is temporarily unavailable.")

    if response.status_code >= 400:
        try:
            error_payload = response.json()
            api_message = (error_payload.get("error") or {}).get("message")
        except ValueError:
            api_message = None

        if api_message:
            raise NutritionServiceError(f"{provider_name} request failed: {api_message}")
        raise NutritionServiceError("AI explanation request failed.")

    try:
        data = response.json()
    except ValueError as exc:
        raise NutritionServiceError("Received an invalid response from AI explanation service.") from exc

    choices = data.get("choices") or []
    message = (choices[0] or {}).get("message") if choices else {}
    content = (message or {}).get("content")

    if isinstance(content, list):
        # Handle structured message formats by concatenating text segments.
        content = " ".join(
            item.get("text", "")
            for item in content
            if isinstance(item, dict) and item.get("text")
        )

    explanation = re.sub(r"\s+", " ", (content or "")).strip()
    if not explanation:
        raise NutritionServiceError("AI explanation service returned an empty response.")

    return explanation
