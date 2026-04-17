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
    low_stock_detail = []
    try:
        from materials.models import Material, Supplier
        from inventory.models import Inventory
        from django.db.models import F
        from types import SimpleNamespace

        total_materials  = Material.objects.filter(is_active=True).count()
        total_suppliers  = Supplier.objects.filter(status='Active').count()
        # IDs of materials that have an Inventory row
        materials_with_inv = set(
            Inventory.objects.values_list('material_id', flat=True)
        )

        # Low-stock count: items whose quantity is at or below their reorder level
        # This includes:
        #   1. Inventory rows where 0 < quantity <= reorder_level
        #   2. Inventory rows where quantity <= 0  (out-of-stock is also low)
        #   3. Active materials with NO Inventory row (implicitly 0 quantity)
        low_stock_with_inv_qs = Inventory.objects.filter(
            quantity__lte=F('material__reorder_level'),
            material__is_active=True
        ).select_related('material')

        low_stock_with_inv = low_stock_with_inv_qs.count()

        # Materials that have no Inventory row are implicitly at 0,
        # which is always <= any reorder_level (default 10)
        no_inv_materials = Material.objects.filter(
            is_active=True
        ).exclude(id__in=materials_with_inv)

        low_stock_no_inv = no_inv_materials.count()

        low_stock_items = low_stock_with_inv + low_stock_no_inv

        # Out-of-stock: quantity at 0 or below, plus materials with no row
        out_of_stock_with_inv = Inventory.objects.filter(
            quantity__lte=0,
            material__is_active=True
        ).count()
        out_of_stock = out_of_stock_with_inv + low_stock_no_inv

        # ── Build the detail list for the dashboard card (max 5 items) ──
        # 1. Real inventory rows that are low-stock, ordered by quantity ascending
        detail_from_inv = list(
            low_stock_with_inv_qs.order_by('quantity')[:5]
        )

        # 2. Materials with no inventory row (quantity is implicitly 0)
        remaining_slots = 5 - len(detail_from_inv)
        if remaining_slots > 0:
            for mat in no_inv_materials.order_by('name')[:remaining_slots]:
                detail_from_inv.append(
                    SimpleNamespace(quantity=0, material=mat)
                )

        # Sort combined list so worst items appear first
        low_stock_detail = sorted(detail_from_inv, key=lambda x: x.quantity)

    except Exception:
        total_materials = total_suppliers = low_stock_items = out_of_stock = 0

    # We'll populate these with real data in future phases
    # For now, they're placeholders so the template doesn't crash
    context = {
        'user_role': user_role,
        'page_title': 'Dashboard',
        'low_stock_detail': low_stock_detail,
        # Placeholder stats — will be replaced with real queries in Phase 4+
        'stats': {
            'pending_orders': 0,
            'low_stock_items': low_stock_items,
            'ongoing_projects': 0,
            'scheduled_deliveries': 0,
            # Phase 2 stats (available now)
            'total_materials':  total_materials,
            'total_suppliers':  total_suppliers,
            'out_of_stock': out_of_stock,
        }
    }

    return render(request, 'core/dashboard.html', context)