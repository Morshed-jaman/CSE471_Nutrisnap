"""Non-destructive baseline for the legacy NutriSnap schema.

Revision ID: 000000000001
Revises:
"""

from alembic import op


revision = "000000000001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """Create missing legacy tables while leaving every existing table and row intact."""
    bind = op.get_bind()
    from app.models import (
        AdviceQuestion,
        MealLog,
        MenuItem,
        Review,
        User,
        Vendor,
        VendorProfile,
        VendorSubscription,
        WaterIntake,
    )

    for model in (
        User,
        Vendor,
        VendorProfile,
        MenuItem,
        MealLog,
        Review,
        VendorSubscription,
        AdviceQuestion,
        WaterIntake,
    ):
        model.__table__.create(bind, checkfirst=True)


def downgrade():
    raise RuntimeError(
        "Refusing to remove the legacy NutriSnap baseline because it would destroy user data."
    )
