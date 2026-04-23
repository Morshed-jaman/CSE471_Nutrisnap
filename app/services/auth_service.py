from functools import wraps

from flask import flash, redirect, request, url_for
from flask_login import current_user


def redirect_for_role(user) -> str:
    if not user.is_authenticated:
        return url_for("auth.login")

    if user.role == "admin":
        return url_for("admin.admin_dashboard")

    if user.role == "vendor":
        if user.vendor_status == "approved":
            return url_for("vendor.vendor_dashboard")
        return url_for("auth.vendor_pending")
#vendor pending page for pending and rejected vendor accounts
    if user.role == "nutrition_expert":
        if user.expert_status == "approved":
            return url_for("advice.expert_advice_dashboard")
        return url_for("auth.expert_pending")

    return url_for("meal.home")


def _login_redirect_response():
    next_url = request.url
    return redirect(url_for("auth.login", next=next_url))


def role_required(*roles):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                return _login_redirect_response()

            if current_user.role not in roles:
                flash("You do not have access to that page.", "danger")
                return redirect(redirect_for_role(current_user))

            return view_func(*args, **kwargs)

        return wrapped

    return decorator


def admin_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for("admin.admin_login", next=request.url))

        if current_user.role != "admin":
            flash("Admin access is required.", "danger")
            return redirect(redirect_for_role(current_user))

        return view_func(*args, **kwargs)

    return wrapped


def approved_vendor_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated:
            return _login_redirect_response()

        if current_user.role != "vendor":
            flash("Vendor access is required.", "danger")
            return redirect(redirect_for_role(current_user))

        if current_user.vendor_status != "approved":
            if current_user.vendor_status == "rejected":
                flash("Your vendor account was rejected. Contact admin for review.", "warning")
            else:
                flash("Your vendor account is pending admin approval.", "info")
            return redirect(url_for("auth.vendor_pending"))

        return view_func(*args, **kwargs)

    return wrapped


def vendor_account_required(view_func):
    return role_required("vendor")(view_func)


def subscriber_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated:
            return _login_redirect_response()

        if current_user.role != "user":
            flash("User access is required.", "danger")
            return redirect(redirect_for_role(current_user))

        if not bool(current_user.is_subscribed):
            flash("This feature is available only for subscribed users.", "warning")
            return redirect(url_for("auth.user_profile"))

        return view_func(*args, **kwargs)

    return wrapped


def verified_expert_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated:
            return _login_redirect_response()

        if current_user.role != "nutrition_expert":
            flash("Nutrition expert access is required.", "danger")
            return redirect(redirect_for_role(current_user))

        if current_user.expert_status != "approved":
            if current_user.expert_status == "rejected":
                flash("Your nutrition expert account was rejected by admin.", "warning")
            else:
                flash("Your nutrition expert account is pending admin verification.", "info")
            return redirect(url_for("auth.expert_pending"))

        return view_func(*args, **kwargs)

    return wrapped
