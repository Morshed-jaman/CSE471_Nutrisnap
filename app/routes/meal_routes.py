import os
import tempfile
from datetime import datetime, timedelta
from urllib.parse import quote

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func, or_
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models import FavoriteMeal, MealLog, MenuItem, Vendor
from app.services.auth_service import redirect_for_role, role_required
from app.services.cloudinary_service import delete_image, upload_image
from app.services.nutrition_service import get_nutrition_insights

meal_bp = Blueprint("meal", __name__)
ALLOWED_MEAL_TYPES = {"breakfast", "lunch", "dinner", "snack"}


def _allowed_file(filename: str) -> bool:
    if "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in current_app.config.get("ALLOWED_IMAGE_EXTENSIONS", set())


def _looks_like_image(file_storage) -> bool:
    mimetype = (file_storage.mimetype or "").lower()
    return mimetype.startswith("image/")


def _parse_meal_date(raw_date: str):
    try:
        return datetime.strptime(raw_date, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _safe_redirect_url(default_endpoint: str, **default_values):
    next_url = (request.form.get("next") or request.args.get("next") or "").strip()
    if next_url.startswith("/") and not next_url.startswith("//"):
        return redirect(next_url)
    return redirect(url_for(default_endpoint, **default_values))


def _save_temp_file(file_storage):
    original_name = secure_filename(file_storage.filename or "upload")
    suffix = os.path.splitext(original_name)[1] or ".jpg"
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    temp_file.close()
    file_storage.save(temp_file.name)
    return temp_file.name


def _meal_image_from_vendor_item(item: MenuItem) -> str:
    if item.image_url:
        return item.image_url

    if item.vendor and item.vendor.image_url:
        return item.vendor.image_url

    label = (item.name or "Meal")[0].upper()
    svg = (
        "<svg xmlns='http://www.w3.org/2000/svg' width='1200' height='900' viewBox='0 0 1200 900'>"
        "<rect width='1200' height='900' fill='#f0ece4'/>"
        "<circle cx='600' cy='450' r='180' fill='#c95e36' fill-opacity='0.16'/>"
        "<text x='50%' y='50%' dominant-baseline='middle' text-anchor='middle' "
        "font-family='Arial, sans-serif' font-size='220' fill='#2f2923'>"
        f"{label}</text></svg>"
    )
    return f"data:image/svg+xml;utf8,{quote(svg)}"


def _meal_note_from_vendor_item(item: MenuItem) -> str:
    vendor_name = item.vendor.name if item.vendor else "Unknown Vendor"
    parts = [f"Added from vendor menu item: {vendor_name}"]

    description = (item.description or "").strip()
    if description:
        parts.append(description)

    return " | ".join(parts)


def _build_meal_log_from_vendor_item(item: MenuItem, meal_type: str, meal_date):
    return MealLog(
        user_id=current_user.id,
        image_url=_meal_image_from_vendor_item(item),
        cloudinary_public_id=None,
        meal_type=meal_type,
        meal_date=meal_date,
        title=item.name,
        note=_meal_note_from_vendor_item(item),
        calories=float(item.calories) if item.calories is not None else None,
        protein=float(item.protein) if item.protein is not None else None,
        carbohydrates=float(item.carbohydrates) if item.carbohydrates is not None else None,
        fats=float(item.fats) if item.fats is not None else None,
    )


def _can_modify_meal(meal: MealLog) -> bool:
    if current_user.role == "admin":
        return True
    return current_user.role == "user" and meal.user_id == current_user.id


def _is_owner(meal: MealLog) -> bool:
    return current_user.role == "user" and meal.user_id == current_user.id


def _owner_label(meal: MealLog) -> str:
    if meal.user:
        return meal.user.name
    return "Legacy / Unknown"


def _image_referenced_by_others(image_url: str | None, exclude_meal_id: int) -> bool:
    if not image_url:
        return False

    count = (
        MealLog.query.filter(MealLog.id != exclude_meal_id, MealLog.image_url == image_url)
        .limit(1)
        .count()
    )
    return count > 0


def _home_page_context(user_id: int):
    total_meal_logs = (
        db.session.query(func.count(MealLog.id)).filter(MealLog.user_id == user_id).scalar() or 0
    )
    meals_with_nutrition = (
        db.session.query(func.count(MealLog.id))
        .filter(
            MealLog.user_id == user_id,
            or_(
                MealLog.calories.isnot(None),
                MealLog.protein.isnot(None),
                MealLog.carbohydrates.isnot(None),
                MealLog.fats.isnot(None),
            ),
        )
        .scalar()
        or 0
    )
    active_vendors = (
        db.session.query(func.count(Vendor.id))
        .filter(Vendor.is_active.is_(True))
        .scalar()
        or 0
    )
    total_menu_items = db.session.query(func.count(MenuItem.id)).scalar() or 0
    recent_uploads = (
        db.session.query(func.count(MealLog.id))
        .filter(
            MealLog.user_id == user_id,
            MealLog.created_at >= datetime.utcnow() - timedelta(days=7),
        )
        .scalar()
        or 0
    )
    available_categories = (
        db.session.query(func.count(func.distinct(Vendor.category)))
        .filter(Vendor.is_active.is_(True))
        .scalar()
        or 0
    )

    latest_meals = (
        MealLog.query.filter(MealLog.user_id == user_id)
        .order_by(MealLog.meal_date.desc(), MealLog.created_at.desc())
        .limit(6)
        .all()
    )
    featured_vendors = (
        Vendor.query.filter(Vendor.is_active.is_(True))
        .order_by(Vendor.created_at.desc())
        .limit(6)
        .all()
    )
    nutrition_ready_meals = (
        MealLog.query.filter(
            MealLog.user_id == user_id,
            or_(
                MealLog.calories.isnot(None),
                MealLog.protein.isnot(None),
                MealLog.carbohydrates.isnot(None),
                MealLog.fats.isnot(None),
            ),
        )
        .order_by(MealLog.updated_at.desc())
        .limit(6)
        .all()
    )

    return dict(
        total_meal_logs=total_meal_logs,
        meals_with_nutrition=meals_with_nutrition,
        active_vendors=active_vendors,
        total_menu_items=total_menu_items,
        recent_uploads=recent_uploads,
        available_categories=available_categories,
        latest_meals=latest_meals,
        featured_vendors=featured_vendors,
        nutrition_ready_meals=nutrition_ready_meals,
    )


@meal_bp.route("/")
def landing():
    if current_user.is_authenticated:
        return redirect(redirect_for_role(current_user))
    return render_template("landing.html")


@meal_bp.route("/home")
@login_required
def home():
    if current_user.role != "user":
        return redirect(redirect_for_role(current_user))
    return render_template("home.html", **_home_page_context(current_user.id))


@meal_bp.route("/upload-meal", methods=["GET", "POST"])
@login_required
@role_required("user")
def upload_meal():
    if request.method == "GET":
        return render_template("meals/upload_meal.html", meal_types=sorted(ALLOWED_MEAL_TYPES))

    image_file = request.files.get("image")
    meal_type = (request.form.get("meal_type") or "").strip().lower()
    meal_date_raw = (request.form.get("meal_date") or "").strip()
    title = (request.form.get("title") or "").strip() or None
    note = (request.form.get("note") or "").strip() or None

    if not image_file or not image_file.filename:
        flash("Please select an image to upload.", "danger")
        return render_template("meals/upload_meal.html", meal_types=sorted(ALLOWED_MEAL_TYPES)), 400

    if not _allowed_file(image_file.filename):
        flash("Only image files are allowed (png, jpg, jpeg, webp, gif).", "danger")
        return render_template("meals/upload_meal.html", meal_types=sorted(ALLOWED_MEAL_TYPES)), 400

    if not _looks_like_image(image_file):
        flash("Uploaded file is not recognized as an image.", "danger")
        return render_template("meals/upload_meal.html", meal_types=sorted(ALLOWED_MEAL_TYPES)), 400

    if meal_type not in ALLOWED_MEAL_TYPES:
        flash("Meal type must be breakfast, lunch, dinner, or snack.", "danger")
        return render_template("meals/upload_meal.html", meal_types=sorted(ALLOWED_MEAL_TYPES)), 400

    meal_date = _parse_meal_date(meal_date_raw)
    if not meal_date:
        flash("Please provide a valid meal date.", "danger")
        return render_template("meals/upload_meal.html", meal_types=sorted(ALLOWED_MEAL_TYPES)), 400

    temp_path = None
    try:
        temp_path = _save_temp_file(image_file)
        image_url, public_id = upload_image(temp_path, folder="meal_logs")

        meal_log = MealLog(
            user_id=current_user.id,
            image_url=image_url,
            cloudinary_public_id=public_id,
            meal_type=meal_type,
            meal_date=meal_date,
            title=title,
            note=note,
        )
        db.session.add(meal_log)
        db.session.commit()
        flash("Meal log saved to your personal meal logs.", "success")
        return redirect(url_for("meal.my_meal_logs"))
    except RuntimeError as exc:
        db.session.rollback()
        current_app.logger.warning("Upload blocked: %s", exc)
        flash(str(exc), "danger")
        return render_template("meals/upload_meal.html", meal_types=sorted(ALLOWED_MEAL_TYPES)), 500
    except Exception as exc:
        db.session.rollback()
        current_app.logger.exception("Failed to save meal log: %s", exc)
        flash("Failed to save meal log. Please try again.", "danger")
        return render_template("meals/upload_meal.html", meal_types=sorted(ALLOWED_MEAL_TYPES)), 500
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


@meal_bp.route("/my-meal-logs")
@login_required
@role_required("user")
def my_meal_logs():
    logs = (
        MealLog.query.filter(MealLog.user_id == current_user.id)
        .order_by(MealLog.created_at.desc())
        .all()
    )
    favorite_meal_ids = {favorite.meal_log_id for favorite in FavoriteMeal.query.all()}
    return render_template(
        "meals/my_meal_logs.html",
        logs=logs,
        favorite_meal_ids=favorite_meal_ids,
    )


@meal_bp.route("/meal-logs")
@login_required
@role_required("user", "vendor", "admin")
def meal_logs():
    logs = MealLog.query.order_by(MealLog.created_at.desc()).all()
    favorite_meal_ids = (
        {favorite.meal_log_id for favorite in FavoriteMeal.query.all()}
        if current_user.role == "user"
        else set()
    )
    return render_template(
        "meals/meal_logs.html",
        logs=logs,
        favorite_meal_ids=favorite_meal_ids,
    )


@meal_bp.route("/meal-log/<int:meal_id>")
@login_required
@role_required("user", "vendor", "admin")
def meal_detail(meal_id):
    meal = db.session.get(MealLog, meal_id)
    if not meal:
        abort(404)

    meal_insights = []
    if any(value is not None for value in [meal.calories, meal.protein, meal.carbohydrates, meal.fats]):
        meal_insights = get_nutrition_insights(
            meal.calories, meal.protein, meal.carbohydrates, meal.fats
        )

    can_modify = _can_modify_meal(meal)
    can_save_copy = current_user.role == "user" and meal.user_id != current_user.id
    can_analyze = current_user.role == "admin" or _is_owner(meal)
    is_meal_favorited = (
        current_user.role == "user"
        and FavoriteMeal.query.filter_by(meal_log_id=meal.id).first() is not None
    )

    return render_template(
        "meals/meal_detail.html",
        meal=meal,
        meal_insights=meal_insights,
        can_modify=can_modify,
        can_analyze=can_analyze,
        can_save_copy=can_save_copy,
        owner_label=_owner_label(meal),
        is_meal_favorited=is_meal_favorited,
    )


@meal_bp.route("/meal-log/<int:meal_id>/save-to-my-meals", methods=["POST"])
@login_required
@role_required("user")
def save_to_my_meals(meal_id: int):
    source_meal = db.session.get(MealLog, meal_id)
    if not source_meal:
        abort(404)

    if source_meal.user_id == current_user.id:
        flash("This meal is already in your personal logs.", "info")
        return redirect(url_for("meal.my_meal_logs"))

    copied_meal = MealLog(
        user_id=current_user.id,
        image_url=source_meal.image_url,
        cloudinary_public_id=None,
        meal_type=source_meal.meal_type,
        meal_date=source_meal.meal_date,
        title=source_meal.title,
        note=source_meal.note,
        calories=source_meal.calories,
        protein=source_meal.protein,
        carbohydrates=source_meal.carbohydrates,
        fats=source_meal.fats,
    )

    try:
        db.session.add(copied_meal)
        db.session.commit()
        flash("Meal copied to your personal meal logs.", "success")
    except Exception:
        db.session.rollback()
        flash("Could not save this meal to your personal logs.", "danger")

    return redirect(url_for("meal.my_meal_logs"))


@meal_bp.route("/menu-item/<int:item_id>/add-to-my-meals", methods=["POST"])
@login_required
@role_required("user")
def add_vendor_item_to_my_meals(item_id: int):
    item = db.session.get(MenuItem, item_id)
    if not item or not item.vendor or not item.vendor.is_active or not item.is_available:
        abort(404)

    meal_type = (request.form.get("meal_type") or "").strip().lower()
    meal_date = _parse_meal_date((request.form.get("meal_date") or "").strip())

    if meal_type not in ALLOWED_MEAL_TYPES:
        flash("Meal type must be breakfast, lunch, dinner, or snack.", "danger")
        return _safe_redirect_url("vendor.menu_item_detail", item_id=item.id)

    if not meal_date:
        flash("Please provide a valid meal date.", "danger")
        return _safe_redirect_url("vendor.menu_item_detail", item_id=item.id)

    try:
        db.session.add(_build_meal_log_from_vendor_item(item, meal_type, meal_date))
        db.session.commit()
        flash(f"{item.name} was added to your meal logs.", "success")
    except Exception as exc:
        db.session.rollback()
        current_app.logger.exception(
            "Failed to add vendor menu item %s to meal logs for user %s: %s",
            item.id,
            current_user.id,
            exc,
        )
        flash("Could not add this vendor item to your meal logs right now. Please try again.", "danger")

    return _safe_redirect_url("vendor.menu_item_detail", item_id=item.id)


@meal_bp.route("/edit-meal/<int:meal_id>", methods=["GET", "POST"])
@login_required
@role_required("user", "admin")
def edit_meal(meal_id):
    meal = db.session.get(MealLog, meal_id)
    if not meal:
        abort(404)

    if not _can_modify_meal(meal):
        flash("You can edit only your own meal logs.", "danger")
        return redirect(url_for("meal.meal_detail", meal_id=meal.id))

    if request.method == "GET":
        return render_template("meals/edit_meal.html", meal=meal, meal_types=sorted(ALLOWED_MEAL_TYPES))

    meal_type = (request.form.get("meal_type") or "").strip().lower()
    meal_date_raw = (request.form.get("meal_date") or "").strip()
    title = (request.form.get("title") or "").strip() or None
    note = (request.form.get("note") or "").strip() or None
    new_image = request.files.get("image")

    if meal_type not in ALLOWED_MEAL_TYPES:
        flash("Meal type must be breakfast, lunch, dinner, or snack.", "danger")
        return render_template("meals/edit_meal.html", meal=meal, meal_types=sorted(ALLOWED_MEAL_TYPES)), 400

    meal_date = _parse_meal_date(meal_date_raw)
    if not meal_date:
        flash("Please provide a valid meal date.", "danger")
        return render_template("meals/edit_meal.html", meal=meal, meal_types=sorted(ALLOWED_MEAL_TYPES)), 400

    old_public_id = meal.cloudinary_public_id
    old_image_url = meal.image_url
    new_public_id = None
    temp_path = None

    try:
        meal.meal_type = meal_type
        meal.meal_date = meal_date
        meal.title = title
        meal.note = note

        if new_image and new_image.filename:
            if not _allowed_file(new_image.filename):
                flash("Only image files are allowed (png, jpg, jpeg, webp, gif).", "danger")
                return render_template("meals/edit_meal.html", meal=meal, meal_types=sorted(ALLOWED_MEAL_TYPES)), 400

            if not _looks_like_image(new_image):
                flash("Uploaded file is not recognized as an image.", "danger")
                return render_template("meals/edit_meal.html", meal=meal, meal_types=sorted(ALLOWED_MEAL_TYPES)), 400

            temp_path = _save_temp_file(new_image)
            new_image_url, new_public_id = upload_image(temp_path, folder="meal_logs")

            meal.image_url = new_image_url
            meal.cloudinary_public_id = new_public_id

        db.session.commit()

        if (
            new_public_id
            and old_public_id
            and old_public_id != new_public_id
            and not _image_referenced_by_others(old_image_url, meal.id)
        ):
            try:
                delete_image(old_public_id)
            except Exception:
                flash("Meal updated, but old Cloudinary image could not be removed.", "warning")

        flash("Meal log updated successfully.", "success")
        return redirect(url_for("meal.meal_detail", meal_id=meal.id))
    except RuntimeError as exc:
        db.session.rollback()
        current_app.logger.warning("Update blocked: %s", exc)
        flash(str(exc), "danger")
        return render_template("meals/edit_meal.html", meal=meal, meal_types=sorted(ALLOWED_MEAL_TYPES)), 500
    except Exception as exc:
        db.session.rollback()
        if new_public_id:
            try:
                delete_image(new_public_id)
            except Exception:
                pass
        current_app.logger.exception("Failed to update meal log: %s", exc)
        flash("Failed to update meal log. Please try again.", "danger")
        return render_template("meals/edit_meal.html", meal=meal, meal_types=sorted(ALLOWED_MEAL_TYPES)), 500
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


@meal_bp.route("/delete-meal/<int:meal_id>", methods=["POST"])
@login_required
@role_required("user", "admin")
def delete_meal(meal_id):
    meal = db.session.get(MealLog, meal_id)
    if not meal:
        abort(404)

    if not _can_modify_meal(meal):
        flash("You can delete only your own meal logs.", "danger")
        return redirect(url_for("meal.meal_detail", meal_id=meal.id))

    public_id = meal.cloudinary_public_id
    meal_image_url = meal.image_url
    try:
        db.session.delete(meal)
        db.session.commit()

        if public_id and not _image_referenced_by_others(meal_image_url, meal.id):
            try:
                delete_image(public_id)
            except Exception:
                flash("Meal deleted, but Cloudinary image removal failed.", "warning")

        flash("Meal log deleted successfully.", "success")
    except Exception as exc:
        db.session.rollback()
        current_app.logger.exception("Failed to delete meal log: %s", exc)
        flash("Failed to delete meal log. Please try again.", "danger")

    if current_user.role == "admin":
        return redirect(url_for("admin.admin_meal_logs"))

    return redirect(url_for("meal.my_meal_logs"))
