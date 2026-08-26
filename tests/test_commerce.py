from datetime import datetime
from decimal import Decimal

import pytest

from app.extensions import db
from app.models import (
    CartItem,
    FavoriteVendor,
    MenuItem,
    Order,
    PaymentTransaction,
    Subscription,
    SubscriptionPlan,
    User,
)
from app.routes import commerce_routes
from app.services.sslcommerz_service import GatewaySession
from app.services.sslcommerz_service import SSLCommerzError
from tests.conftest import login


def _gateway_session():
    return GatewaySession(
        gateway_url="https://sandbox.sslcommerz.com/EasyCheckOut/test",
        session_key="sandbox-session",
        response={"status": "SUCCESS", "GatewayPageURL": "https://sandbox.sslcommerz.com/EasyCheckOut/test"},
    )


def test_cart_rejects_items_from_multiple_vendors(app, client, commerce_data):
    login(client)
    response = client.post(
        f"/cart/items/{commerce_data['item_id']}",
        data={"quantity": "2", "next": "/cart"},
    )
    assert response.status_code == 302
    with app.app_context():
        cart_item = CartItem.query.one()
        assert cart_item.quantity == 2
        assert cart_item.user_id == commerce_data["user_id"]


def test_subscription_is_not_activated_until_gateway_validation(
    app, client, commerce_data, monkeypatch
):
    login(client)
    monkeypatch.setattr(commerce_routes, "initiate_payment", lambda **_kwargs: _gateway_session())

    with app.app_context():
        plan_id = SubscriptionPlan.query.filter_by(code="monthly").one().id

    response = client.post(f"/subscriptions/{plan_id}/checkout")
    assert response.status_code == 302
    assert response.location.startswith("https://sandbox.sslcommerz.com/")

    with app.app_context():
        subscription = Subscription.query.one()
        payment = PaymentTransaction.query.one()
        assert subscription.status == "pending"
        assert payment.status == "pending"
        assert payment.user.is_subscribed is False
        transaction_id = payment.transaction_id

    monkeypatch.setattr(
        commerce_routes,
        "validate_payment",
        lambda _validation_id: {
            "status": "VALID",
            "tran_id": transaction_id,
            "currency": "BDT",
            "amount": "299.00",
            "value_a": "subscription",
            "risk_level": "0",
            "bank_tran_id": "BANK-1",
            "card_type": "VISA",
        },
    )
    response = client.post(
        "/payments/success", data={"tran_id": transaction_id, "val_id": "VALIDATION-1"}
    )
    assert response.status_code == 200

    with app.app_context():
        subscription = Subscription.query.one()
        payment = PaymentTransaction.query.one()
        assert subscription.status == "active"
        assert subscription.starts_at <= datetime.utcnow() <= subscription.ends_at
        assert payment.status == "paid"
        assert payment.user.is_subscribed is True


def test_gateway_amount_mismatch_never_fulfils_subscription(
    app, client, commerce_data, monkeypatch
):
    login(client)
    monkeypatch.setattr(commerce_routes, "initiate_payment", lambda **_kwargs: _gateway_session())
    with app.app_context():
        plan_id = SubscriptionPlan.query.filter_by(code="monthly").one().id
    client.post(f"/subscriptions/{plan_id}/checkout")
    with app.app_context():
        transaction_id = PaymentTransaction.query.one().transaction_id

    monkeypatch.setattr(
        commerce_routes,
        "validate_payment",
        lambda _validation_id: {
            "status": "VALID",
            "tran_id": transaction_id,
            "currency": "BDT",
            "amount": "1.00",
            "value_a": "subscription",
            "risk_level": "0",
        },
    )
    response = client.post(
        "/payments/success", data={"tran_id": transaction_id, "val_id": "BAD-AMOUNT"}
    )
    assert response.status_code == 400
    with app.app_context():
        payment = PaymentTransaction.query.one()
        assert payment.status == "validation_failed"
        assert payment.user.is_subscribed is False
        assert payment.subscription.status != "active"


