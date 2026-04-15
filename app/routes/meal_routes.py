import os
import tempfile
from datetime import datetime, timedelta

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from sqlalchemy import func, or_
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models import MealLog, MenuItem, Vendor
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


def _save_temp_file(file_storage):
    original_name = secure_filename(file_storage.filename or "upload")
    suffix = os.path.splitext(original_name)[1] or ".jpg"
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    temp_file.close()
    file_storage.save(temp_file.name)
    return temp_file.name


@meal_bp.route("/")
def landing():
    return render_template("landing.html")


def _home_page_context():
    total_meal_logs = db.session.query(func.count(MealLog.id)).scalar() or 0
    meals_with_nutrition = (
        db.session.query(func.count(MealLog.id))
        .filter(
            or_(
                MealLog.calories.isnot(None),
                MealLog.protein.isnot(None),
                MealLog.carbohydrates.isnot(None),
                MealLog.fats.isnot(None),
            )
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
        .filter(MealLog.created_at >= datetime.utcnow() - timedelta(days=7))
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
        MealLog.query.order_by(MealLog.meal_date.desc(), MealLog.created_at.desc()).limit(6).all()
    )
    featured_vendors = (
        Vendor.query.filter(Vendor.is_active.is_(True))
        .order_by(Vendor.created_at.desc())
        .limit(6)
        .all()
    )
    nutrition_ready_meals = (
        MealLog.query.filter(
            or_(
                MealLog.calories.isnot(None),
                MealLog.protein.isnot(None),
                MealLog.carbohydrates.isnot(None),
                MealLog.fats.isnot(None),
            )
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


@meal_bp.route("/home")
def home():
    return render_template("home.html", **_home_page_context())


@meal_bp.route("/upload-meal", methods=["GET", "POST"])
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
        image_url, public_id = upload_image(temp_path)

        meal_log = MealLog(
            image_url=image_url,
            cloudinary_public_id=public_id,
            meal_type=meal_type,
            meal_date=meal_date,
            title=title,
            note=note,
        )
        db.session.add(meal_log)
        db.session.commit()
        flash("Meal log saved successfully.", "success")
        return redirect(url_for("meal.meal_logs"))
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


@meal_bp.route("/meal-logs")
def meal_logs():
    logs = MealLog.query.order_by(MealLog.created_at.desc()).all()
    return render_template("meals/meal_logs.html", logs=logs)


@meal_bp.route("/meal-log/<int:meal_id>")
def meal_detail(meal_id):
    meal = db.session.get(MealLog, meal_id)
    if not meal:
        abort(404)

    meal_insights = []
    if any(value is not None for value in [meal.calories, meal.protein, meal.carbohydrates, meal.fats]):
        meal_insights = get_nutrition_insights(
            meal.calories, meal.protein, meal.carbohydrates, meal.fats
        )

    return render_template("meals/meal_detail.html", meal=meal, meal_insights=meal_insights)


@meal_bp.route("/edit-meal/<int:meal_id>", methods=["GET", "POST"])
def edit_meal(meal_id):
    meal = db.session.get(MealLog, meal_id)
    if not meal:
        abort(404)

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
            new_image_url, new_public_id = upload_image(temp_path)

            meal.image_url = new_image_url
            meal.cloudinary_public_id = new_public_id

        db.session.commit()

        if new_public_id and old_public_id and old_public_id != new_public_id:
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
def delete_meal(meal_id):
    meal = db.session.get(MealLog, meal_id)
    if not meal:
        abort(404)

    public_id = meal.cloudinary_public_id
    try:
        db.session.delete(meal)
        db.session.commit()

        if public_id:
            try:
                delete_image(public_id)
            except Exception:
                flash("Meal deleted, but Cloudinary image removal failed.", "warning")

        flash("Meal log deleted successfully.", "success")
    except Exception as exc:
        db.session.rollback()
        current_app.logger.exception("Failed to delete meal log: %s", exc)
        flash("Failed to delete meal log. Please try again.", "danger")

    return redirect(url_for("meal.meal_logs"))
