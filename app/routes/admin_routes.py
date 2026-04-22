from datetime import datetime

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_user
from sqlalchemy import or_

from app.extensions import db
from app.models import MealLog, MenuItem, Review, User, Vendor
from app.services.auth_service import admin_required, redirect_for_role
from app.services.cloudinary_service import delete_image

admin_bp = Blueprint("admin", __name__)


def _normalized_email(raw_email: str) -> str:
    return (raw_email or "").strip().lower()


def _safe_next_url() -> str | None:
    next_url = (request.args.get("next") or request.form.get("next") or "").strip()
    if next_url.startswith("/") and not next_url.startswith("//"):
        return next_url
    return None


@admin_bp.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if current_user.is_authenticated:
        return redirect(redirect_for_role(current_user))

    if request.method == "GET":
        return render_template("admin/admin_login.html", next_url=_safe_next_url())

    email = _normalized_email(request.form.get("email"))
    password = (request.form.get("password") or "").strip()
    next_url = _safe_next_url()

    if not email or not password:
        flash("Email and password are required.", "danger")
        return render_template("admin/admin_login.html", email=email, next_url=next_url), 400

    user = User.query.filter_by(email=email, role="admin").first()
    if not user or not user.check_password(password):
        flash("Invalid admin credentials.", "danger")
        return render_template("admin/admin_login.html", email=email, next_url=next_url), 401

    if not user.is_active:
        flash("Admin account is inactive.", "danger")
        return render_template("admin/admin_login.html", email=email, next_url=next_url), 403

    login_user(user)
    if next_url:
        return redirect(next_url)
    return redirect(url_for("admin.admin_dashboard"))


@admin_bp.route("/admin")
@admin_required
def admin_dashboard():
    total_users = User.query.filter_by(role="user").count()
    total_vendors = User.query.filter_by(role="vendor").count()
    pending_vendors = User.query.filter_by(role="vendor", vendor_status="pending").count()
    approved_vendors = User.query.filter_by(role="vendor", vendor_status="approved").count()
    rejected_vendors = User.query.filter_by(role="vendor", vendor_status="rejected").count()
    pending_experts = User.query.filter_by(role="nutrition_expert", expert_status="pending").count()
    approved_experts = User.query.filter_by(role="nutrition_expert", expert_status="approved").count()
    rejected_experts = User.query.filter_by(role="nutrition_expert", expert_status="rejected").count()

    total_meal_logs = MealLog.query.count()
    nutrition_ready_meals = MealLog.query.filter(
        or_(
            MealLog.calories.isnot(None),
            MealLog.protein.isnot(None),
            MealLog.carbohydrates.isnot(None),
            MealLog.fats.isnot(None),
        )
    ).count()
    total_menu_items = MenuItem.query.count()
    total_reviews = Review.query.count()

    recent_pending_vendors = (
        User.query.filter_by(role="vendor", vendor_status="pending")
        .order_by(User.created_at.desc())
        .limit(8)
        .all()
    )

    return render_template(
        "admin/admin_dashboard.html",
        total_users=total_users,
        total_vendors=total_vendors,
        pending_vendors=pending_vendors,
        approved_vendors=approved_vendors,
        rejected_vendors=rejected_vendors,
        pending_experts=pending_experts,
        approved_experts=approved_experts,
        rejected_experts=rejected_experts,
        total_meal_logs=total_meal_logs,
        nutrition_ready_meals=nutrition_ready_meals,
        total_menu_items=total_menu_items,
        total_reviews=total_reviews,
        recent_pending_vendors=recent_pending_vendors,
    )


@admin_bp.route("/admin/nutrition-experts/pending")
@admin_required
def pending_nutrition_experts():
    experts = (
        User.query.filter_by(role="nutrition_expert")
        .order_by(User.created_at.asc())
        .all()
    )
    return render_template("admin/pending_nutrition_experts.html", experts=experts)


@admin_bp.route("/admin/nutrition-expert/<int:user_id>/approve", methods=["POST"])
@admin_required
def approve_nutrition_expert(user_id: int):
    expert_user = User.query.filter_by(id=user_id, role="nutrition_expert").first()
    if not expert_user:
        abort(404)

    review_note = (request.form.get("review_note") or "").strip() or None

    try:
        expert_user.expert_status = "approved"
        expert_user.expert_review_note = review_note
        db.session.commit()
        flash(f"Nutrition expert approved for {expert_user.name}.", "success")
    except Exception:
        db.session.rollback()
        flash("Failed to approve nutrition expert.", "danger")

    return redirect(url_for("admin.pending_nutrition_experts"))


