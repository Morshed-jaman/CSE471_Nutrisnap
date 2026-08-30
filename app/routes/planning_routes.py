from datetime import date, datetime, timedelta

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models import GroceryItem, MealLog, MealPlanEntry, MenuItem, NutritionPreference, PantryItem, RecipeIngredient, WeeklyMealPlan
from app.services.meal_planner_service import MEAL_TYPES, generate_suggestions, smart_swap
from app.services.pantry_service import SUPPORTED_UNITS, missing_grocery_items, normalize_name, upsert_generated_items


planning_bp = Blueprint("planning", __name__)
CATEGORIES = ("produce", "protein", "grains", "dairy", "spices", "beverages", "other")


def _user_only():
    if current_user.role != "user":
        abort(403)


def _parse_date(value, field, required=False):
    if not value and not required:
        return None
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        abort(400, description=f"Invalid {field}.")


def _positive(value, field, allow_zero=False):
    try:
        number = float(value)
    except (TypeError, ValueError):
        abort(400, description=f"Invalid {field}.")
    if number < 0 or (not allow_zero and number == 0):
        abort(422, description=f"{field.title()} must be {'zero or greater' if allow_zero else 'greater than zero'}.")
    return number


def _monday(value=None):
    selected = _parse_date(value, "week", False) or date.today()
    return selected - timedelta(days=selected.weekday())


def _preference():
    preference = NutritionPreference.query.filter_by(user_id=current_user.id).first()
    if not preference:
        preference = NutritionPreference(user_id=current_user.id)
        db.session.add(preference)
        db.session.flush()
    return preference


def _plan(plan_id):
    plan = WeeklyMealPlan.query.filter_by(id=plan_id, user_id=current_user.id).first()
    if not plan:
        abort(404)
    return plan


def _entry(entry_id):
    entry = MealPlanEntry.query.join(WeeklyMealPlan).filter(MealPlanEntry.id == entry_id, WeeklyMealPlan.user_id == current_user.id).first()
    if not entry:
        abort(404)
    return entry


def _pantry(item_id):
    item = PantryItem.query.filter_by(id=item_id, user_id=current_user.id).first()
    if not item:
        abort(404)
    return item


def _grocery(item_id):
    item = GroceryItem.query.filter_by(id=item_id, user_id=current_user.id).first()
    if not item:
        abort(404)
    return item


@planning_bp.get("/meal-planner")
@login_required
def planner():
    _user_only()
    week_start = _monday(request.args.get("week"))
    plan = WeeklyMealPlan.query.filter_by(user_id=current_user.id, week_start=week_start).first()
    preference = _preference()
    db.session.commit()
    meals = MealLog.query.filter_by(user_id=current_user.id).order_by(MealLog.meal_date.desc()).all()
    menu_items = MenuItem.query.filter_by(is_available=True).order_by(MenuItem.name).all()
    days = []
    for offset in range(7):
        plan_date = week_start + timedelta(days=offset)
        entries = [entry for entry in (plan.entries if plan else []) if entry.plan_date == plan_date]
        totals = {nutrient: round(sum(entry.nutrient(nutrient) for entry in entries), 1) for nutrient in ("calories", "protein", "carbohydrates", "fats")}
        days.append({"date": plan_date, "entries": entries, "totals": totals})
    weekly = {nutrient: round(sum(day["totals"][nutrient] for day in days), 1) for nutrient in ("calories", "protein", "carbohydrates", "fats")}
    return render_template("planning/planner.html", plan=plan, week_start=week_start, week_end=week_start + timedelta(days=6), previous_week=week_start - timedelta(days=7), next_week=week_start + timedelta(days=7), days=days, weekly=weekly, meals=meals, menu_items=menu_items, preference=preference, meal_types=MEAL_TYPES)


@planning_bp.post("/meal-planner/create")
@login_required
def create_plan():
    _user_only()
    week_start = _monday(request.form.get("week_start"))
    plan = WeeklyMealPlan.query.filter_by(user_id=current_user.id, week_start=week_start).first()
    if not plan:
        plan = WeeklyMealPlan(user_id=current_user.id, week_start=week_start)
        db.session.add(plan)
        db.session.commit()
        flash("Draft weekly plan created.", "success")
    return redirect(url_for("planning.planner", week=week_start.isoformat()))


