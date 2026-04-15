from flask import Blueprint, abort, render_template, request

from app.extensions import db
from app.models import FavoriteMenuItem, FavoriteVendor, MenuItem, Vendor
from app.services.nutrition_service import get_healthy_food_indicators

vendor_bp = Blueprint("vendor", __name__)


@vendor_bp.route("/vendors")
def vendors():
    search = (request.args.get("search") or "").strip()
    category = (request.args.get("category") or "").strip()

    query = Vendor.query.filter(Vendor.is_active.is_(True))

    if search:
        query = query.filter(Vendor.name.ilike(f"%{search}%"))

    if category:
        query = query.filter(Vendor.category == category)

    vendors_list = query.order_by(Vendor.name.asc()).all()

    categories_query = (
        Vendor.query.with_entities(Vendor.category)
        .filter(Vendor.is_active.is_(True))
        .distinct()
        .order_by(Vendor.category.asc())
        .all()
    )
    categories = [row[0] for row in categories_query if row[0]]
    favorite_vendor_ids = {row[0] for row in db.session.query(FavoriteVendor.vendor_id).all()}

    return render_template(
        "vendors/vendors.html",
        vendors=vendors_list,
        categories=categories,
        current_search=search,
        current_category=category,
        favorite_vendor_ids=favorite_vendor_ids,
    )


@vendor_bp.route("/vendor/<int:vendor_id>")
def vendor_detail(vendor_id: int):
    vendor = Vendor.query.filter_by(id=vendor_id, is_active=True).first()
    if not vendor:
        abort(404)

    menu_items = (
        MenuItem.query.filter_by(vendor_id=vendor.id, is_available=True)
        .order_by(MenuItem.name.asc())
        .all()
    )

    menu_item_ids = [item.id for item in menu_items]
    favorite_menu_item_ids = set()

    if menu_item_ids:
        favorite_menu_item_ids = {
            row[0]
            for row in db.session.query(FavoriteMenuItem.menu_item_id)
            .filter(FavoriteMenuItem.menu_item_id.in_(menu_item_ids))
            .all()
        }

    is_vendor_favorited = FavoriteVendor.query.filter_by(vendor_id=vendor.id).first() is not None
    menu_item_indicators = {
        item.id: get_healthy_food_indicators(
            item.calories,
            item.protein,
            item.carbohydrates,
            item.fats,
        )
        for item in menu_items
    }

    return render_template(
        "vendors/vendor_detail.html",
        vendor=vendor,
        menu_items=menu_items,
        favorite_menu_item_ids=favorite_menu_item_ids,
        is_vendor_favorited=is_vendor_favorited,
        menu_item_indicators=menu_item_indicators,
    )


@vendor_bp.route("/menu-item/<int:item_id>")
def menu_item_detail(item_id: int):
    item = db.session.get(MenuItem, item_id)
    if not item or not item.is_available or not item.vendor or not item.vendor.is_active:
        abort(404)

    is_menu_item_favorited = FavoriteMenuItem.query.filter_by(menu_item_id=item.id).first() is not None
    menu_item_indicators = get_healthy_food_indicators(
        item.calories,
        item.protein,
        item.carbohydrates,
        item.fats,
    )

    return render_template(
        "vendors/menu_item_detail.html",
        item=item,
        is_menu_item_favorited=is_menu_item_favorited,
        menu_item_indicators=menu_item_indicators,
    )
