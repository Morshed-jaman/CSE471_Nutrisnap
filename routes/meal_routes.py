import os
import tempfile
from datetime import datetime

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from werkzeug.utils import secure_filename

from extensions import db
from models import MealLog
from services.cloudinary_service import delete_image, upload_image

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
def home():
    return render_template("home.html")


@meal_bp.route("/upload-meal", methods=["GET", "POST"])
def upload_meal():
    if request.method == "GET":
        return render_template("upload_meal.html", meal_types=sorted(ALLOWED_MEAL_TYPES))

    image_file = request.files.get("image")
    meal_type = (request.form.get("meal_type") or "").strip().lower()
    meal_date_raw = (request.form.get("meal_date") or "").strip()
    title = (request.form.get("title") or "").strip() or None
    note = (request.form.get("note") or "").strip() or None

    if not image_file or not image_file.filename:
        flash("Please select an image to upload.", "danger")
        return render_template("upload_meal.html", meal_types=sorted(ALLOWED_MEAL_TYPES)), 400

    if not _allowed_file(image_file.filename):
        flash("Only image files are allowed (png, jpg, jpeg, webp, gif).", "danger")
        return render_template("upload_meal.html", meal_types=sorted(ALLOWED_MEAL_TYPES)), 400

    if not _looks_like_image(image_file):
        flash("Uploaded file is not recognized as an image.", "danger")
        return render_template("upload_meal.html", meal_types=sorted(ALLOWED_MEAL_TYPES)), 400

    if meal_type not in ALLOWED_MEAL_TYPES:
        flash("Meal type must be breakfast, lunch, dinner, or snack.", "danger")
        return render_template("upload_meal.html", meal_types=sorted(ALLOWED_MEAL_TYPES)), 400

    meal_date = _parse_meal_date(meal_date_raw)
    if not meal_date:
        flash("Please provide a valid meal date.", "danger")
        return render_template("upload_meal.html", meal_types=sorted(ALLOWED_MEAL_TYPES)), 400

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
        return render_template("upload_meal.html", meal_types=sorted(ALLOWED_MEAL_TYPES)), 500
    except Exception as exc:
        db.session.rollback()
        current_app.logger.exception("Failed to save meal log: %s", exc)
        flash("Failed to save meal log. Please try again.", "danger")
        return render_template("upload_meal.html", meal_types=sorted(ALLOWED_MEAL_TYPES)), 500
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


@meal_bp.route("/meal-logs")
def meal_logs():
    logs = MealLog.query.order_by(MealLog.created_at.desc()).all()
    return render_template("meal_logs.html", logs=logs)


@meal_bp.route("/meal-log/<int:meal_id>")
def meal_detail(meal_id):
    meal = db.session.get(MealLog, meal_id)
    if not meal:
        abort(404)
    return render_template("meal_detail.html", meal=meal)


@meal_bp.route("/edit-meal/<int:meal_id>", methods=["GET", "POST"])
def edit_meal(meal_id):
    meal = db.session.get(MealLog, meal_id)
    if not meal:
        abort(404)

    if request.method == "GET":
        return render_template("edit_meal.html", meal=meal, meal_types=sorted(ALLOWED_MEAL_TYPES))

    meal_type = (request.form.get("meal_type") or "").strip().lower()
    meal_date_raw = (request.form.get("meal_date") or "").strip()
    title = (request.form.get("title") or "").strip() or None
    note = (request.form.get("note") or "").strip() or None
    new_image = request.files.get("image")

    if meal_type not in ALLOWED_MEAL_TYPES:
        flash("Meal type must be breakfast, lunch, dinner, or snack.", "danger")
        return render_template("edit_meal.html", meal=meal, meal_types=sorted(ALLOWED_MEAL_TYPES)), 400

    meal_date = _parse_meal_date(meal_date_raw)
    if not meal_date:
        flash("Please provide a valid meal date.", "danger")
        return render_template("edit_meal.html", meal=meal, meal_types=sorted(ALLOWED_MEAL_TYPES)), 400

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
                return render_template("edit_meal.html", meal=meal, meal_types=sorted(ALLOWED_MEAL_TYPES)), 400

            if not _looks_like_image(new_image):
                flash("Uploaded file is not recognized as an image.", "danger")
                return render_template("edit_meal.html", meal=meal, meal_types=sorted(ALLOWED_MEAL_TYPES)), 400

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
        return render_template("edit_meal.html", meal=meal, meal_types=sorted(ALLOWED_MEAL_TYPES)), 500
    except Exception as exc:
        db.session.rollback()
        if new_public_id:
            try:
                delete_image(new_public_id)
            except Exception:
                pass
        current_app.logger.exception("Failed to update meal log: %s", exc)
        flash("Failed to update meal log. Please try again.", "danger")
        return render_template("edit_meal.html", meal=meal, meal_types=sorted(ALLOWED_MEAL_TYPES)), 500
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