@planning_bp.post("/meal-planner/<int:plan_id>/entries")
@login_required
def add_entry(plan_id):
    _user_only(); plan = _plan(plan_id)
    plan_date = _parse_date(request.form.get("plan_date"), "plan date", True)
    if not plan.week_start <= plan_date <= plan.week_start + timedelta(days=6): abort(422)
    meal_type = request.form.get("meal_type", "").lower()
    if meal_type not in MEAL_TYPES: abort(422)
    source_type, source_id = request.form.get("source_type"), request.form.get("source_id", type=int)
    meal = MealLog.query.filter_by(id=source_id, user_id=current_user.id).first() if source_type == "meal" else None
    menu = MenuItem.query.filter_by(id=source_id, is_available=True).first() if source_type == "menu" else None
    if not meal and not menu: abort(404)
    servings = _positive(request.form.get("servings", 1), "servings")
    db.session.add(MealPlanEntry(plan_id=plan.id, plan_date=plan_date, meal_type=meal_type, meal_log_id=meal.id if meal else None, menu_item_id=menu.id if menu else None, servings=servings))
    db.session.commit(); flash("Meal added to your plan.", "success")
    return redirect(url_for("planning.planner", week=plan.week_start.isoformat()))


@planning_bp.post("/meal-planner/entries/<int:entry_id>/update")
@login_required
def update_entry(entry_id):
    _user_only(); entry = _entry(entry_id)
    entry.servings = _positive(request.form.get("servings"), "servings")
    db.session.commit(); flash("Serving quantity updated.", "success")
    return redirect(url_for("planning.planner", week=entry.plan.week_start.isoformat()))


@planning_bp.post("/meal-planner/entries/<int:entry_id>/remove")
@login_required
def remove_entry(entry_id):
    _user_only(); entry = _entry(entry_id); week = entry.plan.week_start
    db.session.delete(entry); db.session.commit(); flash("Plan entry removed.", "success")
    return redirect(url_for("planning.planner", week=week.isoformat()))


@planning_bp.post("/meal-planner/entries/<int:entry_id>/swap")
@login_required
def swap_entry(entry_id):
    _user_only(); entry = _entry(entry_id); alternative = smart_swap(entry, _preference())
    if not alternative:
        flash("No safe similar alternative is currently available.", "warning")
    else:
        _score, candidate, reason = alternative
        entry.meal_log_id = candidate.id if isinstance(candidate, MealLog) else None
        entry.menu_item_id = candidate.id if isinstance(candidate, MenuItem) else None
        entry.recommendation_reason = reason
        db.session.commit(); flash(f"Meal replaced. {reason}.", "success")
    return redirect(url_for("planning.planner", week=entry.plan.week_start.isoformat()))


@planning_bp.post("/meal-planner/<int:plan_id>/copy-day")
@login_required
def copy_day(plan_id):
    _user_only(); plan = _plan(plan_id)
    source = _parse_date(request.form.get("source_date"), "source date", True); target = _parse_date(request.form.get("target_date"), "target date", True)
    if not all(plan.week_start <= value <= plan.week_start + timedelta(days=6) for value in (source, target)): abort(422)
    MealPlanEntry.query.filter_by(plan_id=plan.id, plan_date=target).delete()
    for row in MealPlanEntry.query.filter_by(plan_id=plan.id, plan_date=source).all():
        db.session.add(MealPlanEntry(plan_id=plan.id, plan_date=target, meal_type=row.meal_type, meal_log_id=row.meal_log_id, menu_item_id=row.menu_item_id, servings=row.servings, recommendation_reason=row.recommendation_reason))
    db.session.commit(); flash("Day copied.", "success")
    return redirect(url_for("planning.planner", week=plan.week_start.isoformat()))


