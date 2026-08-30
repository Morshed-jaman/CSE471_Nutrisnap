import re
import unicodedata
from collections import defaultdict

from app.models import GroceryItem, PantryItem, RecipeIngredient


SUPPORTED_UNITS = {"g", "kg", "ml", "l", "piece", "cup", "tbsp", "tsp"}
BASE_FACTORS = {"g": ("g", 1), "kg": ("g", 1000), "ml": ("ml", 1), "l": ("ml", 1000)}


def normalize_name(value):
    value = unicodedata.normalize("NFKD", (value or "").strip().lower())
    value = "".join(char for char in value if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def to_base(quantity, unit):
    if unit in BASE_FACTORS:
        base, factor = BASE_FACTORS[unit]
        return quantity * factor, base
    return quantity, unit


def missing_grocery_items(plan, pantry_items):
    required = defaultdict(float)
    incomplete = set()
    for entry in plan.entries:
        filters = {"meal_log_id": entry.meal_log_id} if entry.meal_log_id else {"menu_item_id": entry.menu_item_id}
        ingredients = RecipeIngredient.query.filter_by(**filters).all()
        if not ingredients:
            incomplete.add(getattr(entry.source, "title", None) or getattr(entry.source, "name", "Meal"))
        for ingredient in ingredients:
            if ingredient.quantity is None or not ingredient.unit:
                incomplete.add(getattr(entry.source, "title", None) or getattr(entry.source, "name", "Meal"))
                continue
            amount, unit = to_base(ingredient.quantity * entry.servings, ingredient.unit)
            required[(ingredient.normalized_name, unit)] += amount
    available = defaultdict(float)
    for item in pantry_items:
        if item.status != "available" or item.quantity <= 0:
            continue
        amount, unit = to_base(item.quantity, item.unit)
        available[(item.normalized_name, unit)] += amount
    missing = []
    for (name, unit), quantity in required.items():
        shortfall = round(max(0, quantity - available[(name, unit)]), 3)
        if shortfall:
            missing.append({"name": name.title(), "normalized_name": name, "quantity": shortfall, "unit": unit})
    return missing, sorted(incomplete)


def upsert_generated_items(user_id, plan, missing):
    existing = {(item.normalized_name, item.unit): item for item in GroceryItem.query.filter_by(user_id=user_id, plan_id=plan.id, source="plan").all() if item.status != "transferred"}
    for row in missing:
        item = existing.pop((row["normalized_name"], row["unit"]), None)
        if item:
            if item.status != "purchased":
                item.quantity = row["quantity"]
                item.status = "needed"
        else:
            from app.extensions import db
            db.session.add(GroceryItem(user_id=user_id, plan_id=plan.id, source="plan", status="needed", category="other", **row))
    for item in existing.values():
        if item.status not in {"purchased", "transferred"}:
            from app.extensions import db
            db.session.delete(item)
