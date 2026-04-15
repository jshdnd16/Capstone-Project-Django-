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

    # Phase 2 stats — import here to avoid circular imports at the top level
    # We use try/except in case the materials app tables don't exist yet
    try:
        from materials.models import Material, Supplier
        from inventory.models import Inventory
        from django.db.models import F

        total_materials  = Material.objects.filter(is_active=True).count()
        total_suppliers  = Supplier.objects.filter(status='Active').count()
        low_cost_items   = Material.objects.filter(is_active=True, margin_percentage__lt=10).count()
    
        # Low-stock count: quantity above 0 but at or below reorder level
        low_stock_items = Inventory.objects.filter(
            quantity__gt=0,
            quantity__lte=F('material__reorder_level'),
            material__is_active=True
        ).count()

        # Out-of-stock: quantity at 0 or below
        out_of_stock = Inventory.objects.filter(
            quantity__lte=0,
            material__is_active=True
        ).count()
    
    # except Exception:
    #     total_materials = total_suppliers = low_cost_items = 0

    except Exception:
        total_materials = total_suppliers = low_stock_items = out_of_stock = 0

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
            # Phase 2 stats (available now)
            'total_materials':  total_materials,
            'total_suppliers':  total_suppliers,
            'out_of_stock': out_of_stock,
        }
    }

    return render(request, 'core/dashboard.html', context)