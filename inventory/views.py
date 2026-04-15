# inventory/views.py
# All inventory views. Three main sections:
#
# 1. Stock overview  → current levels for all materials, with low-stock alerts
# 2. Transactions    → full history of all stock movements with filters
# 3. Stock actions   → Stock In, Stock Out, Adjustment forms

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Sum, F

from materials.models import Material, Category
from accounts.utils import log_action
from accounts.decorators import role_required, warehouse_required, admin_required

from .models import Inventory, InventoryTransaction
from .forms import StockInForm, StockOutForm, StockAdjustmentForm
from .utils import apply_stock_in, apply_stock_out, apply_adjustment, get_or_create_inventory


# ─────────────────────────────────────────────────────────────
# 1. STOCK OVERVIEW
# ─────────────────────────────────────────────────────────────

@login_required
@role_required('Admin', 'Warehouse', 'Sales', 'Architect')
def stock_overview_view(request):
    """
    Main inventory dashboard. Shows current stock for all materials.
    
    Three sections:
    - ⚠️  Out of Stock  (quantity = 0)
    - 🔴  Low Stock     (quantity ≤ reorder_level but > 0)
    - ✅  OK            (quantity > reorder_level)
    
    All roles can VIEW stock. Only Warehouse/Admin can modify it.
    """

    # Get all inventory records with their related material, category, supplier
    # select_related() prevents N+1 queries by joining tables in one SQL call
    inventory_qs = Inventory.objects.select_related(
        'material', 'material__category', 'material__supplier'
    ).filter(material__is_active=True)

    # ── Filtering ──
    category_filter  = request.GET.get('category', '')
    status_filter    = request.GET.get('stock_status', '')
    search           = request.GET.get('search', '').strip()

    if category_filter:
        inventory_qs = inventory_qs.filter(material__category_id=category_filter)

    if status_filter == 'out':
        inventory_qs = inventory_qs.filter(quantity__lte=0)
    elif status_filter == 'low':
        # quantity is low: above 0 but at or below the reorder level
        inventory_qs = inventory_qs.filter(
            quantity__gt=0,
            quantity__lte=F('material__reorder_level')
        )
    elif status_filter == 'ok':
        inventory_qs = inventory_qs.filter(quantity__gt=F('material__reorder_level'))

    if search:
        inventory_qs = inventory_qs.filter(
            Q(material__name__icontains=search) |
            Q(material__sku__icontains=search)
        )

    # ── Summary Counts for the alert banners ──
    all_inv         = Inventory.objects.filter(material__is_active=True)
    out_of_stock    = all_inv.filter(quantity__lte=0).count()
    low_stock       = all_inv.filter(
        quantity__gt=0, quantity__lte=F('material__reorder_level')
    ).count()
    total_materials = Material.objects.filter(is_active=True).count()

    # Materials in catalog that have NO inventory row yet (never had stock entered)
    materials_with_inv = Inventory.objects.values_list('material_id', flat=True)
    untracked_count = Material.objects.filter(
        is_active=True
    ).exclude(id__in=materials_with_inv).count()

    categories = Category.objects.all()

    return render(request, 'inventory/stock_overview.html', {
        'inventory_list':   inventory_qs,
        'out_of_stock':     out_of_stock,
        'low_stock':        low_stock,
        'total_materials':  total_materials,
        'untracked_count':  untracked_count,
        'categories':       categories,
        'category_filter':  category_filter,
        'status_filter':    status_filter,
        'search':           search,
    })


# ─────────────────────────────────────────────────────────────
# 2. TRANSACTION HISTORY
# ─────────────────────────────────────────────────────────────

@login_required
@role_required('Admin', 'Warehouse', 'Sales', 'Architect')
def transaction_history_view(request):
    """
    Full log of every stock movement. Supports filtering by type,
    material, and date range.
    """

    txns = InventoryTransaction.objects.select_related(
        'material', 'material__category', 'user'
    ).order_by('-transaction_date')

    # ── Filters ──
    type_filter     = request.GET.get('type', '')
    material_filter = request.GET.get('material', '')
    search          = request.GET.get('search', '').strip()

    if type_filter:
        txns = txns.filter(transaction_type=type_filter)
    if material_filter:
        txns = txns.filter(material_id=material_filter)
    if search:
        txns = txns.filter(
            Q(material__name__icontains=search) |
            Q(remarks__icontains=search)
        )

    # Limit to most recent 300 for performance. Full export comes in Phase 8.
    txns = txns[:300]

    materials = Material.objects.filter(is_active=True).order_by('name')

    return render(request, 'inventory/transaction_history.html', {
        'transactions':      txns,
        'materials':         materials,
        'type_filter':       type_filter,
        'material_filter':   material_filter,
        'search':            search,
    })


@login_required
@role_required('Admin', 'Warehouse', 'Sales', 'Architect')
def material_stock_detail_view(request, material_id):
    """
    Detailed view for a single material's stock card.
    Shows current level + full transaction history for that material only.
    """
    material = get_object_or_404(Material, pk=material_id, is_active=True)
    inv      = get_or_create_inventory(material)
    txns     = InventoryTransaction.objects.filter(
        material=material
    ).select_related('user').order_by('-transaction_date')

    # Running totals for this material
    total_in  = txns.filter(transaction_type='IN').aggregate(
        total=Sum('quantity')
    )['total'] or 0
    total_out = txns.filter(transaction_type='OUT').aggregate(
        total=Sum('quantity')
    )['total'] or 0

    return render(request, 'inventory/material_stock_detail.html', {
        'material':    material,
        'inventory':   inv,
        'transactions': txns,
        'total_in':    total_in,
        'total_out':   total_out,
    })


