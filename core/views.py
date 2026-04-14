# core/views.py
# The core app contains views that are shared across the entire system,
# primarily the main dashboard that all users see after logging in.
# Each role sees a different version of the dashboard.

from django.shortcuts import render
from django.contrib.auth.decorators import login_required


@login_required
def dashboard_view(request):
    """
    Main dashboard — every user lands here after login.
    The template will show different widgets based on the user's role.
    
    In later phases, we'll add real stats:
    - Sales: today's orders, pending deliveries
    - Warehouse: low stock alerts, pending procurement
    - Architect: ongoing projects, pending material requests
    - Driver: today's delivery schedule
    """

    # Get the current user's role name (safely — role might be None)
    user_role = request.user.get_role_name()

    # We'll populate these with real data in future phases
    # For now, they're placeholders so the template doesn't crash
    context = {
        'user_role': user_role,
        'page_title': 'Dashboard',
        # Placeholder stats — will be replaced with real queries in Phase 4+
        'stats': {
            'pending_orders': 0,
            'low_stock_items': 0,
            'ongoing_projects': 0,
            'scheduled_deliveries': 0,
        }
    }

    return render(request, 'core/dashboard.html', context)