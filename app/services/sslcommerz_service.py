from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from urllib.parse import urlparse

import requests
from flask import current_app


class SSLCommerzError(RuntimeError):
    """Raised when a payment request cannot be completed safely."""


@dataclass(frozen=True)
class GatewaySession:
    gateway_url: str
    session_key: str | None
    response: dict[str, Any]


def _credentials() -> tuple[str, str]:
    store_id = (current_app.config.get("SSLCOMMERZ_STORE_ID") or "").strip()
    store_password = (current_app.config.get("SSLCOMMERZ_STORE_PASSWORD") or "").strip()
    if not store_id or not store_password:
        raise SSLCommerzError(
            "SSLCOMMERZ is not configured. Add the sandbox store ID and password."
        )
    return store_id, store_password


def _base_url() -> str:
    if current_app.config.get("SSLCOMMERZ_SANDBOX", True):
        return "https://sandbox.sslcommerz.com"
    return "https://securepay.sslcommerz.com"


def _post(url: str, *, data: dict[str, Any]) -> dict[str, Any]:
    timeout = current_app.config.get("PAYMENT_HTTP_TIMEOUT_SECONDS", 15)
    try:
        response = requests.post(url, data=data, timeout=timeout)
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        current_app.logger.warning("Payment gateway request failed category=%s", type(exc).__name__)
        raise SSLCommerzError("The payment gateway is temporarily unavailable.") from exc

    if not isinstance(payload, dict):
        raise SSLCommerzError("The payment gateway returned an invalid response.")
    return payload


def initiate_payment(
    *,
    transaction_id: str,
    amount: Decimal,
    customer_name: str,
    customer_email: str,
    customer_phone: str,
    customer_address: str,
    product_name: str,
    product_category: str,
    product_profile: str,
    success_url: str,
    fail_url: str,
    cancel_url: str,
    ipn_url: str,
    item_count: int = 1,
) -> GatewaySession:
    store_id, store_password = _credentials()
    request_data = {
        "store_id": store_id,
        "store_passwd": store_password,
        "total_amount": f"{amount:.2f}",
        "currency": "BDT",
        "tran_id": transaction_id,
        "success_url": success_url,
        "fail_url": fail_url,
        "cancel_url": cancel_url,
        "ipn_url": ipn_url,
        "cus_name": customer_name[:120],
        "cus_email": customer_email[:120],
        "cus_add1": customer_address[:255],
        "cus_city": "Dhaka",
        "cus_postcode": "1000",
        "cus_country": "Bangladesh",
        "cus_phone": customer_phone[:40],
        "shipping_method": "YES" if product_profile == "physical-goods" else "NO",
        "num_of_item": max(1, int(item_count)),
        "product_name": product_name[:255],
        "product_category": product_category[:100],
        "product_profile": product_profile,
        "value_a": product_category.lower().startswith("nutrition") and "subscription" or "order",
    }
    payload = _post(f"{_base_url()}/gwprocess/v4/api.php", data=request_data)
    gateway_url = str(payload.get("GatewayPageURL") or "").strip()
    gateway_host = (urlparse(gateway_url).hostname or "").lower()
    trusted_hosts = {"sandbox.sslcommerz.com", "securepay.sslcommerz.com"}
    if payload.get("status") != "SUCCESS" or gateway_host not in trusted_hosts:
        current_app.logger.warning("Payment session rejected status=%s", str(payload.get("status"))[:30])
        raise SSLCommerzError("Payment could not be started. Please try again shortly.")

    return GatewaySession(
        gateway_url=gateway_url,
        session_key=str(payload.get("sessionkey") or "").strip() or None,
        response=payload,
    )


def validate_payment(validation_id: str) -> dict[str, Any]:
    store_id, store_password = _credentials()
    if not validation_id:
        raise SSLCommerzError("Missing payment validation ID.")

    request_data = {
        "val_id": validation_id,
        "store_id": store_id,
        "store_passwd": store_password,
        "v": "1",
        "format": "json",
    }
    return _post(f"{_base_url()}/validator/api/validationserverAPI.php", data=request_data)
