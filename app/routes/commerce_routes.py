from __future__ import annotations

import secrets
from datetime import datetime, timedelta
from decimal import Decimal
from urllib.parse import urljoin

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required
from sqlalchemy.orm import joinedload

from app.extensions import csrf, db
from app.models import (
    CartItem,
    MenuItem,
    Order,
    OrderItem,
    PaymentTransaction,
    Subscription,
    SubscriptionPlan,
    Vendor,
)
from app.services.auth_service import admin_required, approved_vendor_required, role_required
from app.services.sslcommerz_service import SSLCommerzError, initiate_payment, validate_payment

commerce_bp = Blueprint("commerce", __name__)
MAX_CART_QUANTITY = 20
ORDER_STATUS_TRANSITIONS = {
    "confirmed": {"preparing", "cancelled"},
    "preparing": {"ready", "cancelled"},
    "ready": {"delivered"},
    "delivered": set(),
    "cancelled": set(),
}

SAFE_GATEWAY_AUDIT_FIELDS = {
    "status",
    "tran_id",
    "amount",
    "currency",
    "val_id",
    "bank_tran_id",
    "card_type",
    "risk_level",
    "risk_title",
    "sessionkey",
    "failedreason",
}


def _safe_gateway_audit(payload) -> dict:
    """Keep the payment audit useful without persisting customer/card details or credentials."""
    if not isinstance(payload, dict):
        return {}
    return {
        key: str(payload[key])[:500]
        for key in SAFE_GATEWAY_AUDIT_FIELDS
        if key in payload and payload[key] not in (None, "")
    }


