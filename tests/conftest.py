from pathlib import Path

import pytest

from app import create_app
from app.config import Config
from app.extensions import db
from app.models import MenuItem, User, Vendor


@pytest.fixture()
def app(tmp_path: Path):
    database_path = (tmp_path / "test.db").as_posix()

    class TestConfig(Config):
        TESTING = True
        WTF_CSRF_ENABLED = False
        SECRET_KEY = "test-secret"
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{database_path}"
        AUTO_CREATE_DB = True
        DEFAULT_ADMIN_EMAIL = None
        DEFAULT_ADMIN_PASSWORD = None
        PUBLIC_BASE_URL = "https://nutrisnap.example"
        SSLCOMMERZ_STORE_ID = "test-store"
        SSLCOMMERZ_STORE_PASSWORD = "test-password"
        SSLCOMMERZ_SANDBOX = True
        SESSION_COOKIE_SECURE = False
        ORDER_DELIVERY_FEE_BDT = 60

    application = create_app(TestConfig)
    yield application

    with application.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def commerce_data(app):
    with app.app_context():
        user = User(
            name="Customer One",
            email="customer@example.com",
            phone="01700000000",
            role="user",
            is_active=True,
            is_subscribed=False,
        )
        user.set_password("password123")
        vendor_user = User(
            name="Vendor Owner",
            email="vendor@example.com",
            phone="01800000000",
            role="vendor",
            vendor_status="approved",
            is_active=True,
        )
        vendor_user.set_password("password123")
        db.session.add_all([user, vendor_user])
        db.session.flush()
        vendor = Vendor(
            owner_user_id=vendor_user.id,
            name="Healthy Kitchen",
            category="Healthy Food",
            is_active=True,
        )
        db.session.add(vendor)
        db.session.flush()
        item = MenuItem(
            vendor_id=vendor.id,
            name="Protein Bowl",
            price="250.00",
            is_available=True,
        )
        db.session.add(item)
        db.session.commit()
        return {"user_id": user.id, "vendor_user_id": vendor_user.id, "vendor_id": vendor.id, "item_id": item.id}


def login(client, email="customer@example.com", password="password123"):
    return client.post("/login", data={"email": email, "password": password})
