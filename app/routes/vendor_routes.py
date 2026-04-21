import os
import tempfile
from datetime import date
from decimal import Decimal, InvalidOperation

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models import FavoriteMenuItem, FavoriteVendor, MenuItem, Review, Vendor, VendorSubscription
from app.services.auth_service import approved_vendor_required, role_required
from app.services.cloudinary_service import delete_image, upload_image
from app.services.email_service import send_vendor_subscription_email

vendor_bp = Blueprint("vendor", __name__)
USER_MEAL_TYPES = ("breakfast", "lunch", "dinner", "snack")


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

    profile = current_user.vendor_profile

    vendor = Vendor(
        owner_user_id=current_user.id,
        name=profile.business_name if profile else current_user.name,
        category=profile.business_category if profile else "General",
        description=profile.business_description if profile else None,
        image_url=profile.cover_image_url if profile else None,
        contact_email=current_user.email,
        phone=current_user.phone,
        address=profile.business_address if profile else None,
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


def _active_vendor_or_404(vendor_id: int) -> Vendor:
    vendor = Vendor.query.filter_by(id=vendor_id, is_active=True).first()
    if not vendor:
        abort(404)
    return vendor


def _safe_redirect_url(default_endpoint: str, **default_values):
    next_url = (request.form.get("next") or request.args.get("next") or "").strip()
    if next_url.startswith("/") and not next_url.startswith("//"):
        return redirect(next_url)
    return redirect(url_for(default_endpoint, **default_values))


def _rating_input_error(raw_rating: str):
    try:
        rating = int((raw_rating or "").strip())
    except (TypeError, ValueError):
        return None, "Please select a valid star rating (1 to 5)."

    if rating < 1 or rating > 5:
        return None, "Rating must be between 1 and 5 stars."
    return rating, None


def _normalized_review_text(raw_text: str, max_length: int = 500):
    text = (raw_text or "").strip()
    if not text:
        return None, None
    if len(text) > max_length:
        return None, f"Review text must be {max_length} characters or less."
    return text, None


@vendor_bp.route("/vendors")
@login_required
@role_required("user", "vendor", "admin")
#featue1 member 2
#route for vonders
def vendors():
    search = (request.args.get("search") or "").strip()
    category = (request.args.get("category") or "").strip()

    query = Vendor.query.filter(Vendor.is_active.is_(True))

    if search:
        query = query.filter(Vendor.name.ilike(f"%{search}%"))

    if category:
        query = query.filter(Vendor.category == category)

    vendors_list = query.order_by(Vendor.name.asc()).all()
    vendor_ids = [v.id for v in vendors_list]

    vendor_rating_map: dict[int, dict[str, float | int]] = {}
    if vendor_ids:
        rating_rows = (
            db.session.query(
                Review.vendor_id,
                func.avg(Review.rating).label("avg_rating"),
                func.count(Review.id).label("review_count"),
            )
            .filter(Review.vendor_id.in_(vendor_ids))
            .group_by(Review.vendor_id)
            .all()
        )
        vendor_rating_map = {
            row.vendor_id: {"avg_rating": float(row.avg_rating), "review_count": int(row.review_count)}
            for row in rating_rows
        }

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
        vendor_rating_map=vendor_rating_map,
    )


@vendor_bp.route("/vendor/<int:vendor_id>")
@login_required
@role_required("user", "vendor", "admin")

