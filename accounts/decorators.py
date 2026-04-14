# accounts/decorators.py
# Custom decorators that restrict views to specific roles.
# 
# A decorator wraps a view function and checks conditions BEFORE
# allowing the view to run. Think of them as security guards.
#
# Usage in views.py:
#   @login_required
#   @admin_required       ← Our custom decorator
#   def some_view(request):
#       ...

from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages


def role_required(*allowed_roles):
    """
    Generic decorator: only allows users with specific roles.
    
    Usage:
        @role_required('Admin', 'Warehouse')
        def inventory_view(request):
            ...
    
    If the user's role is not in allowed_roles, they get redirected
    to the dashboard with an "Access Denied" error message.
    """
    def decorator(view_func):
        @wraps(view_func)   # Preserves the original function's name/docstring
        def wrapper(request, *args, **kwargs):
            # Check if user is logged in and has the required role
            if not request.user.is_authenticated:
                return redirect('accounts:login')

            user_role = request.user.get_role_name()

            # Superusers (is_superuser=True) bypass all role checks
            if request.user.is_superuser or user_role in allowed_roles:
                return view_func(request, *args, **kwargs)

            # User doesn't have the required role
            messages.error(
                request,
                f"Access denied. This page requires one of these roles: {', '.join(allowed_roles)}"
            )
            return redirect('core:dashboard')

        return wrapper
    return decorator


# ─────────────────────────────────────────────────────────────
# CONVENIENCE DECORATORS (shortcuts for common role checks)
# ─────────────────────────────────────────────────────────────

def admin_required(view_func):
    """Only Admin users can access this view."""
    return role_required('Admin')(view_func)


def sales_required(view_func):
    """Only Sales (and Admin) users can access this view."""
    return role_required('Admin', 'Sales')(view_func)


def warehouse_required(view_func):
    """Only Warehouse (and Admin) users can access this view."""
    return role_required('Admin', 'Warehouse')(view_func)


def architect_required(view_func):
    """Only Architects (and Admin) users can access this view."""
    return role_required('Admin', 'Architect')(view_func)


def driver_required(view_func):
    """Drivers (and Admin) can access this view."""
    return role_required('Admin', 'Driver')(view_func)


def sales_or_warehouse(view_func):
    """Sales or Warehouse staff (and Admin) can access this view."""
    return role_required('Admin', 'Sales', 'Warehouse')(view_func)