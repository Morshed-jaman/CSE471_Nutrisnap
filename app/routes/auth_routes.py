import os
import tempfile

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models import User, Vendor
from app.services.auth_service import redirect_for_role
from app.services.cloudinary_service import upload_image

auth_bp = Blueprint("auth", __name__)


def _normalized_email(raw_email: str) -> str:
    return (raw_email or "").strip().lower()


def _safe_next_url() -> str | None:
    next_url = (request.args.get("next") or request.form.get("next") or "").strip()
    if next_url.startswith("/") and not next_url.startswith("//"):
        return next_url
    return None


def _password_errors(password: str, confirm_password: str) -> list[str]:
    errors = []
    if len(password) < 8:
        errors.append("Password must be at least 8 characters long.")
    if password != confirm_password:
        errors.append("Password and confirm password do not match.")
    return errors


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


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(redirect_for_role(current_user))

    if request.method == "GET":
        return render_template("auth/login.html", next_url=_safe_next_url())

    email = _normalized_email(request.form.get("email"))
    password = (request.form.get("password") or "").strip()
    next_url = _safe_next_url()

    if not email or not password:
        flash("Email and password are required.", "danger")
        return render_template("auth/login.html", email=email, next_url=next_url), 400

    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        flash("Invalid email or password.", "danger")
        return render_template("auth/login.html", email=email, next_url=next_url), 401

    if not user.is_active:
        flash("Your account is inactive. Contact support.", "danger")
        return render_template("auth/login.html", email=email, next_url=next_url), 403

    login_user(user)
    return redirect(next_url or redirect_for_role(user))


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(redirect_for_role(current_user))

    if request.method == "GET":
        return render_template("auth/register.html")

    name = (request.form.get("name") or "").strip()
    email = _normalized_email(request.form.get("email"))
    phone = (request.form.get("phone") or "").strip()
    password = (request.form.get("password") or "").strip()
    confirm_password = (request.form.get("confirm_password") or "").strip()

    if not all([name, email, phone, password, confirm_password]):
        flash("All fields are required.", "danger")
        return render_template("auth/register.html", form=request.form), 400

    if "@" not in email:
        flash("Please provide a valid email address.", "danger")
        return render_template("auth/register.html", form=request.form), 400

    if User.query.filter_by(email=email).first():
        flash("Email already exists. Please log in instead.", "danger")
        return render_template("auth/register.html", form=request.form), 409

    password_issues = _password_errors(password, confirm_password)
    if password_issues:
        for issue in password_issues:
            flash(issue, "danger")
        return render_template("auth/register.html", form=request.form), 400

    try:
        user = User(name=name, email=email, phone=phone, role="user", is_active=True)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash("Registration successful. Please log in.", "success")
        return redirect(url_for("auth.login"))
    except Exception:
        db.session.rollback()
        flash("Failed to register account. Please try again.", "danger")
        return render_template("auth/register.html", form=request.form), 500


@auth_bp.route("/vendor/register", methods=["GET", "POST"])
def vendor_register():
    if current_user.is_authenticated:
        return redirect(redirect_for_role(current_user))

    if request.method == "GET":
        return render_template("auth/vendor_register.html")

    name = (request.form.get("name") or "").strip()
    email = _normalized_email(request.form.get("email"))
    phone = (request.form.get("phone") or "").strip()
    password = (request.form.get("password") or "").strip()
    confirm_password = (request.form.get("confirm_password") or "").strip()
    business_name = (request.form.get("business_name") or "").strip()
    business_category = (request.form.get("business_category") or "").strip()
    business_address = (request.form.get("business_address") or "").strip()
    business_description = (request.form.get("business_description") or "").strip() or None
    cover_image_url = (request.form.get("cover_image_url") or "").strip() or None

    required_fields = [
        name,
        email,
        phone,
        password,
        confirm_password,
        business_name,
        business_category,
        business_address,
    ]
    if not all(required_fields):
        flash("Please fill all required fields.", "danger")
        return render_template("auth/vendor_register.html", form=request.form), 400

    if "@" not in email:
        flash("Please provide a valid email address.", "danger")
        return render_template("auth/vendor_register.html", form=request.form), 400

    if User.query.filter_by(email=email).first():
        flash("Email already exists. Please log in instead.", "danger")
        return render_template("auth/vendor_register.html", form=request.form), 409

    password_issues = _password_errors(password, confirm_password)
    if password_issues:
        for issue in password_issues:
            flash(issue, "danger")
        return render_template("auth/vendor_register.html", form=request.form), 400

    temp_path = None
    image_file = request.files.get("cover_image_file")

    try:
        if image_file and image_file.filename:
            if not _allowed_file(image_file.filename):
                flash("Only image files are allowed (png, jpg, jpeg, webp, gif).", "danger")
                return render_template("auth/vendor_register.html", form=request.form), 400

            if not _looks_like_image(image_file):
                flash("Uploaded vendor cover is not recognized as an image.", "danger")
                return render_template("auth/vendor_register.html", form=request.form), 400

            temp_path = _save_temp_file(image_file)
            cover_image_url, _ = upload_image(temp_path, folder="vendor_covers")

        user = User(name=name, email=email, phone=phone, role="vendor", is_active=True)
        user.set_password(password)
        db.session.add(user)
        db.session.flush()

        vendor = Vendor(
            owner_user_id=user.id,
            name=business_name,
            category=business_category,
            description=business_description,
            image_url=cover_image_url,
            contact_email=email,
            phone=phone,
            address=business_address,
            is_active=True,
        )
        db.session.add(vendor)
        db.session.commit()
        flash("Vendor registration successful. Please log in.", "success")
        return redirect(url_for("auth.login"))
    except Exception:
        db.session.rollback()
        flash("Failed to register vendor account. Please try again.", "danger")
        return render_template("auth/vendor_register.html", form=request.form), 500
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


@auth_bp.route("/logout", methods=["GET", "POST"])
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "success")
    return redirect(url_for("auth.login"))
