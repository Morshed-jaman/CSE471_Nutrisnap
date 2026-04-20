import os
import tempfile

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models import User, Vendor, VendorProfile
from app.services.auth_service import redirect_for_role, role_required
from app.services.cloudinary_service import delete_image, upload_image

auth_bp = Blueprint("auth", __name__)


def _normalized_email(raw_email: str) -> str:
    return (raw_email or "").strip().lower()


def _safe_next_url() -> str | None:
    next_url = (request.args.get("next") or request.form.get("next") or "").strip()
    if not next_url:
        return None
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


def _clean_text(raw_value: str | None) -> str:
    return (raw_value or "").strip()


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


def _update_password_if_requested(user: User) -> bool:
    current_password = (request.form.get("current_password") or "").strip()
    new_password = (request.form.get("new_password") or "").strip()
    confirm_new_password = (request.form.get("confirm_new_password") or "").strip()

    if not any([current_password, new_password, confirm_new_password]):
        return True

    if not current_password:
        flash("Current password is required to set a new password.", "danger")
        return False

    if not user.check_password(current_password):
        flash("Current password is incorrect.", "danger")
        return False

    errors = _password_errors(new_password, confirm_new_password)
    if errors:
        for error in errors:
            flash(error, "danger")
        return False

    user.set_password(new_password)
    return True


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

    if user.role == "vendor" and user.vendor_status == "rejected":
        flash("Your vendor account has been rejected. Contact admin for details.", "danger")
        return render_template("auth/login.html", email=email, next_url=next_url), 403

    login_user(user)

    if user.role == "vendor" and user.vendor_status == "pending":
        flash("Vendor account submitted. Please wait for admin approval.", "info")
        return redirect(url_for("auth.vendor_pending"))

    if user.role == "admin":
        return redirect(url_for("admin.admin_dashboard"))

    if user.role == "vendor":
        return redirect(url_for("vendor.vendor_dashboard"))

    if user.role == "nutrition_expert":
        if user.expert_status == "approved":
            return redirect(url_for("advice.expert_advice_dashboard"))
        flash("Nutrition expert account submitted. Please wait for admin verification.", "info")
        return redirect(url_for("auth.expert_pending"))

    if next_url:
        return redirect(next_url)

    return redirect(url_for("meal.home"))


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
        user = User(
            name=name,
            email=email,
            phone=phone,
            role="user",
            is_active=True,
            is_subscribed=False,
            vendor_status=None,
            expert_status=None,
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        flash("Registration successful. Please log in.", "success")
        return redirect(url_for("auth.login"))
    except Exception:
        db.session.rollback()
        flash("Failed to register account. Please try again.", "danger")
        return render_template("auth/register.html", form=request.form), 500


@auth_bp.route("/nutrition-expert/register", methods=["GET", "POST"])
def nutrition_expert_register():
    if current_user.is_authenticated:
        return redirect(redirect_for_role(current_user))

    if request.method == "GET":
        return render_template("auth/nutrition_expert_register.html")

    name = _clean_text(request.form.get("name"))
    email = _normalized_email(request.form.get("email"))
    phone = _clean_text(request.form.get("phone"))
    password = _clean_text(request.form.get("password"))
    confirm_password = _clean_text(request.form.get("confirm_password"))
    credentials = _clean_text(request.form.get("expert_credentials"))

    if not all([name, email, phone, password, confirm_password, credentials]):
        flash("Please fill all required fields.", "danger")
        return render_template("auth/nutrition_expert_register.html", form=request.form), 400

    if len(credentials) < 20:
        flash("Please provide a brief credentials summary (at least 20 characters).", "danger")
        return render_template("auth/nutrition_expert_register.html", form=request.form), 400

    if "@" not in email:
        flash("Please provide a valid email address.", "danger")
        return render_template("auth/nutrition_expert_register.html", form=request.form), 400

    if User.query.filter_by(email=email).first():
        flash("Email already exists. Please log in instead.", "danger")
        return render_template("auth/nutrition_expert_register.html", form=request.form), 409

    password_issues = _password_errors(password, confirm_password)
    if password_issues:
        for issue in password_issues:
            flash(issue, "danger")
        return render_template("auth/nutrition_expert_register.html", form=request.form), 400

    try:
        user = User(
            name=name,
            email=email,
            phone=phone,
            role="nutrition_expert",
            is_active=True,
            is_subscribed=False,
            expert_status="pending",
            expert_credentials=credentials,
            vendor_status=None,
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        flash(
            "Nutrition expert registration submitted. Please wait for admin verification.",
            "success",
        )
        return redirect(url_for("auth.login"))
    except Exception:
        db.session.rollback()
        flash("Failed to submit nutrition expert registration. Please try again.", "danger")
        return render_template("auth/nutrition_expert_register.html", form=request.form), 500


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
    verification_note = (request.form.get("verification_note") or "").strip() or None

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

    cover_image_file = request.files.get("cover_image_file")
    cover_cloudinary_public_id = None
    temp_path = None

    try:
        if cover_image_file and cover_image_file.filename:
            if not _allowed_file(cover_image_file.filename):
                flash("Only image files are allowed (png, jpg, jpeg, webp, gif).", "danger")
                return render_template("auth/vendor_register.html", form=request.form), 400

            if not _looks_like_image(cover_image_file):
                flash("Uploaded vendor cover is not recognized as an image.", "danger")
                return render_template("auth/vendor_register.html", form=request.form), 400

            temp_path = _save_temp_file(cover_image_file)
            cover_image_url, cover_cloudinary_public_id = upload_image(
                temp_path, folder="vendor_covers"
            )

        user = User(
            name=name,
            email=email,
            phone=phone,
            role="vendor",
            is_active=True,
            is_subscribed=False,
            vendor_status="pending",
            expert_status=None,
        )
        user.set_password(password)
        db.session.add(user)
        db.session.flush()

        vendor_profile = VendorProfile(
            user_id=user.id,
            business_name=business_name,
            business_category=business_category,
            business_address=business_address,
            business_description=business_description,
            cover_image_url=cover_image_url,
            cover_cloudinary_public_id=cover_cloudinary_public_id,
            verification_note=verification_note,
            approval_status="pending",
        )
        db.session.add(vendor_profile)
        db.session.commit()

        flash(
            "Vendor registration submitted. Please wait for admin verification before vendor access.",
            "success",
        )
        return redirect(url_for("auth.login"))
    except Exception:
        db.session.rollback()
        if cover_cloudinary_public_id:
            try:
                delete_image(cover_cloudinary_public_id)
            except Exception:
                pass
        flash("Failed to submit vendor registration. Please try again.", "danger")
        return render_template("auth/vendor_register.html", form=request.form), 500
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


@auth_bp.route("/vendor/pending")
@login_required
@role_required("vendor")
def vendor_pending():
    if current_user.vendor_status == "approved":
        return redirect(url_for("vendor.vendor_dashboard"))

    return render_template(
        "auth/pending_vendor.html",
        vendor_status=current_user.vendor_status or "pending",
        vendor_profile=current_user.vendor_profile,
    )


@auth_bp.route("/nutrition-expert/pending")
@login_required
@role_required("nutrition_expert")
def expert_pending():
    if current_user.expert_status == "approved":
        return redirect(url_for("advice.expert_advice_dashboard"))

    return render_template(
        "auth/pending_expert.html",
        expert_status=current_user.expert_status or "pending",
        expert_review_note=current_user.expert_review_note,
    )


@auth_bp.route("/logout", methods=["GET", "POST"])
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "success")
    return redirect(url_for("auth.login"))


@auth_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    if current_user.role == "vendor":
        return redirect(url_for("auth.vendor_profile"))
    if current_user.role == "nutrition_expert":
        return redirect(url_for("auth.nutrition_expert_profile"))
    if current_user.role == "admin":
        return redirect(url_for("auth.admin_profile"))
    return redirect(url_for("auth.user_profile"))


@auth_bp.route("/user/profile", methods=["GET", "POST"])
@login_required
@role_required("user")
def user_profile():
    if request.method == "GET":
        return render_template("profile/profile.html", mode="user")

    name = (request.form.get("name") or "").strip()
    phone = (request.form.get("phone") or "").strip()

    if not name or not phone:
        flash("Name and phone are required.", "danger")
        return render_template("profile/profile.html", mode="user"), 400

    try:
        current_user.name = name
        current_user.phone = phone

        if not _update_password_if_requested(current_user):
            return render_template("profile/profile.html", mode="user"), 400

        db.session.commit()
        flash("Profile updated successfully.", "success")
        return redirect(url_for("auth.user_profile"))
    except Exception:
        db.session.rollback()
        flash("Failed to update profile.", "danger")
        return render_template("profile/profile.html", mode="user"), 500


@auth_bp.route("/vendor/profile", methods=["GET", "POST"])
@login_required
@role_required("vendor")
def vendor_profile():
    profile_data = current_user.vendor_profile
    if request.method == "GET":
        return render_template(
            "profile/vendor_profile.html",
            profile_data=profile_data,
            approval_status=current_user.vendor_status or "pending",
        )

    name = (request.form.get("name") or "").strip()
    phone = (request.form.get("phone") or "").strip()
    business_name = (request.form.get("business_name") or "").strip()
    business_category = (request.form.get("business_category") or "").strip()
    business_address = (request.form.get("business_address") or "").strip()
    business_description = (request.form.get("business_description") or "").strip() or None
    cover_image_url = (request.form.get("cover_image_url") or "").strip() or None
    verification_note = (request.form.get("verification_note") or "").strip() or None

    if not all([name, phone, business_name, business_category, business_address]):
        flash("Please fill all required profile fields.", "danger")
        return render_template(
            "profile/vendor_profile.html",
            profile_data=profile_data,
            approval_status=current_user.vendor_status or "pending",
        ), 400

    cover_image_file = request.files.get("cover_image_file")
    old_cover_public_id = profile_data.cover_cloudinary_public_id if profile_data else None
    new_cover_public_id = None
    temp_path = None
    should_cleanup_old_cover = False

    try:
        current_user.name = name
        current_user.phone = phone

        if not _update_password_if_requested(current_user):
            return render_template(
                "profile/vendor_profile.html",
                profile_data=profile_data,
                approval_status=current_user.vendor_status or "pending",
            ), 400

        if not profile_data:
            profile_data = VendorProfile(user_id=current_user.id)
            db.session.add(profile_data)

        profile_data.business_name = business_name
        profile_data.business_category = business_category
        profile_data.business_address = business_address
        profile_data.business_description = business_description
        profile_data.verification_note = verification_note

        if cover_image_file and cover_image_file.filename:
            if not _allowed_file(cover_image_file.filename):
                flash("Only image files are allowed (png, jpg, jpeg, webp, gif).", "danger")
                return render_template(
                    "profile/vendor_profile.html",
                    profile_data=profile_data,
                    approval_status=current_user.vendor_status or "pending",
                ), 400

            if not _looks_like_image(cover_image_file):
                flash("Uploaded vendor cover is not recognized as an image.", "danger")
                return render_template(
                    "profile/vendor_profile.html",
                    profile_data=profile_data,
                    approval_status=current_user.vendor_status or "pending",
                ), 400

            temp_path = _save_temp_file(cover_image_file)
            new_cover_url, new_cover_public_id = upload_image(temp_path, folder="vendor_covers")
            profile_data.cover_image_url = new_cover_url
            profile_data.cover_cloudinary_public_id = new_cover_public_id
            should_cleanup_old_cover = bool(old_cover_public_id and old_cover_public_id != new_cover_public_id)
        elif cover_image_url:
            if profile_data.cover_cloudinary_public_id:
                should_cleanup_old_cover = True
            profile_data.cover_image_url = cover_image_url
            profile_data.cover_cloudinary_public_id = None

        vendor = Vendor.query.filter_by(owner_user_id=current_user.id).first()
        if vendor:
            vendor.name = business_name
            vendor.category = business_category
            vendor.address = business_address
            vendor.description = business_description
            vendor.phone = phone
            vendor.contact_email = current_user.email
            vendor.image_url = profile_data.cover_image_url

        db.session.commit()

        if should_cleanup_old_cover and old_cover_public_id:
            try:
                delete_image(old_cover_public_id)
            except Exception:
                flash("Profile updated, but old cover image cleanup failed.", "warning")

        flash("Vendor profile updated successfully.", "success")
        return redirect(url_for("auth.vendor_profile"))
    except Exception:
        db.session.rollback()
        if new_cover_public_id:
            try:
                delete_image(new_cover_public_id)
            except Exception:
                pass
        flash("Failed to update vendor profile.", "danger")
        return render_template(
            "profile/vendor_profile.html",
            profile_data=profile_data,
            approval_status=current_user.vendor_status or "pending",
        ), 500
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


@auth_bp.route("/nutrition-expert/profile", methods=["GET", "POST"])
@login_required
@role_required("nutrition_expert")
def nutrition_expert_profile():
    if request.method == "GET":
        return render_template(
            "profile/nutrition_expert_profile.html",
            expert_status=current_user.expert_status or "pending",
        )

    name = _clean_text(request.form.get("name"))
    phone = _clean_text(request.form.get("phone"))
    expert_credentials = _clean_text(request.form.get("expert_credentials"))

    if not name or not phone:
        flash("Name and phone are required.", "danger")
        return render_template(
            "profile/nutrition_expert_profile.html",
            expert_status=current_user.expert_status or "pending",
        ), 400

    if not expert_credentials:
        flash("Credentials summary is required.", "danger")
        return render_template(
            "profile/nutrition_expert_profile.html",
            expert_status=current_user.expert_status or "pending",
        ), 400

    try:
        current_user.name = name
        current_user.phone = phone
        current_user.expert_credentials = expert_credentials

        if not _update_password_if_requested(current_user):
            return render_template(
                "profile/nutrition_expert_profile.html",
                expert_status=current_user.expert_status or "pending",
            ), 400

        if current_user.expert_status == "rejected":
            current_user.expert_status = "pending"
            flash("Profile updated and resubmitted for admin review.", "info")
        else:
            flash("Nutrition expert profile updated successfully.", "success")

        db.session.commit()
        return redirect(url_for("auth.nutrition_expert_profile"))
    except Exception:
        db.session.rollback()
        flash("Failed to update nutrition expert profile.", "danger")
        return render_template(
            "profile/nutrition_expert_profile.html",
            expert_status=current_user.expert_status or "pending",
        ), 500


@auth_bp.route("/user/subscription/activate", methods=["POST"])
@login_required
@role_required("user")
def activate_subscription():
    if current_user.is_subscribed:
        flash("You already have an active subscription.", "info")
        return redirect(url_for("auth.user_profile"))

    try:
        current_user.is_subscribed = True
        db.session.commit()
        flash("Subscription activated. Nutritionist Advice is now available.", "success")
    except Exception:
        db.session.rollback()
        flash("Could not activate subscription right now. Please try again.", "danger")

    return redirect(url_for("auth.user_profile"))


@auth_bp.route("/user/subscription/cancel", methods=["POST"])
@login_required
@role_required("user")
def cancel_subscription():
    if not current_user.is_subscribed:
        flash("No active subscription found.", "info")
        return redirect(url_for("auth.user_profile"))

    try:
        current_user.is_subscribed = False
        db.session.commit()
        flash("Subscription cancelled successfully.", "success")
    except Exception:
        db.session.rollback()
        flash("Could not cancel subscription right now. Please try again.", "danger")

    return redirect(url_for("auth.user_profile"))


@auth_bp.route("/admin/profile", methods=["GET", "POST"])
@login_required
@role_required("admin")
def admin_profile():
    if request.method == "GET":
        return render_template("profile/admin_profile.html")

    name = (request.form.get("name") or "").strip()
    phone = (request.form.get("phone") or "").strip()
    if not name or not phone:
        flash("Name and phone are required.", "danger")
        return render_template("profile/admin_profile.html"), 400

    try:
        current_user.name = name
        current_user.phone = phone

        if not _update_password_if_requested(current_user):
            return render_template("profile/admin_profile.html"), 400

        db.session.commit()
        flash("Admin profile updated successfully.", "success")
        return redirect(url_for("auth.admin_profile"))
    except Exception:
        db.session.rollback()
        flash("Failed to update admin profile.", "danger")
        return render_template("profile/admin_profile.html"), 500
