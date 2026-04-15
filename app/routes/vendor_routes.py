from flask import Blueprint, abort, render_template, request

from app.extensions import db
from app.models import MenuItem, Vendor

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

    return render_template(
        "vendors/vendors.html",
        vendors=vendors_list,
        categories=categories,
        current_search=search,
        current_category=category,
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

    return render_template("vendors/vendor_detail.html", vendor=vendor, menu_items=menu_items)


@vendor_bp.route("/menu-item/<int:item_id>")
def menu_item_detail(item_id: int):
    item = db.session.get(MenuItem, item_id)
    if not item or not item.is_available or not item.vendor or not item.vendor.is_active:
        abort(404)

    return render_template("vendors/menu_item_detail.html", item=item)