def test_payment_initiation_failure_is_safe_and_sanitized(
    app, client, commerce_data, monkeypatch, caplog
):
    login(client)
    monkeypatch.setattr(
        commerce_routes,
        "initiate_payment",
        lambda **_kwargs: (_ for _ in ()).throw(SSLCommerzError("Gateway unavailable.")),
    )
    with app.app_context():
        plan_id = SubscriptionPlan.query.filter_by(code="monthly").one().id
    response = client.post(f"/subscriptions/{plan_id}/checkout")
    assert response.status_code == 302
    with app.app_context():
        assert PaymentTransaction.query.one().status == "failed"
        assert Subscription.query.one().status == "cancelled"
    assert "category=gateway" in caplog.text
    assert app.config["SSLCOMMERZ_STORE_PASSWORD"] not in caplog.text


def test_verified_order_uses_price_snapshot_and_becomes_confirmed(
    app, client, commerce_data, monkeypatch
):
    login(client)
    client.post(
        f"/cart/items/{commerce_data['item_id']}",
        data={"quantity": "2", "next": "/cart"},
    )
    monkeypatch.setattr(commerce_routes, "initiate_payment", lambda **_kwargs: _gateway_session())
    response = client.post(
        "/checkout",
        data={
            "delivery_name": "Customer One",
            "delivery_phone": "01700000000",
            "delivery_address": "House 1, Road 2, Dhaka",
            "customer_note": "Less spicy",
        },
    )
    assert response.status_code == 302

    with app.app_context():
        order = Order.query.one()
        payment = PaymentTransaction.query.one()
        assert order.subtotal == Decimal("500.00")
        assert order.delivery_fee == Decimal("60.00")
        assert order.total_amount == Decimal("560.00")
        assert order.items[0].unit_price == Decimal("250.00")
        assert CartItem.query.count() == 0
        transaction_id = payment.transaction_id

    monkeypatch.setattr(
        commerce_routes,
        "validate_payment",
        lambda _validation_id: {
            "status": "VALIDATED",
            "tran_id": transaction_id,
            "currency": "BDT",
            "amount": "560.00",
            "value_a": "order",
            "risk_level": "0",
        },
    )
    client.post("/payments/ipn", data={"tran_id": transaction_id, "val_id": "IPN-1"})
    with app.app_context():
        order = Order.query.one()
        assert order.payment_status == "paid"
        assert order.status == "confirmed"
        assert order.paid_at is not None


def test_payment_callback_is_idempotent(app, client, commerce_data, monkeypatch):
    login(client)
    monkeypatch.setattr(commerce_routes, "initiate_payment", lambda **_kwargs: _gateway_session())
    with app.app_context():
        plan_id = SubscriptionPlan.query.filter_by(code="monthly").one().id
    client.post(f"/subscriptions/{plan_id}/checkout")
    with app.app_context():
        transaction_id = PaymentTransaction.query.one().transaction_id

    monkeypatch.setattr(
        commerce_routes,
        "validate_payment",
        lambda _validation_id: {
            "status": "VALID",
            "tran_id": transaction_id,
            "currency": "BDT",
            "amount": "299.00",
            "value_a": "subscription",
            "risk_level": "0",
        },
    )
    first = client.post("/payments/ipn", data={"tran_id": transaction_id, "val_id": "VAL-1"})
    second = client.post("/payments/ipn", data={"tran_id": transaction_id, "val_id": "VAL-1"})
    assert first.status_code == 200
    assert second.status_code == 200
    with app.app_context():
        assert Subscription.query.filter_by(status="active").count() == 1


def test_favorites_are_owned_per_user(app, commerce_data):
    with app.app_context():
        second_user = User(
            name="Customer Two",
            email="customer2@example.com",
            phone="01600000000",
            role="user",
            is_active=True,
        )
        second_user.set_password("password123")
        db.session.add(second_user)
        db.session.flush()
        db.session.add_all(
            [
                FavoriteVendor(
                    user_id=commerce_data["user_id"], vendor_id=commerce_data["vendor_id"]
                ),
                FavoriteVendor(
                    user_id=second_user.id, vendor_id=commerce_data["vendor_id"]
                ),
            ]
        )
        db.session.commit()
        assert FavoriteVendor.query.filter_by(vendor_id=commerce_data["vendor_id"]).count() == 2


def test_cart_add_update_and_remove(app, client, commerce_data):
    login(client)
    client.post(f"/cart/items/{commerce_data['item_id']}", data={"quantity": "2"})
    with app.app_context():
        cart_id = CartItem.query.one().id
    client.post(f"/cart/items/{cart_id}/update", data={"quantity": "20"})
    with app.app_context():
        assert CartItem.query.one().quantity == 20
    client.post(f"/cart/items/{cart_id}/remove")
    with app.app_context():
        assert CartItem.query.count() == 0