def vendor_detail(vendor_id: int):
    vendor = _active_vendor_or_404(vendor_id)

    show_all_items = current_user.role == "admin" or (
        current_user.role == "vendor" and vendor.owner_user_id == current_user.id
    )

    menu_query = MenuItem.query.filter_by(vendor_id=vendor.id)
    if not show_all_items:
        menu_query = menu_query.filter(MenuItem.is_available.is_(True))

    menu_items = menu_query.order_by(MenuItem.name.asc()).all()
    menu_item_ids = [item.id for item in menu_items]

    vendor_avg_rating, vendor_review_count = (
        db.session.query(
            func.coalesce(func.avg(Review.rating), 0.0),
            func.count(Review.id),
        )
        .filter(Review.vendor_id == vendor.id)
        .one()
    )
    vendor_avg_rating = float(vendor_avg_rating or 0.0)
    vendor_review_count = int(vendor_review_count or 0)

    vendor_reviews = (
        Review.query.filter_by(vendor_id=vendor.id)
        .order_by(Review.updated_at.desc())
        .limit(20)
        .all()
    )

    my_vendor_review = None
    can_submit_review = current_user.role == "user"
    is_vendor_subscribed = False
    is_vendor_favorited = False
    favorite_menu_item_ids = set()
    if can_submit_review:
        my_vendor_review = Review.query.filter_by(
            user_id=current_user.id, vendor_id=vendor.id, menu_item_id=None
        ).first()
        is_vendor_subscribed = (
            VendorSubscription.query.filter_by(user_id=current_user.id, vendor_id=vendor.id).first()
            is not None
        )
        is_vendor_favorited = FavoriteVendor.query.filter_by(vendor_id=vendor.id).first() is not None
        if menu_item_ids:
            favorite_menu_item_ids = {
                favorite.menu_item_id
                for favorite in FavoriteMenuItem.query.filter(
                    FavoriteMenuItem.menu_item_id.in_(menu_item_ids)
                ).all()
            }

    item_rating_map: dict[int, dict[str, float | int]] = {}
    if menu_item_ids:
        item_rows = (
            db.session.query(
                Review.menu_item_id,
                func.avg(Review.rating).label("avg_rating"),
                func.count(Review.id).label("review_count"),
            )
            .filter(Review.menu_item_id.in_(menu_item_ids))
            .group_by(Review.menu_item_id)
            .all()
        )
        item_rating_map = {
            row.menu_item_id: {
                "avg_rating": float(row.avg_rating),
                "review_count": int(row.review_count),
            }
            for row in item_rows
        }

    return render_template(
        "vendors/vendor_detail.html",
        vendor=vendor,
        menu_items=menu_items,
        show_all_items=show_all_items,
        vendor_avg_rating=vendor_avg_rating,
        vendor_review_count=vendor_review_count,
        vendor_reviews=vendor_reviews,
        my_vendor_review=my_vendor_review,
        can_submit_review=can_submit_review,
        is_vendor_subscribed=is_vendor_subscribed,
        is_vendor_favorited=is_vendor_favorited,
        favorite_menu_item_ids=favorite_menu_item_ids,
        item_rating_map=item_rating_map,
        meal_types=USER_MEAL_TYPES,
        default_meal_date=date.today().isoformat(),
    )


@vendor_bp.route("/vendors/<int:vendor_id>/subscribe", methods=["POST"])
@login_required
@role_required("user")
def subscribe_vendor(vendor_id: int):
    vendor = _active_vendor_or_404(vendor_id)

    if vendor.owner_user_id == current_user.id:
        flash("You cannot subscribe to your own vendor account.", "warning")
        return _safe_redirect_url("vendor.vendor_detail", vendor_id=vendor.id)

    existing_subscription = VendorSubscription.query.filter_by(
        user_id=current_user.id,
        vendor_id=vendor.id,
    ).first()
    if existing_subscription:
        flash("You are already subscribed to this vendor.", "info")
        return _safe_redirect_url("vendor.vendor_detail", vendor_id=vendor.id)

    try:
        db.session.add(VendorSubscription(user_id=current_user.id, vendor_id=vendor.id))
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flash("You are already subscribed to this vendor.", "info")
        return _safe_redirect_url("vendor.vendor_detail", vendor_id=vendor.id)
    except Exception as exc:
        db.session.rollback()
        current_app.logger.exception("Failed to subscribe to vendor %s: %s", vendor.id, exc)
        flash("Could not subscribe to this vendor right now. Please try again.", "danger")
        return _safe_redirect_url("vendor.vendor_detail", vendor_id=vendor.id)

    email_result = send_vendor_subscription_email(vendor, current_user)
    if email_result.sent:
        flash(f"You are now subscribed to {vendor.name}.", "success")
    else:
        flash(
            f"You are now subscribed to {vendor.name}, but {email_result.warning_message or 'the vendor notification email could not be sent.'}",
            "warning",
        )

    return _safe_redirect_url("vendor.vendor_detail", vendor_id=vendor.id)


