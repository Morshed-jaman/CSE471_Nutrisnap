import requests
from flask import current_app


OPEN_METEO_FORECAST_ENDPOINT = "https://api.open-meteo.com/v1/forecast"


def _recommended_goal_for_temperature(temperature_c: float | None, fallback_goal_ml: int) -> tuple[int, str]:
    if temperature_c is None:
        return (
            fallback_goal_ml,
            f"Weather data is unavailable right now, so the standard {fallback_goal_ml} ml goal is being used.",
        )

    if temperature_c < 20:
        return 2000, "Cool weather suggests a 2000 ml hydration target for today."

    if temperature_c < 30:
        return 2500, "Warm weather suggests a 2500 ml hydration target for today."

    return 3000, "Hot weather suggests a 3000 ml hydration target for today."


def get_hydration_recommendation() -> dict:
    fallback_goal_ml = int(current_app.config.get("WATER_TRACKER_FALLBACK_GOAL_ML", 2500))
    latitude = current_app.config.get("WATER_TRACKER_LATITUDE", 23.8103)
    longitude = current_app.config.get("WATER_TRACKER_LONGITUDE", 90.4125)

    try:
        response = requests.get(
            OPEN_METEO_FORECAST_ENDPOINT,
            params={
                "latitude": latitude,
                "longitude": longitude,
                "current": "temperature_2m",
                "temperature_unit": "celsius",
                "timezone": "auto",
                "forecast_days": 1,
            },
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()

        current_weather = payload.get("current") or {}
        raw_temperature = current_weather.get("temperature_2m")
        temperature_c = float(raw_temperature) if raw_temperature is not None else None

        recommended_ml, reason_text = _recommended_goal_for_temperature(
            temperature_c,
            fallback_goal_ml,
        )
        return {
            "temperature_c": round(temperature_c, 1) if temperature_c is not None else None,
            "recommended_ml": recommended_ml,
            "reason_text": reason_text,
        }
    except (requests.RequestException, ValueError, TypeError) as exc:
        current_app.logger.warning("Open-Meteo hydration lookup failed: %s", exc)
        recommended_ml, reason_text = _recommended_goal_for_temperature(None, fallback_goal_ml)
        return {
            "temperature_c": None,
            "recommended_ml": recommended_ml,
            "reason_text": reason_text,
        }
