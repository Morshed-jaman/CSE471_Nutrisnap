from collections import Counter
from datetime import date, timedelta

from app.extensions import db
from app.models import GroceryItem, MealLog, MealPlanEntry, MenuItem, NutritionPreference, PantryItem, RecipeIngredient, User, Vendor, WeeklyMealPlan
from app.services.meal_planner_service import candidate_allowed, rank_candidates, smart_swap
from app.services.pantry_service import missing_grocery_items, normalize_name, to_base, upsert_generated_items


MONDAY = date(2026, 8, 31)


def _seed(app):
    with app.app_context():
        one = User(name="One", email="one@example.com", phone="01700000001", role="user", is_active=True); one.set_password("password123")
        two = User(name="Two", email="two@example.com", phone="01700000002", role="user", is_active=True); two.set_password("password123")
        vendor_user = User(name="Vendor", email="vendor-plan@example.com", phone="01700000003", role="vendor", vendor_status="approved", is_active=True); vendor_user.set_password("password123")
        db.session.add_all([one, two, vendor_user]); db.session.flush()
        vendor = Vendor(owner_user_id=vendor_user.id, name="Planner Kitchen", category="Healthy", is_active=True); db.session.add(vendor); db.session.flush()
        meal = MealLog(user_id=one.id, image_url="local", meal_type="breakfast", meal_date=MONDAY, title="Oat Bowl", calories=400, protein=25, carbohydrates=50, fats=10)
        second = MealLog(user_id=one.id, image_url="local", meal_type="breakfast", meal_date=MONDAY, title="Egg Plate", calories=420, protein=30, carbohydrates=30, fats=15)
        other = MealLog(user_id=two.id, image_url="local", meal_type="breakfast", meal_date=MONDAY, title="Private Meal", calories=300)
        menu = MenuItem(vendor_id=vendor.id, name="Chicken Bowl", price="250", calories=550, protein=42, carbohydrates=55, fats=16, is_available=True)
        unavailable = MenuItem(vendor_id=vendor.id, name="Old Bowl", price="100", calories=500, is_available=False)
        db.session.add_all([meal, second, other, menu, unavailable]); db.session.flush()
        db.session.add_all([RecipeIngredient(meal_log_id=meal.id, name="Rolled Oats", normalized_name="rolled oats", quantity=100, unit="g"), RecipeIngredient(menu_item_id=menu.id, name="Chicken", normalized_name="chicken", quantity=200, unit="g")])
        pref = NutritionPreference(user_id=one.id, calorie_target=2000, protein_target=120, carbohydrate_target=220, fat_target=60)
        db.session.add(pref); db.session.commit()
        return {"one": one.id, "two": two.id, "meal": meal.id, "second": second.id, "other": other.id, "menu": menu.id, "unavailable": unavailable.id}


def _login(client, email="one@example.com"):
    return client.post("/login", data={"email": email, "password": "password123"})


def test_plan_creation_week_boundaries_and_unauthorized(app, client):
    ids = _seed(app)
    assert client.get("/meal-planner").status_code == 302
    _login(client)
    response = client.post("/meal-planner/create", data={"week_start": "2026-09-02"})
    assert response.status_code == 302
    with app.app_context():
        plan = WeeklyMealPlan.query.one(); assert plan.week_start == MONDAY and plan.status == "draft"
    assert client.post(f"/meal-planner/{plan.id}/entries", data={"plan_date": "2026-09-07", "meal_type": "breakfast", "source_type": "meal", "source_id": ids["meal"], "servings": 1}).status_code == 422


def test_entry_totals_servings_activation_copy_clear_and_ownership(app, client):
    ids = _seed(app); _login(client); client.post("/meal-planner/create", data={"week_start": MONDAY.isoformat()})
    with app.app_context(): plan_id = WeeklyMealPlan.query.one().id
    assert client.post(f"/meal-planner/{plan_id}/entries", data={"plan_date": MONDAY.isoformat(), "meal_type": "breakfast", "source_type": "meal", "source_id": ids["meal"], "servings": 1.5}).status_code == 302
    with app.app_context():
        entry = MealPlanEntry.query.one(); assert entry.nutrient("calories") == 600 and entry.nutrient("protein") == 37.5
    client.post(f"/meal-planner/{plan_id}/activate")
    client.post(f"/meal-planner/{plan_id}/copy-day", data={"source_date": MONDAY.isoformat(), "target_date": (MONDAY + timedelta(days=1)).isoformat()})
    with app.app_context(): assert MealPlanEntry.query.count() == 2 and WeeklyMealPlan.query.get(plan_id).status == "active"
    client.post("/logout"); _login(client, "two@example.com")
    assert client.post(f"/meal-planner/entries/{entry.id}/remove").status_code == 404
    assert client.post(f"/meal-planner/{plan_id}/clear-day", data={"plan_date": MONDAY.isoformat()}).status_code == 404