@vendor_bp.route("/vendors/<int:vendor_id>/unsubscribe", methods=["POST"])
@login_required
@role_required("user")
def unsubscribe_vendor(vendor_id: int):
    vendor = _active_vendor_or_404(vendor_id)
    subscription = VendorSubscription.query.filter_by(
        user_id=current_user.id,
        vendor_id=vendor.id,
    ).first()

    if not subscription:
        flash("You are not subscribed to this vendor.", "info")
        return _safe_redirect_url("vendor.vendor_detail", vendor_id=vendor.id)

    try:
        db.session.delete(subscription)
        db.session.commit()
        flash(f"You have unsubscribed from {vendor.name}.", "success")
    except Exception as exc:
        db.session.rollback()
        current_app.logger.exception("Failed to unsubscribe from vendor %s: %s", vendor.id, exc)
        flash("Could not unsubscribe from this vendor right now. Please try again.", "danger")

    return _safe_redirect_url("vendor.vendor_detail", vendor_id=vendor.id)


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

    item_avg_rating, item_review_count = (
        db.session.query(
            func.coalesce(func.avg(Review.rating), 0.0),
            func.count(Review.id),
        )
        .filter(Review.menu_item_id == item.id)
        .one()
    )
    item_avg_rating = float(item_avg_rating or 0.0)
    item_review_count = int(item_review_count or 0)

    item_reviews = (
        Review.query.filter_by(menu_item_id=item.id)
        .order_by(Review.updated_at.desc())
        .limit(20)
        .all()
    )

    my_item_review = None
    can_submit_review = current_user.role == "user"
    is_item_favorited = False
    if can_submit_review:
        my_item_review = Review.query.filter_by(
            user_id=current_user.id, menu_item_id=item.id, vendor_id=None
        ).first()
        is_item_favorited = FavoriteMenuItem.query.filter_by(menu_item_id=item.id).first() is not None

    return render_template(
        "vendors/menu_item_detail.html",
        item=item,
        item_avg_rating=item_avg_rating,
        item_review_count=item_review_count,
        item_reviews=item_reviews,
        my_item_review=my_item_review,
        can_submit_review=can_submit_review,
        is_item_favorited=is_item_favorited,
        meal_types=USER_MEAL_TYPES,
        default_meal_date=date.today().isoformat(),
    )


@vendor_bp.route("/vendor/<int:vendor_id>/review", methods=["POST"])
@login_required
@role_required("user")
def submit_vendor_review(vendor_id: int):
    vendor = _active_vendor_or_404(vendor_id)

    rating, rating_error = _rating_input_error(request.form.get("rating"))
    if rating_error:
        flash(rating_error, "danger")
        return redirect(url_for("vendor.vendor_detail", vendor_id=vendor_id))

    review_text, text_error = _normalized_review_text(request.form.get("review_text"), max_length=500)
    if text_error:
        flash(text_error, "danger")
        return redirect(url_for("vendor.vendor_detail", vendor_id=vendor_id))

    existing_review = Review.query.filter_by(
        user_id=current_user.id, vendor_id=vendor_id, menu_item_id=None
    ).first()

    try:
        if existing_review:
            existing_review.rating = rating
            existing_review.review_text = review_text
            flash("Your vendor review has been updated.", "success")
        else:
            db.session.add(
                Review(
                    user_id=current_user.id,
                    vendor_id=vendor_id,
                    menu_item_id=None,
                    rating=rating,
                    review_text=review_text,
                )
            )
            flash("Your vendor review has been submitted.", "success")

        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        current_app.logger.exception("Failed to submit vendor review: %s", exc)
        flash("Could not save your review right now. Please try again.", "danger")

    return redirect(url_for("vendor.vendor_detail", vendor_id=vendor_id) + "#vendor-reviews")


@vendor_bp.route("/menu-item/<int:item_id>/review", methods=["POST"])
@login_required
@role_required("user")
def submit_menu_item_review(item_id: int):
    item = db.session.get(MenuItem, item_id)
    if not item or not item.vendor or not item.vendor.is_active or not item.is_available:
        abort(404)

    rating, rating_error = _rating_input_error(request.form.get("rating"))
    if rating_error:
        flash(rating_error, "danger")
        return redirect(url_for("vendor.menu_item_detail", item_id=item_id))

    review_text, text_error = _normalized_review_text(request.form.get("review_text"), max_length=500)
    if text_error:
        flash(text_error, "danger")
        return redirect(url_for("vendor.menu_item_detail", item_id=item_id))

    existing_review = Review.query.filter_by(
        user_id=current_user.id, menu_item_id=item_id, vendor_id=None
    ).first()

    try:
        if existing_review:
            existing_review.rating = rating
            existing_review.review_text = review_text
            flash("Your menu item review has been updated.", "success")
        else:
            db.session.add(
                Review(
                    user_id=current_user.id,
                    vendor_id=None,
                    menu_item_id=item_id,
                    rating=rating,
                    review_text=review_text,
                )
            )
            flash("Your menu item review has been submitted.", "success")
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        current_app.logger.exception("Failed to submit menu item review: %s", exc)
        flash("Could not save your review right now. Please try again.", "danger")

    return redirect(url_for("vendor.menu_item_detail", item_id=item_id) + "#item-reviews")


