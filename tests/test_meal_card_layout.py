from datetime import date

from app.extensions import db
from app.models import FavoriteMeal, MealLog, User


def _meal_card_data(app):
    with app.app_context():
        user = User(name="Card Owner", email="cards@example.com", phone="01710000001", role="user", is_active=True)
        user.set_password("password123")
        other = User(name="Uploader With A Deliberately Long Display Name", email="other-cards@example.com", phone="01710000002", role="user", is_active=True)
        other.set_password("password123")
        admin = User(name="Card Admin", email="admin-cards@example.com", phone="01710000003", role="admin", is_active=True)
        admin.set_password("AdminPassword123!")
        db.session.add_all([user, other, admin]); db.session.flush()
        owned = MealLog(user_id=user.id, image_url="/static/images/landing/hero-meal-bowl.webp", meal_type="lunch", meal_date=date(2026, 8, 30), title="A Very Long Meal Name That Must Wrap Naturally Without Squeezing Metadata")
        shared = MealLog(user_id=other.id, image_url="/static/images/landing/hero-meal-bowl.webp", meal_type="dinner", meal_date=date(2026, 8, 29), title="Protein Bowl", calories=520, protein=38, carbohydrates=55, fats=16)
        db.session.add_all([owned, shared]); db.session.flush()
        db.session.add(FavoriteMeal(user_id=user.id, meal_log_id=owned.id)); db.session.commit()


def test_user_meal_cards_preserve_actions_statuses_and_structure(app, client):
    _meal_card_data(app)
    client.post("/login", data={"email": "cards@example.com", "password": "password123"})
    central = client.get("/meal-logs").get_data(as_text=True)
    personal = client.get("/my-meal-logs").get_data(as_text=True)

    assert 'class="meal-log-card-grid' in central
    assert "col-sm-6" not in central
    assert "Nutrition not analyzed" in central
    assert "Copy to My Meals" in central
    assert "In My Meals" in central
    assert "View Details" in central and "AI Explain" in central and "Saved" in central
    assert 'data-confirm-delete="Delete this meal log?"' in central
    assert "Uploader With A Deliberately Long Display Name" in central
    assert "Uploaded by" not in personal
    assert "Analyze" in personal and "Edit" in personal and "Delete" in personal


def test_admin_cards_keep_authorized_actions_without_user_copy_controls(app, client):
    _meal_card_data(app)
    response = client.post("/admin/login", data={"email": "admin-cards@example.com", "password": "AdminPassword123!"})
    assert response.status_code == 302
    html = client.get("/meal-logs").get_data(as_text=True)

    assert html.count(">Edit<") == 2
    assert html.count(">Delete<") == 2
    assert "Copy to My Meals" not in html
    assert "In My Meals" not in html
    assert "Save</span>" not in html