@planning_bp.post("/meal-planner/<int:plan_id>/clear-day")
@login_required
def clear_day(plan_id):
    _user_only(); plan = _plan(plan_id); target = _parse_date(request.form.get("plan_date"), "plan date", True)
    if not plan.week_start <= target <= plan.week_start + timedelta(days=6): abort(422)
    MealPlanEntry.query.filter_by(plan_id=plan.id, plan_date=target).delete(); db.session.commit(); flash("Day cleared.", "success")
    return redirect(url_for("planning.planner", week=plan.week_start.isoformat()))


@planning_bp.post("/meal-planner/<int:plan_id>/activate")
@login_required
def activate_plan(plan_id):
    _user_only(); plan = _plan(plan_id)
    WeeklyMealPlan.query.filter_by(user_id=current_user.id, status="active").update({"status": "draft"})
    plan.status = "active"; db.session.commit(); flash("Weekly plan activated.", "success")
    return redirect(url_for("planning.planner", week=plan.week_start.isoformat()))


@planning_bp.post("/meal-planner/<int:plan_id>/generate")
@login_required
def generate_plan(plan_id):
    _user_only(); plan = _plan(plan_id); suggestions = generate_suggestions(current_user.id, plan.week_start, _preference())
    if not suggestions:
        flash("Add nutrition data to personal meals or vendor items before generating a plan.", "warning")
    else:
        MealPlanEntry.query.filter_by(plan_id=plan.id).delete()
        for day, meal_type, candidate, reason in suggestions:
            db.session.add(MealPlanEntry(plan_id=plan.id, plan_date=day, meal_type=meal_type, meal_log_id=candidate.id if isinstance(candidate, MealLog) else None, menu_item_id=candidate.id if isinstance(candidate, MenuItem) else None, recommendation_reason=reason))
        db.session.commit(); flash("Suggested plan generated. Review every selection before activating it.", "success")
    return redirect(url_for("planning.planner", week=plan.week_start.isoformat()))


@planning_bp.post("/meal-planner/preferences")
@login_required
def update_preferences():
    _user_only(); preference = _preference()
    preference.calorie_target = int(_positive(request.form.get("calorie_target"), "calorie target"))
    preference.protein_target = _positive(request.form.get("protein_target"), "protein target")
    preference.carbohydrate_target = _positive(request.form.get("carbohydrate_target"), "carbohydrate target")
    preference.fat_target = _positive(request.form.get("fat_target"), "fat target")
    preference.weekly_budget = _positive(request.form.get("weekly_budget"), "weekly budget", True) if request.form.get("weekly_budget") else None
    preference.dietary_preferences = (request.form.get("dietary_preferences") or "").strip()[:500] or None
    preference.allergens = (request.form.get("allergens") or "").strip()[:500] or None
    db.session.commit(); flash("Planning preferences updated.", "success")
    return redirect(url_for("planning.planner", week=_monday(request.form.get("week_start")).isoformat()))


@planning_bp.post("/recipe-ingredients")
@login_required
def add_recipe_ingredient():
    source_type = request.form.get("source_type"); source_id = request.form.get("source_id", type=int)
    meal = MealLog.query.filter_by(id=source_id, user_id=current_user.id).first() if source_type == "meal" else None
    menu = MenuItem.query.filter_by(id=source_id).first() if source_type == "menu" else None
    if menu and (current_user.role != "vendor" or not menu.vendor or menu.vendor.owner_user_id != current_user.id): menu = None
    if not meal and not menu: abort(404)
    name = (request.form.get("name") or "").strip(); unit = request.form.get("unit"); quantity_raw = request.form.get("quantity")
    if not name or len(name) > 120: abort(422)
    if (quantity_raw and unit not in SUPPORTED_UNITS) or (unit and not quantity_raw): abort(422)
    quantity = _positive(quantity_raw, "quantity") if quantity_raw else None
    db.session.add(RecipeIngredient(meal_log_id=meal.id if meal else None, menu_item_id=menu.id if menu else None, name=name, normalized_name=normalize_name(name), quantity=quantity, unit=unit or None))
    db.session.commit(); flash("Structured ingredient added.", "success")
    return redirect(request.referrer or url_for("planning.planner"))


