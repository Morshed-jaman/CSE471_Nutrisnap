from decimal import Decimal

from extensions import db
from models import MenuItem, Vendor


DEMO_VENDOR_DATA = [
    {
        "vendor": {
            "name": "Green Bowl Kitchen",
            "category": "Healthy",
            "description": "Fresh grain bowls, lean proteins, and balanced meal boxes.",
            "image_url": "https://images.unsplash.com/photo-1512621776951-a57141f2eefd?auto=format&fit=crop&w=1200&q=80",
            "contact_email": "hello@greenbowl.example",
            "phone": "+8801700001001",
            "address": "Dhanmondi, Dhaka",
            "is_active": True,
        },
        "items": [
            {
                "name": "Chicken Quinoa Bowl",
                "description": "Grilled chicken, quinoa, roasted vegetables, tahini dressing.",
                "price": Decimal("9.50"),
                "image_url": "https://images.unsplash.com/photo-1546069901-ba9599a7e63c?auto=format&fit=crop&w=1000&q=80",
                "calories": Decimal("430"),
                "protein": Decimal("34"),
                "carbohydrates": Decimal("38"),
                "fats": Decimal("14"),
                "is_available": True,
            },
            {
                "name": "Tofu Power Bowl",
                "description": "Marinated tofu, brown rice, avocado, seasonal greens.",
                "price": Decimal("8.75"),
                "image_url": "https://images.unsplash.com/photo-1512058564366-18510be2db19?auto=format&fit=crop&w=1000&q=80",
                "calories": Decimal("410"),
                "protein": Decimal("21"),
                "carbohydrates": Decimal("47"),
                "fats": Decimal("16"),
                "is_available": True,
            },
            {
                "name": "Salmon Greens Plate",
                "description": "Oven salmon with leafy salad and citrus vinaigrette.",
                "price": Decimal("11.20"),
                "image_url": "https://images.unsplash.com/photo-1467003909585-2f8a72700288?auto=format&fit=crop&w=1000&q=80",
                "calories": Decimal("460"),
                "protein": Decimal("36"),
                "carbohydrates": Decimal("20"),
                "fats": Decimal("24"),
                "is_available": True,
            },
        ],
    },
    {
        "vendor": {
            "name": "Urban Grill Hub",
            "category": "Fast Food",
            "description": "Modern grilled favorites with lighter preparation options.",
            "image_url": "https://images.unsplash.com/photo-1555396273-367ea4eb4db5?auto=format&fit=crop&w=1200&q=80",
            "contact_email": "contact@urbangrill.example",
            "phone": "+8801700001002",
            "address": "Banani, Dhaka",
            "is_active": True,
        },
        "items": [
            {
                "name": "Lean Beef Burger",
                "description": "Whole wheat bun, lean beef patty, lettuce, tomato.",
                "price": Decimal("7.90"),
                "image_url": "https://images.unsplash.com/photo-1568901346375-23c9450c58cd?auto=format&fit=crop&w=1000&q=80",
                "calories": Decimal("540"),
                "protein": Decimal("31"),
                "carbohydrates": Decimal("43"),
                "fats": Decimal("27"),
                "is_available": True,
            },
            {
                "name": "Grilled Chicken Wrap",
                "description": "Chicken breast wrap with yogurt sauce and mixed veggies.",
                "price": Decimal("6.80"),
                "image_url": "https://images.unsplash.com/photo-1604908177073-8437c0a56b2b?auto=format&fit=crop&w=1000&q=80",
                "calories": Decimal("420"),
                "protein": Decimal("29"),
                "carbohydrates": Decimal("39"),
                "fats": Decimal("14"),
                "is_available": True,
            },
            {
                "name": "Baked Potato Wedges",
                "description": "Crispy baked wedges with smoked paprika and herbs.",
                "price": Decimal("3.90"),
                "image_url": "https://images.unsplash.com/photo-1518013431117-eb1465fa5752?auto=format&fit=crop&w=1000&q=80",
                "calories": Decimal("280"),
                "protein": Decimal("5"),
                "carbohydrates": Decimal("40"),
                "fats": Decimal("10"),
                "is_available": True,
            },
        ],
    },
    {
        "vendor": {
            "name": "FitFuel Cafe",
            "category": "Cafe",
            "description": "Protein smoothies, oat bowls, and macro-friendly snacks.",
            "image_url": "https://images.unsplash.com/photo-1509042239860-f550ce710b93?auto=format&fit=crop&w=1200&q=80",
            "contact_email": "info@fitfuel.example",
            "phone": "+8801700001003",
            "address": "Gulshan 1, Dhaka",
            "is_active": True,
        },
        "items": [
            {
                "name": "Berry Protein Smoothie",
                "description": "Mixed berries, whey protein, almond milk.",
                "price": Decimal("5.50"),
                "image_url": "https://images.unsplash.com/photo-1505252585461-04db1eb84625?auto=format&fit=crop&w=1000&q=80",
                "calories": Decimal("260"),
                "protein": Decimal("27"),
                "carbohydrates": Decimal("24"),
                "fats": Decimal("7"),
                "is_available": True,
            },
            {
                "name": "Peanut Oat Jar",
                "description": "Overnight oats with peanut butter, chia, and banana.",
                "price": Decimal("4.40"),
                "image_url": "https://images.unsplash.com/photo-1517673132405-a56a62b18caf?auto=format&fit=crop&w=1000&q=80",
                "calories": Decimal("340"),
                "protein": Decimal("14"),
                "carbohydrates": Decimal("44"),
                "fats": Decimal("12"),
                "is_available": True,
            },
            {
                "name": "Greek Yogurt Parfait",
                "description": "Greek yogurt layered with granola and fruit compote.",
                "price": Decimal("4.95"),
                "image_url": "https://images.unsplash.com/photo-1488477181946-6428a0291777?auto=format&fit=crop&w=1000&q=80",
                "calories": Decimal("290"),
                "protein": Decimal("18"),
                "carbohydrates": Decimal("31"),
                "fats": Decimal("9"),
                "is_available": True,
            },
        ],
    },
    {
        "vendor": {
            "name": "Spice Route Asian",
            "category": "Asian",
            "description": "Asian-inspired rice bowls and noodle plates with nutrition labels.",
            "image_url": "https://images.unsplash.com/photo-1552566626-52f8b828add9?auto=format&fit=crop&w=1200&q=80",
            "contact_email": "support@spiceroute.example",
            "phone": "+8801700001004",
            "address": "Uttara, Dhaka",
            "is_active": True,
        },
        "items": [
            {
                "name": "Teriyaki Chicken Rice",
                "description": "Steamed rice, teriyaki chicken, sesame vegetables.",
                "price": Decimal("8.20"),
                "image_url": "https://images.unsplash.com/photo-1553621042-f6e147245754?auto=format&fit=crop&w=1000&q=80",
                "calories": Decimal("520"),
                "protein": Decimal("30"),
                "carbohydrates": Decimal("59"),
                "fats": Decimal("17"),
                "is_available": True,
            },
            {
                "name": "Tofu Udon Stir Fry",
                "description": "Udon noodles with tofu, bok choy, and mushrooms.",
                "price": Decimal("7.60"),
                "image_url": "https://images.unsplash.com/photo-1612929633738-8fe44f7ec841?auto=format&fit=crop&w=1000&q=80",
                "calories": Decimal("470"),
                "protein": Decimal("19"),
                "carbohydrates": Decimal("63"),
                "fats": Decimal("15"),
                "is_available": True,
            },
            {
                "name": "Miso Salmon Bowl",
                "description": "Miso glazed salmon with rice and sauteed greens.",
                "price": Decimal("10.80"),
                "image_url": "https://images.unsplash.com/photo-1498654896293-37aacf113fd9?auto=format&fit=crop&w=1000&q=80",
                "calories": Decimal("540"),
                "protein": Decimal("35"),
                "carbohydrates": Decimal("42"),
                "fats": Decimal("24"),
                "is_available": True,
            },
        ],
    },
    {
        "vendor": {
            "name": "Plant Plate Co.",
            "category": "Vegan",
            "description": "100% plant-based dishes focused on fiber-rich ingredients.",
            "image_url": "https://images.unsplash.com/photo-1490818387583-1baba5e638af?auto=format&fit=crop&w=1200&q=80",
            "contact_email": "team@plantplate.example",
            "phone": "+8801700001005",
            "address": "Mirpur DOHS, Dhaka",
            "is_active": True,
        },
        "items": [
            {
                "name": "Chickpea Buddha Bowl",
                "description": "Roasted chickpeas, couscous, spinach, tahini drizzle.",
                "price": Decimal("7.30"),
                "image_url": "https://images.unsplash.com/photo-1511690743698-d9d85f2fbf38?auto=format&fit=crop&w=1000&q=80",
                "calories": Decimal("450"),
                "protein": Decimal("17"),
                "carbohydrates": Decimal("58"),
                "fats": Decimal("16"),
                "is_available": True,
            },
            {
                "name": "Lentil Spinach Soup",
                "description": "Slow-cooked lentils with spinach and tomato base.",
                "price": Decimal("4.80"),
                "image_url": "https://images.unsplash.com/photo-1547592180-85f173990554?auto=format&fit=crop&w=1000&q=80",
                "calories": Decimal("230"),
                "protein": Decimal("13"),
                "carbohydrates": Decimal("31"),
                "fats": Decimal("6"),
                "is_available": True,
            },
            {
                "name": "Avocado Toast Duo",
                "description": "Whole-grain toast topped with avocado and seeds.",
                "price": Decimal("5.20"),
                "image_url": "https://images.unsplash.com/photo-1484723091739-30a097e8f929?auto=format&fit=crop&w=1000&q=80",
                "calories": Decimal("320"),
                "protein": Decimal("9"),
                "carbohydrates": Decimal("35"),
                "fats": Decimal("17"),
                "is_available": True,
            },
        ],
    },
]


def seed_vendor_demo_data() -> tuple[int, int]:
    seeded_vendors = 0
    seeded_items = 0

    try:
        for block in DEMO_VENDOR_DATA:
            vendor_data = block["vendor"]
            vendor = Vendor.query.filter_by(name=vendor_data["name"]).first()

            if not vendor:
                vendor = Vendor(**vendor_data)
                db.session.add(vendor)
                db.session.flush()
                seeded_vendors += 1
            else:
                for field, value in vendor_data.items():
                    setattr(vendor, field, value)

            for item_data in block["items"]:
                item = MenuItem.query.filter_by(vendor_id=vendor.id, name=item_data["name"]).first()
                if not item:
                    item = MenuItem(vendor_id=vendor.id, **item_data)
                    db.session.add(item)
                    seeded_items += 1
                else:
                    for field, value in item_data.items():
                        setattr(item, field, value)
                    item.vendor_id = vendor.id

        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    total_vendors = Vendor.query.filter_by(is_active=True).count()
    total_items = MenuItem.query.filter_by(is_available=True).count()
    return total_vendors, total_items
