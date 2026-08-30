import re
from collections import Counter
from datetime import date, timedelta

from app.models import FavoriteMeal, FavoriteMenuItem, MealLog, MenuItem, PantryItem, RecipeIngredient, Vendor


MEAL_TYPES = ("breakfast", "lunch", "dinner", "snack")


def terms(value):
    return {part.strip().lower() for part in re.split(r"[,;]", value or "") if part.strip()}


def ingredients_for(candidate):
    key = "meal_log_id" if isinstance(candidate, MealLog) else "menu_item_id"
    return RecipeIngredient.query.filter_by(**{key: candidate.id}).all()


def candidate_allowed(candidate, preference):
    if isinstance(candidate, MealLog) and candidate.user_id is None:
        return False
    if isinstance(candidate, MenuItem) and (not candidate.is_available or not candidate.vendor or not candidate.vendor.is_active):
        return False
    nutrient_values = [candidate.calories, candidate.protein, candidate.carbohydrates, candidate.fats]
    if any(value is not None and float(value) < 0 for value in nutrient_values):
        return False
    ingredient_names = {item.normalized_name for item in ingredients_for(candidate)}
    if ingredient_names & terms(preference.allergens):
        return False
    diets = terms(preference.dietary_preferences)
    text = f"{getattr(candidate, 'title', '')} {getattr(candidate, 'name', '')} {getattr(candidate, 'description', '')}".lower()
    if "vegetarian" in diets and any(word in text or word in ingredient_names for word in ("chicken", "beef", "fish", "pork", "meat")):
        return False
    if "vegan" in diets and any(word in text or word in ingredient_names for word in ("chicken", "beef", "fish", "pork", "meat", "egg", "milk", "cheese")):
        return False
    return True


def rank_candidates(user_id, meal_type, preference, recent_ids=None):
    recent_ids = recent_ids or Counter()
    meals = MealLog.query.filter_by(user_id=user_id, meal_type=meal_type).all()
    vendor_items = MenuItem.query.join(Vendor).filter(MenuItem.is_available.is_(True), Vendor.is_active.is_(True)).all()
    favorite_meals = {row.meal_log_id for row in FavoriteMeal.query.filter_by(user_id=user_id)}
    favorite_items = {row.menu_item_id for row in FavoriteMenuItem.query.filter_by(user_id=user_id)}
    pantry_items = [row for row in PantryItem.query.filter_by(user_id=user_id, status="available") if row.quantity > 0]
    pantry_names = {row.normalized_name for row in pantry_items}
    expiring_names = {row.normalized_name for row in pantry_items if row.expiry_date and row.expiry_date <= date.today() + timedelta(days=3)}
    meal_target = preference.calorie_target / 4
    scored = []
    for candidate in [*meals, *vendor_items]:
        if not candidate_allowed(candidate, preference):
            continue
        calories = float(candidate.calories or 0)
        protein = float(candidate.protein or 0)
        carbs = float(candidate.carbohydrates or 0)
        fats = float(candidate.fats or 0)
        score = max(0, 35 - abs(calories - meal_target) / 20) if calories else -12
        score += min(protein / max(preference.protein_target / 4, 1), 1.5) * 18
        score += max(0, 12 - abs(carbs - preference.carbohydrate_target / 4) / 8)
        score += max(0, 8 - abs(fats - preference.fat_target / 4) / 4)
        candidate_type = "meal" if isinstance(candidate, MealLog) else "menu"
        key = (candidate_type, candidate.id)
        if candidate.id in (favorite_meals if candidate_type == "meal" else favorite_items):
            score += 15
        ingredient_names = {item.normalized_name for item in ingredients_for(candidate)}
        pantry_matches = len(ingredient_names & pantry_names)
        score += pantry_matches * 5
        score += len(ingredient_names & expiring_names) * 6
        if isinstance(candidate, MenuItem) and preference.weekly_budget is not None:
            per_meal_budget = float(preference.weekly_budget) / 28
            score += 8 if float(candidate.price) <= per_meal_budget else -min(18, (float(candidate.price) - per_meal_budget) / 10)
        score -= recent_ids[key] * 14
        reasons = []
        if protein >= preference.protein_target / 5:
            reasons.append("Good protein match")
        if pantry_matches:
            reasons.append("Uses ingredients already in your pantry")
        if ingredient_names & expiring_names:
            reasons.append("Uses an ingredient expiring soon")
        if calories and abs(calories - meal_target) <= 120:
            reasons.append("Fits your remaining calorie target")
        if candidate.id in (favorite_meals if candidate_type == "meal" else favorite_items):
            reasons.append("One of your saved meals")
        if not reasons:
            reasons.append("Supports variety in your weekly plan")
        scored.append((round(score, 3), candidate, "; ".join(reasons[:2])))
    return sorted(scored, key=lambda row: (-row[0], getattr(row[1], "id", 0)))


def generate_suggestions(user_id, week_start, preference):
    suggestions = []
    repetitions = Counter()
    for offset in range(7):
        day = week_start + timedelta(days=offset)
        for meal_type in MEAL_TYPES:
            ranked = rank_candidates(user_id, meal_type, preference, repetitions)
            if not ranked:
                continue
            _score, candidate, reason = ranked[0]
            kind = "meal" if isinstance(candidate, MealLog) else "menu"
            repetitions[(kind, candidate.id)] += 1
            suggestions.append((day, meal_type, candidate, reason))
    return suggestions


def smart_swap(entry, preference):
    original = entry.source
    original_calories = float(getattr(original, "calories", 0) or 0)
    kind = "meal" if entry.meal_log_id else "menu"
    ranked = rank_candidates(entry.plan.user_id, entry.meal_type, preference, Counter({(kind, original.id): 10}))
    close = [row for row in ranked if row[1].id != original.id or ("meal" if isinstance(row[1], MealLog) else "menu") != kind]
    if original_calories:
        close.sort(key=lambda row: (abs(float(row[1].calories or 0) - original_calories) > max(150, original_calories * .25), -row[0]))
    return close[0] if close else None