@planning_bp.post("/meal-planner/entries/<int:entry_id>/consume")
@login_required
def consume_entry(entry_id):
    _user_only(); entry = _entry(entry_id)
    if entry.consumed_at: abort(409)
    filters = {"meal_log_id": entry.meal_log_id} if entry.meal_log_id else {"menu_item_id": entry.menu_item_id}
    for ingredient in RecipeIngredient.query.filter_by(**filters):
        if ingredient.quantity is None or not ingredient.unit: continue
        pantry = PantryItem.query.filter_by(user_id=current_user.id, normalized_name=ingredient.normalized_name, unit=ingredient.unit, status="available").first()
        if pantry: pantry.quantity = max(0, pantry.quantity - ingredient.quantity * entry.servings); pantry.version += 1
    entry.consumed_at = datetime.utcnow(); db.session.commit(); flash("Meal preparation confirmed; matching pantry stock was updated.", "success")
    return redirect(url_for("planning.planner", week=entry.plan.week_start.isoformat()))


@planning_bp.get("/pantry")
@login_required
def pantry():
    _user_only(); query = PantryItem.query.filter_by(user_id=current_user.id)
    search = normalize_name(request.args.get("q")); status = request.args.get("status")
    items = query.order_by(PantryItem.expiry_date.asc(), PantryItem.name.asc()).all()
    if search: items = [item for item in items if search in item.normalized_name]
    if status: items = [item for item in items if item.display_status() == status]
    groceries = GroceryItem.query.filter_by(user_id=current_user.id).order_by(GroceryItem.status, GroceryItem.name).all()
    grocery_status, grocery_category = request.args.get("grocery_status"), request.args.get("grocery_category")
    if grocery_status: groceries = [item for item in groceries if item.status == grocery_status]
    if grocery_category: groceries = [item for item in groceries if item.category == grocery_category]
    alerts = [item for item in items if item.display_status() in {"expiring soon", "expired", "low stock"} or item.discard_count >= 2]
    return render_template("planning/pantry.html", items=items, groceries=groceries, alerts=alerts, units=sorted(SUPPORTED_UNITS), categories=CATEGORIES)


@planning_bp.post("/pantry/items")
@login_required
def add_pantry_item():
    _user_only(); name = (request.form.get("name") or "").strip(); unit = request.form.get("unit"); category = request.form.get("category", "other")
    if not name or len(name) > 120 or unit not in SUPPORTED_UNITS or category not in CATEGORIES: abort(422)
    purchase = _parse_date(request.form.get("purchase_date"), "purchase date"); expiry = _parse_date(request.form.get("expiry_date"), "expiry date")
    if purchase and expiry and expiry < purchase: abort(422)
    item = PantryItem(user_id=current_user.id, name=name, normalized_name=normalize_name(name), quantity=_positive(request.form.get("quantity"), "quantity", True), unit=unit, category=category, purchase_date=purchase, expiry_date=expiry, low_stock_threshold=_positive(request.form.get("low_stock_threshold", 0), "threshold", True), storage_location=(request.form.get("storage_location") or "").strip()[:50] or None)
    db.session.add(item); db.session.commit(); flash("Pantry item added.", "success")
    return redirect(url_for("planning.pantry"))


@planning_bp.post("/pantry/items/<int:item_id>/update")
@login_required
def update_pantry_item(item_id):
    _user_only(); item = _pantry(item_id)
    expected = request.form.get("version", type=int)
    if expected != item.version: abort(409)
    name = (request.form.get("name") or item.name).strip(); unit = request.form.get("unit", item.unit); category = request.form.get("category", item.category)
    if not name or unit not in SUPPORTED_UNITS or category not in CATEGORIES: abort(422)
    item.name = name[:120]; item.normalized_name = normalize_name(name); item.unit = unit; item.category = category
    item.quantity = _positive(request.form.get("quantity"), "quantity", True); item.low_stock_threshold = _positive(request.form.get("low_stock_threshold"), "threshold", True)
    expiry = _parse_date(request.form.get("expiry_date"), "expiry date")
    if item.purchase_date and expiry and expiry < item.purchase_date: abort(422)
    item.expiry_date = expiry; item.version += 1; db.session.commit(); flash("Pantry item updated.", "success")
    return redirect(url_for("planning.pantry"))


