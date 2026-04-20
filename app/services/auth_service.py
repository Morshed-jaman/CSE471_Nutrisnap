from functools import wraps

from flask import flash, redirect, request, url_for
from flask_login import current_user


def redirect_for_role(user) -> str:
    if not user.is_authenticated:
        return url_for("auth.login")

    if user.role == "vendor":
        return url_for("vendor.vendor_dashboard")

    if user.role == "admin":
        return url_for("vendor.vendors")

    return url_for("meal.home")


def _login_redirect_response():
    return redirect(url_for("auth.login", next=request.url))


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


def vendor_required(view_func):
    return role_required("vendor")(view_func)