def test_allergen_dietary_archived_ranking_variety_and_swap(app):
    ids = _seed(app)
    with app.app_context():
        pref = NutritionPreference.query.filter_by(user_id=ids["one"]).one(); menu = db.session.get(MenuItem, ids["menu"])
        pref.allergens = "chicken"; assert not candidate_allowed(menu, pref)
        pref.allergens = None; pref.dietary_preferences = "vegetarian"; assert not candidate_allowed(menu, pref)
        pref.dietary_preferences = None
        ranked = rank_candidates(ids["one"], "breakfast", pref); assert ranked and all(getattr(row[1], "is_available", True) for row in ranked)
        first_kind = "meal" if isinstance(ranked[0][1], MealLog) else "menu"
        repeated = rank_candidates(ids["one"], "breakfast", pref, Counter({(first_kind, ranked[0][1].id): 5})); assert repeated[0][1] is not ranked[0][1]
        plan = WeeklyMealPlan(user_id=ids["one"], week_start=MONDAY); db.session.add(plan); db.session.flush()
        entry = MealPlanEntry(plan_id=plan.id, plan_date=MONDAY, meal_type="breakfast", meal_log_id=ids["meal"]); db.session.add(entry); db.session.commit()
        replacement = smart_swap(entry, pref); assert replacement and replacement[1] is not entry.source and replacement[2]


def test_empty_recommendation_dataset_is_safe(app, client):
    ids = _seed(app)
    with app.app_context():
        MenuItem.query.update({"is_available": False}); MealLog.query.filter_by(user_id=ids["two"]).delete(); db.session.commit()
    _login(client, "two@example.com"); client.post("/meal-planner/create", data={"week_start": MONDAY.isoformat()})
    with app.app_context(): plan_id = WeeklyMealPlan.query.filter_by(user_id=ids["two"]).one().id
    response = client.post(f"/meal-planner/{plan_id}/generate", follow_redirects=True)
    assert response.status_code == 200 and b"Add nutrition data" in response.data


def test_pantry_crud_validation_status_boundaries_and_stale_update(app, client):
    _seed(app); _login(client)
    assert client.post("/pantry/items", data={"name":"Spinach","quantity":-1,"unit":"g","category":"produce","low_stock_threshold":0}).status_code == 422
    assert client.post("/pantry/items", data={"name":"Spinach","quantity":100,"unit":"g","category":"produce","purchase_date":"2026-09-02","expiry_date":"2026-09-01","low_stock_threshold":20}).status_code == 422
    client.post("/pantry/items", data={"name":"Spinach","quantity":20,"unit":"g","category":"produce","expiry_date":MONDAY.isoformat(),"low_stock_threshold":20})
    with app.app_context():
        item = PantryItem.query.one(); item_id=item.id; assert item.display_status(MONDAY) == "expiring soon"; assert item.display_status(MONDAY + timedelta(days=1)) == "expired"
    assert client.post(f"/pantry/items/{item_id}/update", data={"version":99,"quantity":10,"low_stock_threshold":20}).status_code == 409
    assert client.post(f"/pantry/items/{item_id}/status", data={"status":"discarded"}).status_code == 302
    with app.app_context(): assert db.session.get(PantryItem,item_id).discard_count == 1
    assert client.post(f"/pantry/items/{item_id}/delete").status_code == 302


def test_normalization_conversion_grocery_math_and_manual_preservation(app):
    ids = _seed(app)
    assert normalize_name("  Crème-Fraîche ") == "creme fraiche" and to_base(1.5,"kg") == (1500,"g")
    with app.app_context():
        plan=WeeklyMealPlan(user_id=ids["one"],week_start=MONDAY,status="active"); db.session.add(plan); db.session.flush()
        db.session.add_all([MealPlanEntry(plan_id=plan.id,plan_date=MONDAY,meal_type="breakfast",meal_log_id=ids["meal"],servings=2), PantryItem(user_id=ids["one"],name="Rolled oats",normalized_name="rolled oats",quantity=.05,unit="kg",category="grains"), GroceryItem(user_id=ids["one"],name="Soap",normalized_name="soap",quantity=1,unit="piece",source="manual")]); db.session.commit()
        missing,incomplete=missing_grocery_items(plan,PantryItem.query.all()); assert not incomplete and missing[0]["quantity"] == 150
        upsert_generated_items(ids["one"],plan,missing); db.session.commit(); upsert_generated_items(ids["one"],plan,missing); db.session.commit()
        assert GroceryItem.query.filter_by(source="manual").count()==1 and GroceryItem.query.filter_by(source="plan").count()==1


def test_purchase_transfer_is_idempotent_and_consumption_is_explicit(app, client):
    ids=_seed(app); _login(client)
    with app.app_context():
        plan=WeeklyMealPlan(user_id=ids["one"],week_start=MONDAY,status="active"); db.session.add(plan); db.session.flush()
        entry=MealPlanEntry(plan_id=plan.id,plan_date=MONDAY,meal_type="breakfast",meal_log_id=ids["meal"]); grocery=GroceryItem(user_id=ids["one"],name="Rolled Oats",normalized_name="rolled oats",quantity=500,unit="g",source="manual",status="purchased"); db.session.add_all([entry,grocery]); db.session.commit(); entry_id=entry.id; grocery_id=grocery.id
    assert client.post(f"/grocery/items/{grocery_id}/transfer").status_code==302
    assert client.post(f"/grocery/items/{grocery_id}/transfer").status_code==409
    with app.app_context(): assert PantryItem.query.one().quantity==500
    assert client.post(f"/meal-planner/entries/{entry_id}/consume").status_code==302
    assert client.post(f"/meal-planner/entries/{entry_id}/consume").status_code==409
    with app.app_context(): assert PantryItem.query.one().quantity==400


def test_pantry_ownership_isolation(app, client):
    ids=_seed(app)
    with app.app_context(): item=PantryItem(user_id=ids["one"],name="Milk",normalized_name="milk",quantity=1,unit="l"); db.session.add(item); db.session.commit(); item_id=item.id
    _login(client,"two@example.com")
    assert client.post(f"/pantry/items/{item_id}/delete").status_code==404
