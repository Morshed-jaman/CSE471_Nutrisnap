import os
import tempfile
from decimal import Decimal, InvalidOperation

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models import FavoriteMenuItem, FavoriteVendor, MenuItem, Vendor, VendorSubscription
from app.services.auth_service import role_required, vendor_required
from app.services.cloudinary_service import delete_image, upload_image
from app.services.email_service import send_vendor_subscription_email
from app.services.nutrition_service import get_healthy_food_indicators

vendor_bp = Blueprint("vendor", __name__)


def _allowed_file(filename: str) -> bool:
    if "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in current_app.config.get("ALLOWED_IMAGE_EXTENSIONS", set())


def _looks_like_image(file_storage) -> bool:
    mimetype = (file_storage.mimetype or "").lower()
    return mimetype.startswith("image/")


def _save_temp_file(file_storage):
    original_name = secure_filename(file_storage.filename or "upload")
    suffix = os.path.splitext(original_name)[1] or ".jpg"
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    temp_file.close()
    file_storage.save(temp_file.name)
    return temp_file.name


def _to_decimal(raw_value: str, field_name: str, required: bool = False):
    raw = (raw_value or "").strip()
    if not raw:
        if required:
            raise ValueError(f"{field_name} is required.")
        return None

    try:
        return Decimal(raw)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{field_name} must be a valid number.") from exc


def _get_or_create_owned_vendor() -> Vendor:
    vendor = Vendor.query.filter_by(owner_user_id=current_user.id).first()
    if vendor:
        return vendor

    vendor = Vendor(
        owner_user_id=current_user.id,
        name=f"{current_user.name}'s Vendor",
        category="General",
        description=None,
        image_url=None,
        contact_email=current_user.email,
        phone=current_user.phone,
        address=None,
        is_active=True,
    )
    db.session.add(vendor)
    db.session.commit()
    return vendor


def _owned_menu_item_or_404(item_id: int) -> MenuItem:
    item = db.session.get(MenuItem, item_id)
    if not item or not item.vendor or item.vendor.owner_user_id != current_user.id:
        abort(404)
    return item


@vendor_bp.route("/vendors")
@login_required
@role_required("user", "vendor", "admin")
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
@login_required
@role_required("user", "vendor", "admin")
def vendor_detail(vendor_id: int):
    vendor = Vendor.query.filter_by(id=vendor_id, is_active=True).first()
    if not vendor:
        abort(404)

    show_all_items = current_user.role == "admin" or (
        current_user.role == "vendor" and vendor.owner_user_id == current_user.id
    )
    menu_query = MenuItem.query.filter_by(vendor_id=vendor.id)
    if not show_all_items:
        menu_query = menu_query.filter(MenuItem.is_available.is_(True))
    menu_items = menu_query.order_by(MenuItem.name.asc()).all()

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

    is_subscribed = False
    can_subscribe = current_user.role == "user"
    if can_subscribe:
        is_subscribed = (
            VendorSubscription.query.filter_by(user_id=current_user.id, vendor_id=vendor.id).first()
            is not None
        )

    return render_template(
        "vendors/vendor_detail.html",
        vendor=vendor,
        menu_items=menu_items,
        favorite_menu_item_ids=favorite_menu_item_ids,
        is_vendor_favorited=is_vendor_favorited,
        menu_item_indicators=menu_item_indicators,
        show_all_items=show_all_items,
        can_subscribe=can_subscribe,
        is_subscribed=is_subscribed,
        subscriber_count=len(vendor.subscriptions),
    )


@vendor_bp.route("/menu-item/<int:item_id>")
@login_required
@role_required("user", "vendor", "admin")
def menu_item_detail(item_id: int):
    item = db.session.get(MenuItem, item_id)
    if not item or not item.vendor or not item.vendor.is_active:
        abort(404)

    can_view_unavailable = current_user.role == "admin" or (
        current_user.role == "vendor" and item.vendor.owner_user_id == current_user.id
    )
    if not item.is_available and not can_view_unavailable:
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


@vendor_bp.route("/vendor/<int:vendor_id>/subscribe", methods=["POST"])
@login_required
@role_required("user")
def subscribe_vendor(vendor_id: int):
    vendor = Vendor.query.filter_by(id=vendor_id, is_active=True).first()
    if not vendor:
        abort(404)

    existing = VendorSubscription.query.filter_by(user_id=current_user.id, vendor_id=vendor.id).first()
    if existing:
        flash("You are already subscribed to this vendor.", "info")
        return redirect(url_for("vendor.vendor_detail", vendor_id=vendor.id))

    try:
        db.session.add(VendorSubscription(user_id=current_user.id, vendor_id=vendor.id))
        db.session.commit()
        try:
            send_vendor_subscription_email(vendor, current_user)
        except Exception as exc:
            current_app.logger.warning(
                "Vendor subscription email failed for vendor_id=%s: %s",
                vendor.id,
                exc,
            )
        flash("Subscribed to vendor successfully.", "success")
    except Exception as exc:
        db.session.rollback()
        current_app.logger.exception("Failed to subscribe to vendor: %s", exc)
        flash("Could not subscribe to this vendor right now.", "danger")

    return redirect(url_for("vendor.vendor_detail", vendor_id=vendor.id))


