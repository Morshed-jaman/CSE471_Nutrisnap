from decimal import Decimal

import pytest

from app.services import sslcommerz_service
from app.services.sslcommerz_service import SSLCommerzError, initiate_payment


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def _start_payment():
    return initiate_payment(
        transaction_id="NS-PAY-1",
        amount=Decimal("560.00"),
        customer_name="Customer",
        customer_email="customer@example.com",
        customer_phone="01700000000",
        customer_address="Dhaka, Bangladesh",
        product_name="NutriSnap order",
        product_category="Food",
        product_profile="physical-goods",
        success_url="https://nutrisnap.example/payments/success",
        fail_url="https://nutrisnap.example/payments/fail",
        cancel_url="https://nutrisnap.example/payments/cancel",
        ipn_url="https://nutrisnap.example/payments/ipn",
        item_count=2,
    )


def test_gateway_session_accepts_only_official_sslcommerz_host(app, monkeypatch):
    monkeypatch.setattr(
        sslcommerz_service.requests,
        "post",
        lambda *_args, **_kwargs: FakeResponse(
            {
                "status": "SUCCESS",
                "GatewayPageURL": "https://sandbox.sslcommerz.com/EasyCheckOut/session",
                "sessionkey": "session-1",
            }
        ),
    )
    with app.app_context():
        session = _start_payment()
        assert session.gateway_url.startswith("https://sandbox.sslcommerz.com/")


def test_gateway_session_rejects_untrusted_redirect_host(app, monkeypatch):
    monkeypatch.setattr(
        sslcommerz_service.requests,
        "post",
        lambda *_args, **_kwargs: FakeResponse(
            {
                "status": "SUCCESS",
                "GatewayPageURL": "https://sslcommerz.example.org/phishing",
                "sessionkey": "session-1",
            }
        ),
    )
    with app.app_context(), pytest.raises(SSLCommerzError):
        _start_payment()