def _money(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.01"))


def _new_reference(prefix: str) -> str:
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    return f"{prefix}-{timestamp}-{secrets.token_hex(4).upper()}"


def _public_url(endpoint: str) -> str:
    path = url_for(endpoint)
    configured_base = (current_app.config.get("PUBLIC_BASE_URL") or "").strip()
    if configured_base:
        return urljoin(f"{configured_base.rstrip('/')}/", path.lstrip("/"))
    return url_for(endpoint, _external=True, _scheme="https")


def _cart_items():
    return (
        CartItem.query.options(joinedload(CartItem.menu_item).joinedload(MenuItem.vendor))
        .filter_by(user_id=current_user.id)
        .order_by(CartItem.created_at.asc())
        .all()
    )


def _cart_summary(items):
    subtotal = sum((_money(item.line_total) for item in items), Decimal("0.00"))
    delivery_fee = _money(current_app.config.get("ORDER_DELIVERY_FEE_BDT", 60)) if items else Decimal("0.00")
    return subtotal, delivery_fee, subtotal + delivery_fee


def _single_vendor(items):
    vendor_ids = {item.menu_item.vendor_id for item in items if item.menu_item}
    return next(iter(vendor_ids)) if len(vendor_ids) == 1 else None


def _safe_local_next(default_url: str) -> str:
    next_url = (request.form.get("next") or "").strip()
    if next_url.startswith("/") and not next_url.startswith("//"):
        return next_url
    return default_url


def _start_gateway_session(payment: PaymentTransaction, *, customer_address: str, item_count: int):
    if payment.purpose == "order":
        product_name = f"NutriSnap order {payment.order.order_number}"
        product_category = "Food"
        product_profile = "physical-goods"
    else:
        product_name = f"NutriSnap {payment.subscription.plan.name}"
        product_category = "Nutrition subscription"
        product_profile = "non-physical-goods"

    gateway_session = initiate_payment(
        transaction_id=payment.transaction_id,
        amount=_money(payment.amount),
        customer_name=payment.user.name,
        customer_email=payment.user.email,
        customer_phone=payment.user.phone,
        customer_address=customer_address,
        product_name=product_name,
        product_category=product_category,
        product_profile=product_profile,
        success_url=_public_url("commerce.payment_success"),
        fail_url=_public_url("commerce.payment_fail"),
        cancel_url=_public_url("commerce.payment_cancel"),
        ipn_url=_public_url("commerce.payment_ipn"),
        item_count=item_count,
    )
    payment.status = "pending"
    payment.gateway_session_key = gateway_session.session_key
    payment.gateway_response = _safe_gateway_audit(gateway_session.response)
    db.session.commit()
    return redirect(gateway_session.gateway_url)


@commerce_bp.route("/subscriptions")
@login_required
@role_required("user")
def subscription_plans():
    plans = SubscriptionPlan.query.filter_by(is_active=True).order_by(SubscriptionPlan.price).all()
    active_subscription = (
        Subscription.query.filter_by(user_id=current_user.id, status="active")
        .filter(Subscription.ends_at > datetime.utcnow())
        .order_by(Subscription.ends_at.desc())
        .first()
    )
    return render_template(
        "commerce/subscription_plans.html",
        plans=plans,
        active_subscription=active_subscription,
    )


@commerce_bp.route("/subscriptions/<int:plan_id>/checkout", methods=["POST"])
@login_required
@role_required("user")
def subscription_checkout(plan_id: int):
    plan = SubscriptionPlan.query.filter_by(id=plan_id, is_active=True).first_or_404()
    subscription = Subscription(user_id=current_user.id, plan_id=plan.id, status="pending")
    db.session.add(subscription)
    db.session.flush()

    payment = PaymentTransaction(
        transaction_id=_new_reference("NS-SUB"),
        user_id=current_user.id,
        subscription_id=subscription.id,
        purpose="subscription",
        amount=_money(plan.price),
        currency="BDT",
        status="initiated",
    )
    db.session.add(payment)
    db.session.commit()

    try:
        return _start_gateway_session(payment, customer_address="Digital subscription", item_count=1)
    except SSLCommerzError as exc:
        current_app.logger.warning(
            "Payment initiation failed route=%s transaction=%s category=gateway",
            request.path, payment.transaction_id,
        )
        payment.status = "failed"
        payment.failure_reason = str(exc)
        subscription.status = "cancelled"
        db.session.commit()
        flash(str(exc), "danger")
        return redirect(url_for("commerce.subscription_plans"))


@commerce_bp.route("/cart")
@login_required
@role_required("user")
def cart():
    items = _cart_items()
    subtotal, delivery_fee, total = _cart_summary(items)
    return render_template(
        "commerce/cart.html",
        cart_items=items,
        subtotal=subtotal,
        delivery_fee=delivery_fee,
        total=total,
        single_vendor=_single_vendor(items) is not None,
    )


@commerce_bp.route("/cart/items/<int:item_id>", methods=["POST"])
@login_required
@role_required("user")
def add_to_cart(item_id: int):
    menu_item = (
        MenuItem.query.join(Vendor)
        .filter(MenuItem.id == item_id, MenuItem.is_available.is_(True), Vendor.is_active.is_(True))
        .first_or_404()
    )
    try:
        quantity = int(request.form.get("quantity", "1"))
    except ValueError:
        quantity = 0
    if not 1 <= quantity <= MAX_CART_QUANTITY:
        flash(f"Quantity must be between 1 and {MAX_CART_QUANTITY}.", "danger")
        return redirect(request.referrer or url_for("vendor.menu_item_detail", item_id=item_id))

    existing_items = _cart_items()
    existing_vendor = _single_vendor(existing_items)
    if existing_items and existing_vendor != menu_item.vendor_id:
        flash("A cart can contain items from one vendor only. Clear the cart to switch vendors.", "warning")
        return redirect(url_for("commerce.cart"))

    cart_item = CartItem.query.filter_by(user_id=current_user.id, menu_item_id=item_id).first()
    if cart_item:
        cart_item.quantity = min(MAX_CART_QUANTITY, cart_item.quantity + quantity)
    else:
        db.session.add(CartItem(user_id=current_user.id, menu_item_id=item_id, quantity=quantity))
    db.session.commit()
    flash(f"{menu_item.name} added to your cart.", "success")
    return redirect(_safe_local_next(url_for("commerce.cart")))


@commerce_bp.route("/cart/items/<int:cart_item_id>/update", methods=["POST"])
@login_required
@role_required("user")
def update_cart_item(cart_item_id: int):
    cart_item = CartItem.query.filter_by(id=cart_item_id, user_id=current_user.id).first_or_404()
    try:
        quantity = int(request.form.get("quantity", "1"))
    except ValueError:
        quantity = 0
    if not 1 <= quantity <= MAX_CART_QUANTITY:
        flash(f"Quantity must be between 1 and {MAX_CART_QUANTITY}.", "danger")
    else:
        cart_item.quantity = quantity
        db.session.commit()
        flash("Cart updated.", "success")
    return redirect(url_for("commerce.cart"))


@commerce_bp.route("/cart/items/<int:cart_item_id>/remove", methods=["POST"])
@login_required
@role_required("user")
def remove_cart_item(cart_item_id: int):
    cart_item = CartItem.query.filter_by(id=cart_item_id, user_id=current_user.id).first_or_404()
    db.session.delete(cart_item)
    db.session.commit()
    flash("Item removed from your cart.", "success")
    return redirect(url_for("commerce.cart"))


@commerce_bp.route("/checkout", methods=["GET", "POST"])
@login_required
@role_required("user")
def order_checkout():
    items = _cart_items()
    if not items or _single_vendor(items) is None:
        flash("Your cart is empty or contains items from multiple vendors.", "warning")
        return redirect(url_for("commerce.cart"))
    if any(not item.menu_item.is_available or not item.menu_item.vendor.is_active for item in items):
        flash("One or more items are no longer available. Please update your cart.", "warning")
        return redirect(url_for("commerce.cart"))

    subtotal, delivery_fee, total = _cart_summary(items)
    if request.method == "GET":
        return render_template(
            "commerce/checkout.html",
            cart_items=items,
            subtotal=subtotal,
            delivery_fee=delivery_fee,
            total=total,
        )

    delivery_name = (request.form.get("delivery_name") or "").strip()
    delivery_phone = (request.form.get("delivery_phone") or "").strip()
    delivery_address = (request.form.get("delivery_address") or "").strip()
    customer_note = (request.form.get("customer_note") or "").strip() or None
    if not delivery_name or not delivery_phone or len(delivery_address) < 10:
        flash("Name, phone, and a complete delivery address are required.", "danger")
        return render_template(
            "commerce/checkout.html",
            cart_items=items,
            subtotal=subtotal,
            delivery_fee=delivery_fee,
            total=total,
            form=request.form,
        ), 400

    order = Order(
        order_number=_new_reference("NS-ORD"),
        user_id=current_user.id,
        vendor_id=_single_vendor(items),
        status="pending_payment",
        payment_status="pending",
        subtotal=subtotal,
        delivery_fee=delivery_fee,
        total_amount=total,
        delivery_name=delivery_name[:120],
        delivery_phone=delivery_phone[:40],
        delivery_address=delivery_address[:500],
        customer_note=customer_note[:500] if customer_note else None,
    )
    db.session.add(order)
    db.session.flush()
    for cart_item in items:
        unit_price = _money(cart_item.menu_item.price)
        db.session.add(
            OrderItem(
                order_id=order.id,
                menu_item_id=cart_item.menu_item_id,
                item_name=cart_item.menu_item.name,
                unit_price=unit_price,
                quantity=cart_item.quantity,
                line_total=unit_price * cart_item.quantity,
            )
        )

    payment = PaymentTransaction(
        transaction_id=_new_reference("NS-PAY"),
        user_id=current_user.id,
        order_id=order.id,
        purpose="order",
        amount=total,
        currency="BDT",
        status="initiated",
    )
    db.session.add(payment)
    db.session.commit()

    try:
        response = _start_gateway_session(
            payment,
            customer_address=delivery_address,
            item_count=sum(item.quantity for item in items),
        )
        CartItem.query.filter_by(user_id=current_user.id).delete()
        db.session.commit()
        return response
    except SSLCommerzError as exc:
        current_app.logger.warning(
            "Payment initiation failed route=%s transaction=%s category=gateway",
            request.path, payment.transaction_id,
        )
        payment.status = "failed"
        payment.failure_reason = str(exc)
        order.status = "payment_failed"
        order.payment_status = "failed"
        db.session.commit()
        flash(str(exc), "danger")
        return redirect(url_for("commerce.order_detail", order_id=order.id))


def _find_payment() -> PaymentTransaction | None:
    transaction_id = (request.values.get("tran_id") or "").strip()
    if not transaction_id:
        return None
    return PaymentTransaction.query.filter_by(transaction_id=transaction_id).first()


def _mark_failed(payment: PaymentTransaction, status: str, reason: str):
    if payment.status == "paid":
        return
    payment.status = status
    payment.failure_reason = reason[:500]
    if payment.order:
        payment.order.payment_status = "cancelled" if status == "cancelled" else "failed"
        payment.order.status = "cancelled" if status == "cancelled" else "payment_failed"
    if payment.subscription:
        payment.subscription.status = "cancelled"
    db.session.commit()


def _verify_and_fulfil(payment: PaymentTransaction, validation_id: str) -> tuple[bool, str]:
    if payment.status == "paid":
        return True, "Payment was already verified."

    try:
        payload = validate_payment(validation_id)
    except SSLCommerzError as exc:
        _mark_failed(payment, "validation_failed", str(exc))
        return False, str(exc)

    gateway_status = str(payload.get("status") or "").upper()
    gateway_transaction_id = str(payload.get("tran_id") or "")
    gateway_currency = str(payload.get("currency") or "").upper()
    try:
        gateway_amount = _money(payload.get("amount"))
    except Exception:
        gateway_amount = Decimal("-1.00")

    valid = (
        gateway_status in {"VALID", "VALIDATED"}
        and secrets.compare_digest(gateway_transaction_id, payment.transaction_id)
        and gateway_currency == payment.currency
        and gateway_amount == _money(payment.amount)
        and str(payload.get("value_a") or "") == payment.purpose
    )
    if not valid:
        payment.gateway_response = _safe_gateway_audit(payload)
        _mark_failed(payment, "validation_failed", "Gateway validation data did not match the transaction.")
        return False, "Payment validation failed."

    if str(payload.get("risk_level") or "0") == "1":
        payment.gateway_response = _safe_gateway_audit(payload)
        payment.risk_level = "1"
        _mark_failed(payment, "validation_failed", "Gateway marked this transaction as risky.")
        return False, "Payment requires manual risk review."

    now = datetime.utcnow()
    payment.status = "paid"
    payment.validation_id = validation_id
    payment.bank_transaction_id = str(payload.get("bank_tran_id") or "") or None
    payment.card_type = str(payload.get("card_type") or "")[:80] or None
    payment.risk_level = str(payload.get("risk_level") or "0")[:20]
    payment.gateway_response = _safe_gateway_audit(payload)
    payment.paid_at = now
    payment.failure_reason = None

    if payment.order:
        payment.order.payment_status = "paid"
        payment.order.status = "confirmed"
        payment.order.paid_at = now
    else:
        subscription = payment.subscription
        latest_active = (
            Subscription.query.filter_by(user_id=payment.user_id, status="active")
            .filter(Subscription.ends_at > now)
            .order_by(Subscription.ends_at.desc())
            .first()
        )
        starts_at = latest_active.ends_at if latest_active else now
        subscription.status = "active"
        subscription.starts_at = starts_at
        subscription.ends_at = starts_at + timedelta(days=subscription.plan.duration_days)
        payment.user.is_subscribed = True

    db.session.commit()
    return True, "Payment verified successfully."


@commerce_bp.route("/payments/success", methods=["GET", "POST"])
@csrf.exempt
def payment_success():
    payment = _find_payment()
    if not payment:
        return render_template("commerce/payment_result.html", success=False, message="Payment record not found."), 404
    validation_id = (request.values.get("val_id") or "").strip()
    success, message = _verify_and_fulfil(payment, validation_id)
    return render_template("commerce/payment_result.html", success=success, message=message, payment=payment), (200 if success else 400)


@commerce_bp.route("/payments/fail", methods=["GET", "POST"])
@csrf.exempt
def payment_fail():
    payment = _find_payment()
    if payment:
        _mark_failed(payment, "failed", "The gateway reported a failed payment.")
    return render_template("commerce/payment_result.html", success=False, message="Payment failed. No access or order confirmation was granted.", payment=payment), 400


@commerce_bp.route("/payments/cancel", methods=["GET", "POST"])
@csrf.exempt
def payment_cancel():
    payment = _find_payment()
    if payment:
        _mark_failed(payment, "cancelled", "The customer cancelled the payment.")
    return render_template("commerce/payment_result.html", success=False, message="Payment cancelled.", payment=payment), 200


@commerce_bp.route("/payments/ipn", methods=["POST"])
@csrf.exempt
def payment_ipn():
    payment = _find_payment()
    if not payment:
        return jsonify({"ok": False, "error": "transaction_not_found"}), 404
    validation_id = (request.form.get("val_id") or "").strip()
    success, message = _verify_and_fulfil(payment, validation_id)
    return jsonify({"ok": success, "message": message}), (200 if success else 400)


@commerce_bp.route("/orders")
@login_required
@role_required("user")
def orders():
    user_orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.created_at.desc()).all()
    return render_template("commerce/orders.html", orders=user_orders)


