"""Add adaptive planner, pantry, grocery, and structured ingredients.

Revision ID: 8f2c1a7d4b90
Revises: 13c04f232d70
"""

import sqlalchemy as sa
from alembic import op


revision = "8f2c1a7d4b90"
down_revision = "13c04f232d70"
branch_labels = None
depends_on = None


TABLES = (
    "nutrition_preferences",
    "weekly_meal_plans",
    "meal_plan_entries",
    "recipe_ingredients",
    "pantry_items",
    "grocery_items",
)


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = set(inspector.get_table_names())
    required = {"users", "meal_logs", "menu_items"}
    if not required.issubset(existing):
        raise RuntimeError("NutriSnap core tables are required before planner migration.")
    from app.models.pantry import GroceryItem, PantryItem
    from app.models.planning import MealPlanEntry, NutritionPreference, RecipeIngredient, WeeklyMealPlan
    for model in (NutritionPreference, WeeklyMealPlan, MealPlanEntry, RecipeIngredient, PantryItem, GroceryItem):
        model.__table__.create(bind, checkfirst=True)


def downgrade():
    # This removes only the tables introduced by this revision. Existing application data is untouched.
    bind = op.get_bind()
    existing = set(sa.inspect(bind).get_table_names())
    for table_name in reversed(TABLES):
        if table_name in existing:
            op.drop_table(table_name)