@vendor_bp.route("/vendor/<int:vendor_id>/unsubscribe", methods=["POST"])
@login_required
@role_required("user")
def unsubscribe_vendor(vendor_id: int):
    vendor = Vendor.query.filter_by(id=vendor_id, is_active=True).first()
    if not vendor:
        abort(404)

    existing = VendorSubscription.query.filter_by(user_id=current_user.id, vendor_id=vendor.id).first()
    if not existing:
        flash("You are not subscribed to this vendor.", "info")
        return redirect(url_for("vendor.vendor_detail", vendor_id=vendor.id))

    try:
        db.session.delete(existing)
        db.session.commit()
        flash("Unsubscribed from vendor successfully.", "success")
    except Exception as exc:
        db.session.rollback()
        current_app.logger.exception("Failed to unsubscribe from vendor: %s", exc)
        flash("Could not unsubscribe from this vendor right now.", "danger")

    return redirect(url_for("vendor.vendor_detail", vendor_id=vendor.id))


@vendor_bp.route("/vendor/dashboard")
@login_required
@vendor_required
def vendor_dashboard():
    vendor = _get_or_create_owned_vendor()
    menu_items = MenuItem.query.filter_by(vendor_id=vendor.id).order_by(MenuItem.name.asc()).all()
    total_items = len(menu_items)
    available_items = sum(1 for item in menu_items if item.is_available)
    unavailable_items = total_items - available_items
    subscriber_count = VendorSubscription.query.filter_by(vendor_id=vendor.id).count()
    return render_template(
        "vendor/vendor_dashboard.html",
        vendor=vendor,
        menu_items=menu_items[:6],
        total_items=total_items,
        available_items=available_items,
        unavailable_items=unavailable_items,
        subscriber_count=subscriber_count,
    )


@vendor_bp.route("/vendor/menu-items")
@login_required
@vendor_required
def vendor_menu_items():
    vendor = _get_or_create_owned_vendor()
    menu_items = MenuItem.query.filter_by(vendor_id=vendor.id).order_by(MenuItem.created_at.desc()).all()
    return render_template("vendor/menu_items.html", vendor=vendor, menu_items=menu_items)


@vendor_bp.route("/vendor/menu-item/create", methods=["GET", "POST"])
@vendor_bp.route("/vendor/menu-item/new", methods=["GET", "POST"])
@login_required
@vendor_required
def create_menu_item():
    vendor = _get_or_create_owned_vendor()

    if request.method == "GET":
        return render_template("vendor/menu_item_form.html", vendor=vendor, item=None, mode="create")

    name = (request.form.get("name") or "").strip()
    description = (request.form.get("description") or "").strip() or None
    is_available = (request.form.get("is_available") or "on") == "on"

    if not name:
        flash("Menu item name is required.", "danger")
        return render_template("vendor/menu_item_form.html", vendor=vendor, item=None, mode="create"), 400

    try:
        price = _to_decimal(request.form.get("price"), "Price", required=True)
        calories = _to_decimal(request.form.get("calories"), "Calories")
        protein = _to_decimal(request.form.get("protein"), "Protein")
        carbohydrates = _to_decimal(request.form.get("carbohydrates"), "Carbohydrates")
        fats = _to_decimal(request.form.get("fats"), "Fats")
    except ValueError as exc:
        flash(str(exc), "danger")
        return render_template("vendor/menu_item_form.html", vendor=vendor, item=None, mode="create"), 400

    image_url = (request.form.get("image_url") or "").strip() or None
    cloudinary_public_id = None
    image_file = request.files.get("image_file")
    temp_path = None

    try:
        if image_file and image_file.filename:
            if not _allowed_file(image_file.filename):
                flash("Only image files are allowed (png, jpg, jpeg, webp, gif).", "danger")
                return render_template("vendor/menu_item_form.html", vendor=vendor, item=None, mode="create"), 400

            if not _looks_like_image(image_file):
                flash("Uploaded file is not recognized as an image.", "danger")
                return render_template("vendor/menu_item_form.html", vendor=vendor, item=None, mode="create"), 400

            temp_path = _save_temp_file(image_file)
            image_url, cloudinary_public_id = upload_image(temp_path, folder="vendor_menu_items")

        menu_item = MenuItem(
            vendor_id=vendor.id,
            name=name,
            description=description,
            price=price,
            image_url=image_url,
            cloudinary_public_id=cloudinary_public_id,
            calories=calories,
            protein=protein,
            carbohydrates=carbohydrates,
            fats=fats,
            is_available=is_available,
        )
        db.session.add(menu_item)
        db.session.commit()
        flash("Menu item created successfully.", "success")
        return redirect(url_for("vendor.vendor_menu_items"))
    except Exception as exc:
        db.session.rollback()
        current_app.logger.exception("Failed to create menu item: %s", exc)
        if cloudinary_public_id:
            try:
                delete_image(cloudinary_public_id)
            except Exception:
                pass
        flash("Failed to create menu item.", "danger")
        return render_template("vendor/menu_item_form.html", vendor=vendor, item=None, mode="create"), 500
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


