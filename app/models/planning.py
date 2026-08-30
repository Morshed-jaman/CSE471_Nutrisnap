from datetime import date, datetime

from app.extensions import db


class NutritionPreference(db.Model):
    __tablename__ = "nutrition_preferences"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, unique=True, index=True)
    calorie_target = db.Column(db.Integer, nullable=False, default=2000)
    protein_target = db.Column(db.Float, nullable=False, default=120)
    carbohydrate_target = db.Column(db.Float, nullable=False, default=240)
    fat_target = db.Column(db.Float, nullable=False, default=65)
    dietary_preferences = db.Column(db.Text, nullable=True)
    allergens = db.Column(db.Text, nullable=True)
    weekly_budget = db.Column(db.Numeric(10, 2), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class WeeklyMealPlan(db.Model):
    __tablename__ = "weekly_meal_plans"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    week_start = db.Column(db.Date, nullable=False, index=True)
    status = db.Column(db.String(16), nullable=False, default="draft", index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    entries = db.relationship("MealPlanEntry", back_populates="plan", cascade="all, delete-orphan", order_by="MealPlanEntry.plan_date, MealPlanEntry.meal_type, MealPlanEntry.id")

    __table_args__ = (
        db.UniqueConstraint("user_id", "week_start", name="uq_weekly_plan_user_week"),
        db.CheckConstraint("status IN ('draft','active')", name="ck_weekly_plan_status"),
    )

class MealPlanEntry(db.Model):
    __tablename__ = "meal_plan_entries"

    id = db.Column(db.Integer, primary_key=True)
    plan_id = db.Column(db.Integer, db.ForeignKey("weekly_meal_plans.id"), nullable=False, index=True)
    plan_date = db.Column(db.Date, nullable=False, index=True)
    meal_type = db.Column(db.String(16), nullable=False)
    meal_log_id = db.Column(db.Integer, db.ForeignKey("meal_logs.id"), nullable=True, index=True)
    menu_item_id = db.Column(db.Integer, db.ForeignKey("menu_items.id"), nullable=True, index=True)
    servings = db.Column(db.Float, nullable=False, default=1)
    recommendation_reason = db.Column(db.String(255), nullable=True)
    consumed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    plan = db.relationship("WeeklyMealPlan", back_populates="entries")
    meal_log = db.relationship("MealLog")
    menu_item = db.relationship("MenuItem")

    __table_args__ = (
        db.CheckConstraint("meal_type IN ('breakfast','lunch','dinner','snack')", name="ck_plan_entry_meal_type"),
        db.CheckConstraint("servings > 0", name="ck_plan_entry_servings"),
        db.CheckConstraint("(meal_log_id IS NOT NULL AND menu_item_id IS NULL) OR (meal_log_id IS NULL AND menu_item_id IS NOT NULL)", name="ck_plan_entry_one_source"),
    )

    @property
    def source(self):
        return self.meal_log or self.menu_item

    def nutrient(self, name):
        value = getattr(self.source, name, None) if self.source else None
        return round(float(value or 0) * self.servings, 2)


class RecipeIngredient(db.Model):
    __tablename__ = "recipe_ingredients"

    id = db.Column(db.Integer, primary_key=True)
    meal_log_id = db.Column(db.Integer, db.ForeignKey("meal_logs.id"), nullable=True, index=True)
    menu_item_id = db.Column(db.Integer, db.ForeignKey("menu_items.id"), nullable=True, index=True)
    name = db.Column(db.String(120), nullable=False)
    normalized_name = db.Column(db.String(120), nullable=False, index=True)
    quantity = db.Column(db.Float, nullable=True)
    unit = db.Column(db.String(20), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        db.CheckConstraint("(meal_log_id IS NOT NULL AND menu_item_id IS NULL) OR (meal_log_id IS NULL AND menu_item_id IS NOT NULL)", name="ck_recipe_ingredient_one_source"),
        db.CheckConstraint("quantity IS NULL OR quantity > 0", name="ck_recipe_ingredient_quantity"),
    )
