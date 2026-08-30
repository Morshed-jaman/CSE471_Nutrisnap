from html.parser import HTMLParser
from urllib.parse import urlsplit

from app.extensions import db
from app.models import MenuItem, SubscriptionPlan, User, Vendor


class _LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hrefs = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                self.hrefs.append(href)


def test_landing_renders_public_content_and_valid_routes(client):
    response = client.get("/")

    assert response.status_code == 200
    assert b"Eat smarter" in response.data
    assert b"Illustrative sample data" in response.data
    assert b"Nutrition intelligence" in response.data
    assert b"Weekly insights" in response.data
    assert b"Pause motion" in response.data
    assert b"Daily overview" in response.data
    assert b'href="/register"' in response.data
    assert b'href="/vendors"' in response.data
    assert b'href="/login"' in response.data


def test_landing_uses_live_meal_and_plan_data(app, client):
    with app.app_context():
        vendor = Vendor(name="Fresh Table", category="Healthy", is_active=True)
        db.session.add(vendor)
        db.session.flush()
        db.session.add(MenuItem(vendor_id=vendor.id, name="Citrus Bowl", price="375.00", is_available=True))
        plan = SubscriptionPlan.query.filter_by(code="monthly").first()
        plan.name = "Live Monthly Plan"
        plan.price = "349.00"
        db.session.commit()

    response = client.get("/")

    assert response.status_code == 200
    assert b"Citrus Bowl" in response.data
    assert b"Fresh Table" in response.data
    assert "৳349.00" in response.get_data(as_text=True)


def test_landing_renders_authenticated_dashboard_cta(app, client):
    with app.app_context():
        user = User(name="Landing User", email="landing@example.com", phone="01711111111", role="user", is_active=True)
        user.set_password("password123")
        db.session.add(user)
        db.session.commit()

    login_response = client.post("/login", data={"email": "landing@example.com", "password": "password123"})
    assert login_response.status_code == 302

    response = client.get("/")
    assert response.status_code == 200
    assert b"Open Dashboard" in response.data
    assert b'href="/home"' in response.data


def test_landing_fallbacks_render_without_public_catalog(app, client):
    with app.app_context():
        MenuItem.query.delete()
        SubscriptionPlan.query.delete()
        db.session.commit()

    response = client.get("/")

    assert response.status_code == 200
    assert b"Garden grain bowl" in response.data
    assert b"Plans are temporarily unavailable" in response.data


def test_landing_has_no_broken_internal_links(client):
    response = client.get("/")
    parser = _LinkParser()
    parser.feed(response.get_data(as_text=True))

    paths = {urlsplit(href).path for href in parser.hrefs if href.startswith("/")}
    assert paths
    for path in paths:
        linked_response = client.get(path)
        assert linked_response.status_code < 400, f"Broken landing-page link: {path}"


def test_landing_photographic_hero_assets_are_local_and_available(client):
    response = client.get("/")
    html = response.get_data(as_text=True)
    asset_names = (
        "hero-meal-bowl.webp",
        "ingredient-avocado.webp",
        "ingredient-tomato.webp",
        "ingredient-spinach.webp",
        "ingredient-lemon.webp",
        "ingredient-herbs.webp",
    )

    assert "bowl-food" not in html
    for asset_name in asset_names:
        assert asset_name in html
        asset_response = client.get(f"/static/images/landing/{asset_name}")
        assert asset_response.status_code == 200
        assert asset_response.content_type == "image/webp"


def test_landing_has_seo_metadata_and_medical_disclaimer(client):
    response = client.get("/")
    html = response.get_data(as_text=True)

    assert '<link rel="canonical"' in html
    assert 'property="og:title"' in html
    assert 'name="twitter:card"' in html
    assert "not a substitute for professional medical advice" in html