def test_cart_rejects_a_second_vendor(app, client, commerce_data):
    login(client)
    client.post(f"/cart/items/{commerce_data['item_id']}", data={"quantity": "1"})
    with app.app_context():
        second_vendor = commerce_data["vendor_id"] + 1
        from app.models import Vendor
        db.session.add(Vendor(id=second_vendor, name="Other Kitchen", category="Food", is_active=True))
        db.session.flush()
        other = MenuItem(vendor_id=second_vendor, name="Other Bowl", price="90.00", is_available=True)
        db.session.add(other)
        db.session.commit()
        other_id = other.id
    client.post(f"/cart/items/{other_id}", data={"quantity": "1"})
    with app.app_context():
        assert CartItem.query.count() == 1
        assert CartItem.query.one().menu_item_id == commerce_data["item_id"]


def _pending_subscription_transaction(app, client, monkeypatch):
    monkeypatch.setattr(commerce_routes, "initiate_payment", lambda **_kwargs: _gateway_session())
    login(client)
    with app.app_context():
        plan_id = SubscriptionPlan.query.filter_by(code="monthly").one().id
    client.post(f"/subscriptions/{plan_id}/checkout")
    with app.app_context():
        return PaymentTransaction.query.one().transaction_id


@pytest.mark.parametrize(
    ("overrides", "validation_id"),
    [
        ({"currency": "USD"}, "BAD-CURRENCY"),
        ({"tran_id": "DIFFERENT-ID"}, "BAD-TRANSACTION"),
        ({"risk_level": "1"}, "RISKY"),
    ],
)
def test_gateway_validation_rejects_mismatches(
    app, client, commerce_data, monkeypatch, overrides, validation_id
):
    transaction_id = _pending_subscription_transaction(app, client, monkeypatch)
    payload = {
        "status": "VALID",
        "tran_id": transaction_id,
        "currency": "BDT",
        "amount": "299.00",
        "value_a": "subscription",
        "risk_level": "0",
    }
    payload.update(overrides)
    monkeypatch.setattr(commerce_routes, "validate_payment", lambda _value: payload)
    response = client.post(
        "/payments/ipn", data={"tran_id": transaction_id, "val_id": validation_id}
    )
    assert response.status_code == 400
    with app.app_context():
        assert PaymentTransaction.query.one().status == "validation_failed"
        assert Subscription.query.one().status != "active"


def test_unauthorized_order_access_is_forbidden(app, client, commerce_data):
    with app.app_context():
        order = Order(
            order_number="NS-ORD-PRIVATE",
            user_id=commerce_data["user_id"],
            vendor_id=commerce_data["vendor_id"],
            status="confirmed",
            payment_status="paid",
            subtotal="1.00",
            delivery_fee="0.00",
            total_amount="1.00",
            delivery_name="Private",
            delivery_phone="01700000000",
            delivery_address="A complete private address",
        )
        outsider = User(name="Outsider", email="outside@example.com", phone="01500000000", role="user")
        outsider.set_password("password123")
        db.session.add_all([order, outsider])
        db.session.commit()
        order_id = order.id
    login(client, email="outside@example.com")
    assert client.get(f"/orders/{order_id}").status_code == 403


def test_vendor_status_transition_rules(app, client, commerce_data):
    with app.app_context():
        order = Order(
            order_number="NS-ORD-STATUS",
            user_id=commerce_data["user_id"],
            vendor_id=commerce_data["vendor_id"],
            status="confirmed",
            payment_status="paid",
            subtotal="1.00",
            delivery_fee="0.00",
            total_amount="1.00",
            delivery_name="Customer",
            delivery_phone="01700000000",
            delivery_address="A complete delivery address",
        )
        db.session.add(order)
        db.session.commit()
        order_id = order.id
    login(client, email="vendor@example.com")
    client.post(f"/vendor/orders/{order_id}/status", data={"status": "delivered"})
    with app.app_context():
        assert db.session.get(Order, order_id).status == "confirmed"
    client.post(f"/vendor/orders/{order_id}/status", data={"status": "preparing"})
    with app.app_context():
        assert db.session.get(Order, order_id).status == "preparing"