# ─────────────────────────────────────────────────────────────
# 3. STOCK ACTIONS (Warehouse + Admin only)
# ─────────────────────────────────────────────────────────────

@login_required
@role_required('Admin', 'Warehouse')
def stock_in_view(request):
    """
    Records incoming stock. Can be pre-filled via ?material=ID
    from the stock overview page's quick-action button.
    """
    # Allow pre-selecting a material from a link (e.g. ?material=5)
    initial_material = request.GET.get('material')
    initial = {'material': initial_material} if initial_material else {}

    form = StockInForm(request.POST or None, initial=initial)

    if request.method == 'POST' and form.is_valid():
        material = form.cleaned_data['material']
        quantity = form.cleaned_data['quantity']

        inv = apply_stock_in(
            material       = material,
            quantity       = quantity,
            user           = request.user,
            reference_type = form.cleaned_data['reference_type'],
            reference_id   = form.cleaned_data.get('reference_id'),
            remarks        = form.cleaned_data.get('remarks', ''),
        )

        log_action(
            user           = request.user,
            action_type    = 'UPDATE_INVENTORY',
            table_affected = 'inventory',
            record_id      = inv.pk,
            description    = (
                f"STOCK IN: +{quantity} {material.unit} of '{material.name}'. "
                f"New balance: {inv.quantity} {material.unit}."
            ),
            request = request
        )

        messages.success(
            request,
            f"✓ Stock In recorded: +{quantity} {material.unit} of {material.name}. "
            f"New balance: {inv.quantity} {material.unit}."
        )
        return redirect('inventory:stock_overview')

    return render(request, 'inventory/stock_in_form.html', {
        'form':       form,
        'form_title': 'Record Stock In',
    })


@login_required
@role_required('Admin', 'Warehouse')
def stock_out_view(request):
    """
    Records stock being issued (for sales orders, architecture projects, etc.).
    Validates that sufficient stock exists before allowing submission.
    """
    initial_material = request.GET.get('material')
    initial = {'material': initial_material} if initial_material else {}

    form = StockOutForm(request.POST or None, initial=initial)

    if request.method == 'POST' and form.is_valid():
        material = form.cleaned_data['material']
        quantity = form.cleaned_data['quantity']

        try:
            inv = apply_stock_out(
                material       = material,
                quantity       = quantity,
                user           = request.user,
                reference_type = form.cleaned_data['reference_type'],
                reference_id   = form.cleaned_data.get('reference_id'),
                remarks        = form.cleaned_data.get('remarks', ''),
            )

            log_action(
                user           = request.user,
                action_type    = 'UPDATE_INVENTORY',
                table_affected = 'inventory',
                record_id      = inv.pk,
                description    = (
                    f"STOCK OUT: -{quantity} {material.unit} of '{material.name}'. "
                    f"New balance: {inv.quantity} {material.unit}."
                ),
                request = request
            )

            messages.success(
                request,
                f"✓ Stock Out recorded: -{quantity} {material.unit} of {material.name}. "
                f"Remaining: {inv.quantity} {material.unit}."
            )
            return redirect('inventory:stock_overview')

        except ValueError as e:
            # apply_stock_out raises ValueError for insufficient stock
            messages.error(request, str(e))

    return render(request, 'inventory/stock_out_form.html', {
        'form':       form,
        'form_title': 'Record Stock Out',
    })


@login_required
@role_required('Admin', 'Warehouse')
def stock_adjustment_view(request):
    """
    Manual stock adjustment after a physical recount.
    
    The user enters the CORRECT quantity (from their physical count),
    and the system figures out the difference automatically.
    This is how real warehouse management works.
    """
    initial_material = request.GET.get('material')
    initial = {'material': initial_material} if initial_material else {}

    form = StockAdjustmentForm(request.POST or None, initial=initial)

    if request.method == 'POST' and form.is_valid():
        material     = form.cleaned_data['material']
        new_quantity = form.cleaned_data['new_quantity']
        reason       = form.cleaned_data['reason']
        remarks      = form.cleaned_data.get('remarks', '')

        inv, delta = apply_adjustment(
            material     = material,
            new_quantity = new_quantity,
            user         = request.user,
            reason       = reason,
            remarks      = remarks,
        )

        # Describe the change clearly in the log
        if delta > 0:
            delta_str = f"+{delta} (stock was higher than recorded)"
        elif delta < 0:
            delta_str = f"{delta} (stock was lower than recorded)"
        else:
            delta_str = "no change (count matched records)"

        log_action(
            user           = request.user,
            action_type    = 'UPDATE_INVENTORY',
            table_affected = 'inventory',
            record_id      = inv.pk,
            description    = (
                f"ADJUSTMENT: '{material.name}' adjusted by {delta_str}. "
                f"New balance: {new_quantity} {material.unit}. Reason: {reason}."
            ),
            request = request
        )

        messages.success(
            request,
            f"✓ Adjustment saved. '{material.name}' stock set to {new_quantity} {material.unit} "
            f"(change: {'+' if delta >= 0 else ''}{delta})."
        )
        return redirect('inventory:stock_overview')

    return render(request, 'inventory/stock_adjustment_form.html', {
        'form':       form,
        'form_title': 'Stock Adjustment',
    })