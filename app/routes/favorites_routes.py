from urllib.parse import urlsplit

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import login_required

from app.extensions import db
from app.models import (
    FavoriteMeal,
    FavoriteMenuItem,
    FavoriteVendor,
    MealLog,
    MenuItem,
    Vendor,
)
from app.services.auth_service import role_required
from app.services.nutrition_service import get_nutrition_insights

favorites_bp = Blueprint("favorites", __name__)


def _safe_next_url(default_endpoint: str, **default_values) -> str:
    next_url = (
        request.form.get("next")
        or request.args.get("next")
        or request.referrer
        or ""
    ).strip()

    if next_url:
        parsed = urlsplit(next_url)
        if not parsed.scheme and not parsed.netloc and parsed.path.startswith("/"):
            return next_url

    return url_for(default_endpoint, **default_values)


@favorites_bp.route("/favorites")
@login_required
@role_required("user")
def favorites_list():
    favorite_vendors = (
        FavoriteVendor.query.join(Vendor)
        .filter(Vendor.is_active.is_(True))
        .order_by(FavoriteVendor.created_at.desc())
        .all()
    )

    favorite_menu_items = (
        FavoriteMenuItem.query.join(MenuItem)
        .join(Vendor)
        .filter(MenuItem.is_available.is_(True), Vendor.is_active.is_(True))
        .order_by(FavoriteMenuItem.created_at.desc())
        .all()
    )

    favorite_meals = FavoriteMeal.query.join(MealLog).order_by(FavoriteMeal.created_at.desc()).all()

    menu_item_indicator_map = {
        favorite.menu_item.id: get_nutrition_insights(
            favorite.menu_item.calories,
            favorite.menu_item.protein,
            favorite.menu_item.carbohydrates,
            favorite.menu_item.fats,
        )
        for favorite in favorite_menu_items
    }

    meal_indicator_map = {
        favorite.meal_log.id: get_nutrition_insights(
            favorite.meal_log.calories,
            favorite.meal_log.protein,
            favorite.meal_log.carbohydrates,
            favorite.meal_log.fats,
        )
        for favorite in favorite_meals
    }

    return render_template(
        "favorites/favorites.html",
        favorite_vendors=favorite_vendors,
        favorite_menu_items=favorite_menu_items,
        favorite_meals=favorite_meals,
        menu_item_indicator_map=menu_item_indicator_map,
        meal_indicator_map=meal_indicator_map,
    )


@favorites_bp.route("/favorites/vendors/<int:vendor_id>/toggle", methods=["POST"])
@login_required
@role_required("user")
def toggle_vendor_favorite(vendor_id: int):
    vendor = Vendor.query.filter_by(id=vendor_id, is_active=True).first()
    if not vendor:
        abort(404)

    favorite = FavoriteVendor.query.filter_by(vendor_id=vendor.id).first()
    next_url = _safe_next_url("vendor.vendor_detail", vendor_id=vendor.id)

    try:
        if favorite:
            db.session.delete(favorite)
            flash(f"Removed {vendor.name} from favorites.", "info")
        else:
            db.session.add(FavoriteVendor(vendor_id=vendor.id))
            flash(f"Saved {vendor.name} to favorites.", "success")

        db.session.commit()
    except Exception:
        db.session.rollback()
        flash("Could not update vendor favorite right now.", "danger")

    return redirect(next_url)


@favorites_bp.route("/favorites/menu-items/<int:item_id>/toggle", methods=["POST"])
@login_required
@role_required("user")
def toggle_menu_item_favorite(item_id: int):
    menu_item = db.session.get(MenuItem, item_id)
    if not menu_item or not menu_item.is_available or not menu_item.vendor or not menu_item.vendor.is_active:
        abort(404)

    favorite = FavoriteMenuItem.query.filter_by(menu_item_id=menu_item.id).first()
    next_url = _safe_next_url("vendor.menu_item_detail", item_id=menu_item.id)

    try:
        if favorite:
            db.session.delete(favorite)
            flash(f"Removed {menu_item.name} from favorites.", "info")
        else:
            db.session.add(FavoriteMenuItem(menu_item_id=menu_item.id))
            flash(f"Saved {menu_item.name} to favorites.", "success")

        db.session.commit()
    except Exception:
        db.session.rollback()
        flash("Could not update menu item favorite right now.", "danger")

    return redirect(next_url)


@favorites_bp.route("/favorites/meals/<int:meal_id>/toggle", methods=["POST"])
@login_required
@role_required("user")
def toggle_meal_favorite(meal_id: int):
    meal = db.session.get(MealLog, meal_id)
    if not meal:
        abort(404)

    favorite = FavoriteMeal.query.filter_by(meal_log_id=meal.id).first()
    next_url = _safe_next_url("meal.meal_detail", meal_id=meal.id)

    meal_name = meal.title or f"{meal.meal_type.capitalize()} meal"

    try:
        if favorite:
            db.session.delete(favorite)
            flash(f"Removed {meal_name} from favorites.", "info")
        else:
            db.session.add(FavoriteMeal(meal_log_id=meal.id))
            flash(f"Saved {meal_name} to favorites.", "success")

        db.session.commit()
    except Exception:
        db.session.rollback()
        flash("Could not update meal favorite right now.", "danger")

    return redirect(next_url)