@planning_bp.post("/pantry/items/<int:item_id>/status")
@login_required
def pantry_status(item_id):
    _user_only(); item = _pantry(item_id); status = request.form.get("status")
    if status not in {"available", "consumed", "discarded"}: abort(422)
    if status == "discarded" and item.status != "discarded": item.discard_count += 1
    item.status = status; item.version += 1; db.session.commit(); flash(f"Item marked {status}.", "success")
    return redirect(url_for("planning.pantry"))


@planning_bp.post("/pantry/items/<int:item_id>/delete")
@login_required
def delete_pantry_item(item_id):
    _user_only(); db.session.delete(_pantry(item_id)); db.session.commit(); flash("Pantry item removed.", "success")
    return redirect(url_for("planning.pantry"))


@planning_bp.post("/grocery/generate")
@login_required
def generate_grocery():
    _user_only(); plan = WeeklyMealPlan.query.filter_by(user_id=current_user.id, status="active").first()
    if not plan: abort(409, description="Activate a weekly plan first.")
    missing, incomplete = missing_grocery_items(plan, PantryItem.query.filter_by(user_id=current_user.id).all())
    upsert_generated_items(current_user.id, plan, missing); db.session.commit()
    flash("Grocery list generated." + (f" Recipe quantities missing for: {', '.join(incomplete)}." if incomplete else ""), "warning" if incomplete else "success")
    return redirect(url_for("planning.pantry"))


@planning_bp.post("/grocery/items")
@login_required
def add_grocery_item():
    _user_only(); name = (request.form.get("name") or "").strip(); unit = request.form.get("unit"); category = request.form.get("category", "other")
    if not name or unit not in SUPPORTED_UNITS or category not in CATEGORIES: abort(422)
    db.session.add(GroceryItem(user_id=current_user.id, name=name, normalized_name=normalize_name(name), quantity=_positive(request.form.get("quantity"), "quantity"), unit=unit, category=category, source="manual"))
    db.session.commit(); flash("Manual grocery item added.", "success"); return redirect(url_for("planning.pantry"))


@planning_bp.post("/grocery/items/<int:item_id>/update")
@login_required
def update_grocery_item(item_id):
    _user_only(); item = _grocery(item_id)
    if item.status == "transferred": abort(409)
    status = request.form.get("status", "needed")
    if status not in {"needed", "checked", "purchased"}: abort(422)
    item.quantity = _positive(request.form.get("quantity", item.quantity), "quantity"); item.status = status; db.session.commit(); flash("Grocery item updated.", "success"); return redirect(url_for("planning.pantry"))


@planning_bp.post("/grocery/items/<int:item_id>/transfer")
@login_required
def transfer_grocery_item(item_id):
    _user_only(); item = _grocery(item_id)
    if item.status == "transferred": abort(409)
    if item.status != "purchased": abort(422)
    pantry = PantryItem.query.filter_by(user_id=current_user.id, normalized_name=item.normalized_name, unit=item.unit, status="available").first()
    if pantry: pantry.quantity += item.quantity; pantry.version += 1
    else: db.session.add(PantryItem(user_id=current_user.id, name=item.name, normalized_name=item.normalized_name, quantity=item.quantity, unit=item.unit, category=item.category))
    item.status = "transferred"; db.session.commit(); flash("Purchased item moved into your pantry.", "success"); return redirect(url_for("planning.pantry"))


@planning_bp.post("/grocery/clear-purchased")
@login_required
def clear_purchased():
    _user_only(); GroceryItem.query.filter_by(user_id=current_user.id, status="purchased").delete(); db.session.commit(); flash("Purchased entries cleared.", "success"); return redirect(url_for("planning.pantry"))