@admin_bp.route("/admin/nutrition-expert/<int:user_id>/reject", methods=["POST"])
@admin_required
def reject_nutrition_expert(user_id: int):
    expert_user = User.query.filter_by(id=user_id, role="nutrition_expert").first()
    if not expert_user:
        abort(404)

    review_note = (request.form.get("review_note") or "").strip() or None

    try:
        expert_user.expert_status = "rejected"
        expert_user.expert_review_note = review_note
        db.session.commit()
        flash(f"Nutrition expert rejected for {expert_user.name}.", "warning")
    except Exception:
        db.session.rollback()
        flash("Failed to reject nutrition expert.", "danger")

    return redirect(url_for("admin.pending_nutrition_experts"))


@admin_bp.route("/admin/vendors/pending")
@admin_required
def pending_vendors():
    vendors = (
        User.query.filter_by(role="vendor", vendor_status="pending")
        .order_by(User.created_at.asc())
        .all()
    )
    return render_template("admin/pending_vendors.html", vendors=vendors)


@admin_bp.route("/admin/vendor/<int:user_id>")
@admin_required
def vendor_review(user_id: int):
    vendor_user = User.query.filter_by(id=user_id, role="vendor").first()
    if not vendor_user:
        abort(404)

    return render_template("admin/vendor_review.html", vendor_user=vendor_user)


@admin_bp.route("/admin/vendor/<int:user_id>/approve", methods=["POST"])
@admin_required
def approve_vendor(user_id: int):
    vendor_user = User.query.filter_by(id=user_id, role="vendor").first()
    if not vendor_user:
        abort(404)

    review_note = (request.form.get("review_note") or "").strip() or None

    try:
        vendor_user.vendor_status = "approved"

        if vendor_user.vendor_profile:
            vendor_user.vendor_profile.approval_status = "approved"
            vendor_user.vendor_profile.reviewed_at = datetime.utcnow()
            vendor_user.vendor_profile.reviewed_by_admin_id = current_user.id
            vendor_user.vendor_profile.admin_review_note = review_note

            existing_vendor = Vendor.query.filter_by(owner_user_id=vendor_user.id).first()
            if not existing_vendor:
                existing_vendor = Vendor(
                    owner_user_id=vendor_user.id,
                    name=vendor_user.vendor_profile.business_name,
                    category=vendor_user.vendor_profile.business_category,
                    description=vendor_user.vendor_profile.business_description,
                    image_url=vendor_user.vendor_profile.cover_image_url,
                    contact_email=vendor_user.email,
                    phone=vendor_user.phone,
                    address=vendor_user.vendor_profile.business_address,
                    is_active=True,
                )
                db.session.add(existing_vendor)
            else:
                existing_vendor.name = vendor_user.vendor_profile.business_name
                existing_vendor.category = vendor_user.vendor_profile.business_category
                existing_vendor.description = vendor_user.vendor_profile.business_description
                existing_vendor.image_url = vendor_user.vendor_profile.cover_image_url
                existing_vendor.contact_email = vendor_user.email
                existing_vendor.phone = vendor_user.phone
                existing_vendor.address = vendor_user.vendor_profile.business_address
                existing_vendor.is_active = True

        db.session.commit()
        flash(f"Vendor account approved for {vendor_user.name}.", "success")
    except Exception:
        db.session.rollback()
        flash("Failed to approve vendor account.", "danger")

    return redirect(url_for("admin.vendor_review", user_id=user_id))


@admin_bp.route("/admin/vendor/<int:user_id>/reject", methods=["POST"])
@admin_required
def reject_vendor(user_id: int):
    vendor_user = User.query.filter_by(id=user_id, role="vendor").first()
    if not vendor_user:
        abort(404)

    review_note = (request.form.get("review_note") or "").strip() or None

    try:
        vendor_user.vendor_status = "rejected"

        if vendor_user.vendor_profile:
            vendor_user.vendor_profile.approval_status = "rejected"
            vendor_user.vendor_profile.reviewed_at = datetime.utcnow()
            vendor_user.vendor_profile.reviewed_by_admin_id = current_user.id
            vendor_user.vendor_profile.admin_review_note = review_note

        existing_vendor = Vendor.query.filter_by(owner_user_id=vendor_user.id).first()
        if existing_vendor:
            existing_vendor.is_active = False

        db.session.commit()
        flash(f"Vendor account rejected for {vendor_user.name}.", "warning")
    except Exception:
        db.session.rollback()
        flash("Failed to reject vendor account.", "danger")

    return redirect(url_for("admin.vendor_review", user_id=user_id))