@vendor_bp.route("/vendor-review/<int:review_id>/delete", methods=["POST"])
@login_required
@role_required("user", "admin")
def delete_vendor_review(review_id: int):
    review = db.session.get(Review, review_id)
    if not review or review.vendor_id is None:
        abort(404)

    if current_user.role != "admin" and review.user_id != current_user.id:
        flash("You can delete only your own review.", "danger")
        return redirect(url_for("vendor.vendor_detail", vendor_id=review.vendor_id))

    vendor_id = review.vendor_id
    try:
        db.session.delete(review)
        db.session.commit()
        flash("Vendor review deleted.", "success")
    except Exception as exc:
        db.session.rollback()
        current_app.logger.exception("Failed to delete vendor review: %s", exc)
        flash("Could not delete this review.", "danger")

    return redirect(url_for("vendor.vendor_detail", vendor_id=vendor_id) + "#vendor-reviews")


@vendor_bp.route("/menu-item-review/<int:review_id>/delete", methods=["POST"])
@login_required
@role_required("user", "admin")
def delete_menu_item_review(review_id: int):
    review = db.session.get(Review, review_id)
    if not review or review.menu_item_id is None:
        abort(404)

    if current_user.role != "admin" and review.user_id != current_user.id:
        flash("You can delete only your own review.", "danger")
        return redirect(url_for("vendor.menu_item_detail", item_id=review.menu_item_id))

    item_id = review.menu_item_id
    try:
        db.session.delete(review)
        db.session.commit()
        flash("Menu item review deleted.", "success")
    except Exception as exc:
        db.session.rollback()
        current_app.logger.exception("Failed to delete menu item review: %s", exc)
        flash("Could not delete this review.", "danger")

    return redirect(url_for("vendor.menu_item_detail", item_id=item_id) + "#item-reviews")


@vendor_bp.route("/vendor/dashboard")
@approved_vendor_required
def vendor_dashboard():
    vendor = _get_or_create_owned_vendor()
    menu_items = MenuItem.query.filter_by(vendor_id=vendor.id).order_by(MenuItem.name.asc()).all()
    subscriptions = (
        VendorSubscription.query.options(joinedload(VendorSubscription.user))
        .filter_by(vendor_id=vendor.id)
        .order_by(VendorSubscription.created_at.desc())
        .all()
    )
    total_items = len(menu_items)
    available_items = sum(1 for item in menu_items if item.is_available)
    unavailable_items = total_items - available_items
    vendor_avg_rating, vendor_review_count = (
        db.session.query(
            func.coalesce(func.avg(Review.rating), 0.0),
            func.count(Review.id),
        )
        .filter(Review.vendor_id == vendor.id)
        .one()
    )
    return render_template(
        "vendor/vendor_dashboard.html",
        vendor=vendor,
        menu_items=menu_items[:6],
        total_items=total_items,
        available_items=available_items,
        unavailable_items=unavailable_items,
        subscriber_count=len(subscriptions),
        recent_subscriptions=subscriptions[:8],
        vendor_avg_rating=float(vendor_avg_rating or 0.0),
        vendor_review_count=int(vendor_review_count or 0),
    )


@vendor_bp.route("/vendor/menu-items")
@approved_vendor_required
def vendor_menu_items():
    vendor = _get_or_create_owned_vendor()
    menu_items = MenuItem.query.filter_by(vendor_id=vendor.id).order_by(MenuItem.created_at.desc()).all()
    return render_template("vendor/menu_items.html", vendor=vendor, menu_items=menu_items)


@vendor_bp.route("/vendor/menu-item/create", methods=["GET", "POST"])
@vendor_bp.route("/vendor/menu-item/new", methods=["GET", "POST"])
@approved_vendor_required
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
@approved_vendor_required
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
@approved_vendor_required
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
@approved_vendor_required
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
#many are not included in feature 1
