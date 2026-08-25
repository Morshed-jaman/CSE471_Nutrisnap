from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from app.extensions import db


class SubscriptionPlan(db.Model):
    __tablename__ = "subscription_plans"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(40), nullable=False, unique=True, index=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    duration_days = db.Column(db.Integer, nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    subscriptions = db.relationship("Subscription", back_populates="plan", lazy="select")

    __table_args__ = (
        db.CheckConstraint("price >= 0", name="ck_subscription_plan_price_nonnegative"),
        db.CheckConstraint("duration_days > 0", name="ck_subscription_plan_duration_positive"),
    )


class Subscription(db.Model):
    __tablename__ = "subscriptions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    plan_id = db.Column(
        db.Integer, db.ForeignKey("subscription_plans.id"), nullable=False, index=True
    )
    status = db.Column(db.String(20), nullable=False, default="pending", index=True)
    starts_at = db.Column(db.DateTime, nullable=True)
    ends_at = db.Column(db.DateTime, nullable=True, index=True)
    cancelled_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    user = db.relationship("User", back_populates="paid_subscriptions")
    plan = db.relationship("SubscriptionPlan", back_populates="subscriptions")
    payments = db.relationship("PaymentTransaction", back_populates="subscription", lazy="select")

    __table_args__ = (
        db.CheckConstraint(
            "status IN ('pending', 'active', 'cancelled', 'expired')",
            name="ck_subscription_status",
        ),
    )

    @property
    def is_current(self) -> bool:
        return bool(self.status == "active" and self.ends_at and self.ends_at > datetime.utcnow())


class CartItem(db.Model):
    __tablename__ = "cart_items"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    menu_item_id = db.Column(
        db.Integer, db.ForeignKey("menu_items.id"), nullable=False, index=True
    )
    quantity = db.Column(db.Integer, nullable=False, default=1)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    user = db.relationship("User", back_populates="cart_items")
    menu_item = db.relationship("MenuItem", back_populates="cart_entries")

    __table_args__ = (
        db.UniqueConstraint("user_id", "menu_item_id", name="uq_cart_user_menu_item"),
        db.CheckConstraint("quantity > 0 AND quantity <= 20", name="ck_cart_quantity"),
    )

    @property
    def line_total(self) -> Decimal:
        return (self.menu_item.price or Decimal("0.00")) * self.quantity


class Order(db.Model):
    __tablename__ = "orders"

    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(32), nullable=False, unique=True, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    vendor_id = db.Column(db.Integer, db.ForeignKey("vendors.id"), nullable=False, index=True)
    status = db.Column(db.String(24), nullable=False, default="pending_payment", index=True)
    payment_status = db.Column(db.String(20), nullable=False, default="pending", index=True)
    subtotal = db.Column(db.Numeric(12, 2), nullable=False)
    delivery_fee = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    total_amount = db.Column(db.Numeric(12, 2), nullable=False)
    delivery_name = db.Column(db.String(120), nullable=False)
    delivery_phone = db.Column(db.String(40), nullable=False)
    delivery_address = db.Column(db.String(500), nullable=False)
    customer_note = db.Column(db.String(500), nullable=True)
    paid_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    user = db.relationship("User", back_populates="orders")
    vendor = db.relationship("Vendor", back_populates="orders")
    items = db.relationship(
        "OrderItem", back_populates="order", lazy="select", cascade="all, delete-orphan"
    )
    payments = db.relationship("PaymentTransaction", back_populates="order", lazy="select")

    __table_args__ = (
        db.CheckConstraint("subtotal >= 0", name="ck_order_subtotal_nonnegative"),
        db.CheckConstraint("delivery_fee >= 0", name="ck_order_delivery_nonnegative"),
        db.CheckConstraint("total_amount >= 0", name="ck_order_total_nonnegative"),
        db.CheckConstraint(
            "status IN ('pending_payment', 'confirmed', 'preparing', 'ready', 'delivered', "
            "'cancelled', 'payment_failed')",
            name="ck_order_status",
        ),
        db.CheckConstraint(
            "payment_status IN ('pending', 'paid', 'failed', 'cancelled', 'refunded')",
            name="ck_order_payment_status",
        ),
    )


class OrderItem(db.Model):
    __tablename__ = "order_items"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False, index=True)
    menu_item_id = db.Column(db.Integer, db.ForeignKey("menu_items.id"), nullable=False)
    item_name = db.Column(db.String(120), nullable=False)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    line_total = db.Column(db.Numeric(12, 2), nullable=False)

    order = db.relationship("Order", back_populates="items")
    menu_item = db.relationship("MenuItem", back_populates="order_items")

    __table_args__ = (
        db.CheckConstraint("unit_price >= 0", name="ck_order_item_price_nonnegative"),
        db.CheckConstraint("quantity > 0", name="ck_order_item_quantity_positive"),
        db.CheckConstraint("line_total >= 0", name="ck_order_item_total_nonnegative"),
    )


class PaymentTransaction(db.Model):
    __tablename__ = "payment_transactions"

    id = db.Column(db.Integer, primary_key=True)
    transaction_id = db.Column(db.String(64), nullable=False, unique=True, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=True, index=True)
    subscription_id = db.Column(
        db.Integer, db.ForeignKey("subscriptions.id"), nullable=True, index=True
    )
    provider = db.Column(db.String(30), nullable=False, default="sslcommerz")
    purpose = db.Column(db.String(20), nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    currency = db.Column(db.String(3), nullable=False, default="BDT")
    status = db.Column(db.String(24), nullable=False, default="initiated", index=True)
    gateway_session_key = db.Column(db.String(255), nullable=True)
    validation_id = db.Column(db.String(255), nullable=True, index=True)
    bank_transaction_id = db.Column(db.String(255), nullable=True)
    card_type = db.Column(db.String(80), nullable=True)
    risk_level = db.Column(db.String(20), nullable=True)
    failure_reason = db.Column(db.String(500), nullable=True)
    gateway_response = db.Column(db.JSON, nullable=True)
    paid_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    user = db.relationship("User", back_populates="payment_transactions")
    order = db.relationship("Order", back_populates="payments")
    subscription = db.relationship("Subscription", back_populates="payments")

    __table_args__ = (
        db.CheckConstraint("amount >= 0", name="ck_payment_amount_nonnegative"),
        db.CheckConstraint("purpose IN ('order', 'subscription')", name="ck_payment_purpose"),
        db.CheckConstraint(
            "status IN ('initiated', 'pending', 'paid', 'failed', 'cancelled', "
            "'validation_failed')",
            name="ck_payment_status",
        ),
        db.CheckConstraint(
            "(order_id IS NOT NULL AND subscription_id IS NULL) OR "
            "(order_id IS NULL AND subscription_id IS NOT NULL)",
            name="ck_payment_single_target",
        ),
    )