@commerce_bp.route("/orders/<int:order_id>")
@login_required
def order_detail(order_id: int):
    order = Order.query.options(joinedload(Order.items), joinedload(Order.vendor)).filter_by(id=order_id).first_or_404()
    can_view = current_user.role == "admin" or order.user_id == current_user.id or (
        current_user.role == "vendor" and order.vendor.owner_user_id == current_user.id
    )
    if not can_view:
        abort(403)
    return render_template("commerce/order_detail.html", order=order)


@commerce_bp.route("/vendor/orders")
@login_required
@approved_vendor_required
def vendor_orders():
    vendor = Vendor.query.filter_by(owner_user_id=current_user.id).first_or_404()
    orders_list = Order.query.filter_by(vendor_id=vendor.id).order_by(Order.created_at.desc()).all()
    return render_template("commerce/vendor_orders.html", orders=orders_list, vendor=vendor)


@commerce_bp.route("/vendor/orders/<int:order_id>/status", methods=["POST"])
@login_required
@approved_vendor_required
def update_order_status(order_id: int):
    vendor = Vendor.query.filter_by(owner_user_id=current_user.id).first_or_404()
    order = Order.query.filter_by(id=order_id, vendor_id=vendor.id).first_or_404()
    new_status = (request.form.get("status") or "").strip()
    if order.payment_status != "paid" or new_status not in ORDER_STATUS_TRANSITIONS.get(order.status, set()):
        flash("That order status change is not allowed.", "danger")
    else:
        order.status = new_status
        db.session.commit()
        flash("Order status updated.", "success")
    return redirect(url_for("commerce.order_detail", order_id=order.id))


@commerce_bp.route("/admin/commerce")
@login_required
@admin_required
def admin_commerce():
    recent_payments = PaymentTransaction.query.order_by(PaymentTransaction.created_at.desc()).limit(100).all()
    recent_orders = Order.query.order_by(Order.created_at.desc()).limit(100).all()
    paid_total = (
        db.session.query(db.func.coalesce(db.func.sum(PaymentTransaction.amount), 0))
        .filter(PaymentTransaction.status == "paid")
        .scalar()
    )
    return render_template(
        "commerce/admin_commerce.html",
        payments=recent_payments,
        orders=recent_orders,
        paid_total=_money(paid_total),
    )
