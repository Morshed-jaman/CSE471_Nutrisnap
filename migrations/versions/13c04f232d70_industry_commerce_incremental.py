"""Add commerce and per-user favorites without recreating existing application tables.

Revision ID: 13c04f232d70
Revises: 000000000001
"""

from datetime import datetime

import sqlalchemy as sa
from alembic import op


revision = "13c04f232d70"
down_revision = "000000000001"
branch_labels = None
depends_on = None


FAVORITES = (
    ("favorite_vendors", "vendor_id", "vendors", None),
    ("favorite_menu_items", "menu_item_id", "menu_items", None),
    ("favorite_meals", "meal_log_id", "meal_logs", "user_id"),
)


def _rebuild_favorite_table(table_name, target_column, target_table, ownership_column):
    bind = op.get_bind()
    count = bind.execute(sa.text(f"SELECT COUNT(*) FROM {table_name}")).scalar_one()
    if count and ownership_column is None:
        raise RuntimeError(
            f"Cannot determine ownership for {count} row(s) in {table_name}. "
            "Export/reconcile those rows before rerunning this migration."
        )
    if count:
        unresolved = bind.execute(
            sa.text(
                f"SELECT COUNT(*) FROM {table_name} f "
                f"LEFT JOIN {target_table} t ON t.id = f.{target_column} "
                f"WHERE t.{ownership_column} IS NULL"
            )
        ).scalar_one()
        if unresolved:
            raise RuntimeError(
                f"Cannot determine ownership for {unresolved} row(s) in {table_name}. "
                "Fix the target ownership before rerunning this migration."
            )

    temporary = f"{table_name}_per_user_tmp"
    op.create_table(
        temporary,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(target_column, sa.Integer(), sa.ForeignKey(f"{target_table}.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("user_id", target_column, name=f"uq_{table_name}_user_target"),
    )
    if count:
        op.execute(
            sa.text(
                f"INSERT INTO {temporary} (id, user_id, {target_column}, created_at) "
                f"SELECT f.id, t.{ownership_column}, f.{target_column}, f.created_at "
                f"FROM {table_name} f JOIN {target_table} t ON t.id = f.{target_column}"
            )
        )
    op.drop_table(table_name)
    op.rename_table(temporary, table_name)
    op.create_index(f"ix_{table_name}_user_id", table_name, ["user_id"])
    op.create_index(f"ix_{table_name}_{target_column}", table_name, [target_column])


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "users" not in tables or "vendors" not in tables or "menu_items" not in tables:
        raise RuntimeError(
            "NutriSnap's existing core schema was not found. Create the core schema first; "
            "this revision is intentionally incremental and will not recreate user data."
        )

    for table_name, target_column, target_table, ownership_column in FAVORITES:
        if table_name in tables:
            columns = {column["name"] for column in inspector.get_columns(table_name)}
            if "user_id" not in columns:
                _rebuild_favorite_table(
                    table_name, target_column, target_table, ownership_column
                )

    # SQLAlchemy definitions are the single source of truth for the new tables only.
    from app.models.commerce import (
        CartItem,
        Order,
        OrderItem,
        PaymentTransaction,
        Subscription,
        SubscriptionPlan,
    )
    from app.models.favorite import FavoriteMeal, FavoriteMenuItem, FavoriteVendor

    for model in (FavoriteVendor, FavoriteMenuItem, FavoriteMeal):
        model.__table__.create(bind, checkfirst=True)
    for model in (
        SubscriptionPlan,
        Subscription,
        CartItem,
        Order,
        OrderItem,
        PaymentTransaction,
    ):
        model.__table__.create(bind, checkfirst=True)

    plans = sa.table(
        "subscription_plans",
        sa.column("code", sa.String),
        sa.column("name", sa.String),
        sa.column("description", sa.Text),
        sa.column("price", sa.Numeric),
        sa.column("duration_days", sa.Integer),
        sa.column("is_active", sa.Boolean),
        sa.column("created_at", sa.DateTime),
        sa.column("updated_at", sa.DateTime),
    )
    existing_codes = {
        row[0] for row in bind.execute(sa.text("SELECT code FROM subscription_plans"))
    }
    now = datetime.utcnow()
    defaults = (
        ("monthly", "NutriSnap Plus Monthly", 299, 30),
        ("quarterly", "NutriSnap Plus Quarterly", 799, 90),
        ("annual", "NutriSnap Plus Annual", 2499, 365),
    )
    rows = [
        {
            "code": code,
            "name": name,
            "description": "Prepaid premium nutrition access; no automatic renewal.",
            "price": price,
            "duration_days": days,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        }
        for code, name, price, days in defaults
        if code not in existing_codes
    ]
    if rows:
        op.bulk_insert(plans, rows)


def downgrade():
    raise RuntimeError(
        "Refusing to downgrade commerce because that would destroy order, subscription, "
        "payment, cart, or favorite history. Restore a verified backup for recovery."
    )