@vendor_bp.route("/vendor/menu-item/<int:item_id>/edit", methods=["GET", "POST"])
@login_required
@vendor_required
def edit_menu_item(item_id: int):
    vendor = _get_or_create_owned_vendor()
    item = _owned_menu_item_or_404(item_id)

    if request.method == "GET":
        return render_template("vendor/menu_item_form.html", vendor=vendor, item=item, mode="edit")

    name = (request.form.get("name") or "").strip()
    description = (request.form.get("description") or "").strip() or None
    is_available = (request.form.get("is_available") or "off") == "on"

    if not name:
        flash("Menu item name is required.", "danger")
        return render_template("vendor/menu_item_form.html", vendor=vendor, item=item, mode="edit"), 400

    try:
        price = _to_decimal(request.form.get("price"), "Price", required=True)
        calories = _to_decimal(request.form.get("calories"), "Calories")
        protein = _to_decimal(request.form.get("protein"), "Protein")
        carbohydrates = _to_decimal(request.form.get("carbohydrates"), "Carbohydrates")
        fats = _to_decimal(request.form.get("fats"), "Fats")
    except ValueError as exc:
        flash(str(exc), "danger")
        return render_template("vendor/menu_item_form.html", vendor=vendor, item=item, mode="edit"), 400

    old_public_id = item.cloudinary_public_id
    new_public_id = None
    image_file = request.files.get("image_file")
    image_url_override = (request.form.get("image_url") or "").strip() or None
    temp_path = None

    try:
        item.name = name
        item.description = description
        item.price = price
        item.calories = calories
        item.protein = protein
        item.carbohydrates = carbohydrates
        item.fats = fats
        item.is_available = is_available

        if image_file and image_file.filename:
            if not _allowed_file(image_file.filename):
                flash("Only image files are allowed (png, jpg, jpeg, webp, gif).", "danger")
                return render_template("vendor/menu_item_form.html", vendor=vendor, item=item, mode="edit"), 400

            if not _looks_like_image(image_file):
                flash("Uploaded file is not recognized as an image.", "danger")
                return render_template("vendor/menu_item_form.html", vendor=vendor, item=item, mode="edit"), 400

            temp_path = _save_temp_file(image_file)
            new_image_url, new_public_id = upload_image(temp_path, folder="vendor_menu_items")
            item.image_url = new_image_url
            item.cloudinary_public_id = new_public_id
        elif image_url_override:
            item.image_url = image_url_override

        db.session.commit()

        if new_public_id and old_public_id and old_public_id != new_public_id:
            try:
                delete_image(old_public_id)
            except Exception:
                flash("Item updated, but old image cleanup failed.", "warning")

        flash("Menu item updated successfully.", "success")
        return redirect(url_for("vendor.vendor_menu_items"))
    except Exception as exc:
        db.session.rollback()
        current_app.logger.exception("Failed to update menu item: %s", exc)
        if new_public_id:
            try:
                delete_image(new_public_id)
            except Exception:
                pass
        flash("Failed to update menu item.", "danger")
        return render_template("vendor/menu_item_form.html", vendor=vendor, item=item, mode="edit"), 500
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


@vendor_bp.route("/vendor/menu-item/<int:item_id>/delete", methods=["POST"])
@login_required
@vendor_required
def delete_menu_item(item_id: int):
    item = _owned_menu_item_or_404(item_id)
    public_id = item.cloudinary_public_id

    try:
        db.session.delete(item)
        db.session.commit()
        if public_id:
            try:
                delete_image(public_id)
            except Exception:
                flash("Item deleted, but image cleanup failed.", "warning")
        flash("Menu item deleted successfully.", "success")
    except Exception as exc:
        db.session.rollback()
        current_app.logger.exception("Failed to delete menu item: %s", exc)
        flash("Failed to delete menu item.", "danger")

    return redirect(url_for("vendor.vendor_menu_items"))


@vendor_bp.route("/vendor/menu-item/<int:item_id>/toggle-availability", methods=["POST"])
@login_required
@vendor_required
def toggle_menu_item_availability(item_id: int):
    item = _owned_menu_item_or_404(item_id)
    try:
        item.is_available = not bool(item.is_available)
        db.session.commit()
        state = "available" if item.is_available else "unavailable"
        flash(f"'{item.name}' marked as {state}.", "success")
    except Exception as exc:
        db.session.rollback()
        current_app.logger.exception("Failed to toggle item availability: %s", exc)
        flash("Could not update availability status.", "danger")
    return redirect(url_for("vendor.vendor_menu_items"))
