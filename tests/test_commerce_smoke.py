from app.extensions import db
from app.models import User
from tests.conftest import login


def test_commerce_templates_render_for_user_vendor_and_admin(app, client, commerce_data):
    login(client)
    for path in ("/subscriptions", "/cart", "/orders"):
        response = client.get(path)
        assert response.status_code == 200
        assert b"NutriSnap" in response.data

    client.post("/logout")
    login(client, email="vendor@example.com")
    response = client.get("/vendor/orders")
    assert response.status_code == 200
    assert b"NutriSnap" in response.data

    with app.app_context():
        admin = User(
            name="Commerce Admin",
            email="admin@example.com",
            phone="01900000000",
            role="admin",
            is_active=True,
        )
        admin.set_password("password123")
        db.session.add(admin)
        db.session.commit()
    client.post("/logout")
    login(client, email="admin@example.com")
    response = client.get("/admin/commerce")
    assert response.status_code == 200
    assert b"NutriSnap" in response.data