def _image_referenced_elsewhere(image_url: str | None, excluding_meal_id: int) -> bool:
    if not image_url:
        return False
    return (
        MealLog.query.filter(MealLog.id != excluding_meal_id, MealLog.image_url == image_url)
        .limit(1)
        .count()
        > 0
    )


@admin_bp.route("/admin/meal-logs")
@admin_required
def admin_meal_logs():
    logs = MealLog.query.order_by(MealLog.created_at.desc()).all()
    return render_template("admin/admin_meal_logs.html", logs=logs)


@admin_bp.route("/admin/meal-log/<int:meal_id>")
@admin_required
def admin_meal_detail(meal_id: int):
    meal = db.session.get(MealLog, meal_id)
    if not meal:
        abort(404)
    return render_template("admin/admin_meal_detail.html", meal=meal)


@admin_bp.route("/admin/meal-log/<int:meal_id>/delete", methods=["POST"])
@admin_required
def admin_delete_meal(meal_id: int):
    meal = db.session.get(MealLog, meal_id)
    if not meal:
        abort(404)

    public_id = meal.cloudinary_public_id
    image_url = meal.image_url
    try:
        db.session.delete(meal)
        db.session.commit()

        if public_id and not _image_referenced_elsewhere(image_url, meal_id):
            try:
                delete_image(public_id)
            except Exception:
                flash("Meal removed, but Cloudinary cleanup failed.", "warning")

        flash("Meal log deleted by admin.", "success")
    except Exception:
        db.session.rollback()
        flash("Failed to delete this meal log.", "danger")

    return redirect(url_for("admin.admin_meal_logs"))


@admin_bp.route("/admin/menu-items")
@admin_required
def admin_menu_items():
    items = (
        MenuItem.query.join(Vendor, MenuItem.vendor_id == Vendor.id)
        .order_by(MenuItem.created_at.desc())
        .all()
    )
    return render_template("admin/admin_menu_items.html", items=items)


@admin_bp.route("/admin/menu-item/<int:item_id>")
@admin_required
def admin_menu_item_detail(item_id: int):
    item = (
        MenuItem.query.join(Vendor, MenuItem.vendor_id == Vendor.id)
        .filter(MenuItem.id == item_id)
        .first()
    )
    if not item:
        abort(404)
    return render_template("admin/admin_menu_item_detail.html", item=item)


@admin_bp.route("/admin/reviews")
@admin_required
def admin_reviews():
    reviews = Review.query.order_by(Review.updated_at.desc()).all()
    return render_template("admin/admin_reviews.html", reviews=reviews)


@admin_bp.route("/admin/review/<int:review_id>/delete", methods=["POST"])
@admin_required
def admin_delete_review(review_id: int):
    review = db.session.get(Review, review_id)
    if not review:
        abort(404)

    came_from_admin_reviews = "/admin/reviews" in (request.referrer or "")
    target_vendor_id = review.vendor_id
    target_item_id = review.menu_item_id
    try:
        db.session.delete(review)
        db.session.commit()
        flash("Review deleted by admin.", "success")
    except Exception:
        db.session.rollback()
        flash("Failed to delete review.", "danger")
        return redirect(url_for("admin.admin_reviews"))

    if came_from_admin_reviews:
        return redirect(url_for("admin.admin_reviews"))
    if target_vendor_id:
        return redirect(url_for("vendor.vendor_detail", vendor_id=target_vendor_id) + "#vendor-reviews")
    if target_item_id:
        return redirect(url_for("vendor.menu_item_detail", item_id=target_item_id) + "#item-reviews")
    return redirect(url_for("admin.admin_reviews"))


@admin_bp.route("/admin/menu-item/<int:item_id>/delete", methods=["POST"])
@admin_required
def admin_delete_menu_item(item_id: int):
    item = db.session.get(MenuItem, item_id)
    if not item:
        abort(404)

    public_id = item.cloudinary_public_id
    try:
        db.session.delete(item)
        db.session.commit()

        if public_id:
            try:
                delete_image(public_id)
            except Exception:
                flash("Menu item deleted, but Cloudinary cleanup failed.", "warning")

        flash("Menu item removed by admin.", "success")
    except Exception:
        db.session.rollback()
        flash("Failed to delete menu item.", "danger")

    return redirect(url_for("admin.admin_menu_items"))
