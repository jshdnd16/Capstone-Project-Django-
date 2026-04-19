# procurement/views.py
# All procurement views. Three main groups:
#
# PROCUREMENT ORDER VIEWS → list, detail, create, edit, status updates
# RECEIVING VIEW          → record actual quantities received + auto stock-in
# DASHBOARD               → summary stats, overdue alerts, spend overview

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction as db_transaction
from django.db.models import Q, Sum, Count
from django.utils import timezone

from accounts.utils import log_action
from accounts.decorators import role_required, admin_required, warehouse_required
from inventory.utils import apply_stock_in
from materials.models import Material, Supplier

from .models import ProcurementOrder, ProcurementItem
from .forms import (
    ProcurementOrderForm, ProcurementItemFormSet,
    ProcurementUpdateForm, ReceivingForm,
)


# ─────────────────────────────────────────────────────────────
# PROCUREMENT DASHBOARD
# ─────────────────────────────────────────────────────────────

@login_required
@role_required('Admin', 'Warehouse')
def procurement_dashboard_view(request):
    """
    Overview dashboard for procurement.
    Shows pending orders, overdue alerts, spend stats, and
    a list of materials that are below their reorder level
    so the Warehouse knows what to order next.
    """
    from inventory.models import Inventory
    from django.db.models import F

    # ── Active POs ──
    active_pos   = ProcurementOrder.objects.filter(
        status__in=['Draft', 'Submitted', 'Confirmed', 'Shipped']
    ).select_related('supplier', 'ordered_by').order_by('expected_delivery_date')

    # ── Overdue POs (expected date has passed) ──
    today = timezone.localdate()
    overdue_pos = [po for po in active_pos if po.is_overdue]

    # ── Spending stats ──
    this_month_start = today.replace(day=1)
    month_spend = ProcurementOrder.objects.filter(
        status='Received',
        actual_delivery_date__gte=this_month_start
    ).aggregate(total=Sum('total_amount'))['total'] or 0

    year_spend = ProcurementOrder.objects.filter(
        status='Received',
        actual_delivery_date__year=today.year
    ).aggregate(total=Sum('total_amount'))['total'] or 0

    # ── Materials to reorder (below reorder level) ──
    reorder_needed = Inventory.objects.filter(
        quantity__lte=F('material__reorder_level'),
        material__is_active=True,
        material__is_sales_inventory=True   # Only Sales stock items
    ).select_related(
        'material', 'material__supplier', 'material__category'
    ).order_by('quantity')

    # ── Recent completed POs ──
    recent_received = ProcurementOrder.objects.filter(
        status='Received'
    ).select_related('supplier').order_by('-actual_delivery_date')[:5]

    return render(request, 'procurement/procurement_dashboard.html', {
        'active_pos':       active_pos,
        'overdue_pos':      overdue_pos,
        'overdue_count':    len(overdue_pos),
        'month_spend':      month_spend,
        'year_spend':       year_spend,
        'reorder_needed':   reorder_needed,
        'reorder_count':    reorder_needed.count(),
        'recent_received':  recent_received,
        'today':            today,
    })


# ─────────────────────────────────────────────────────────────
# PROCUREMENT ORDER VIEWS
# ─────────────────────────────────────────────────────────────

@login_required
@role_required('Admin', 'Warehouse')
def procurement_list_view(request):
    """
    Lists all procurement orders with filtering by status,
    supplier, and search.
    """
    orders = ProcurementOrder.objects.select_related(
        'supplier', 'ordered_by'
    ).order_by('-order_date')

    # ── Filters ──
    status_filter   = request.GET.get('status', '')
    supplier_filter = request.GET.get('supplier', '')
    search          = request.GET.get('search', '').strip()

    if status_filter:
        orders = orders.filter(status=status_filter)
    if supplier_filter:
        orders = orders.filter(supplier_id=supplier_filter)
    if search:
        orders = orders.filter(
            Q(supplier__company_name__icontains=search) |
            Q(dr_number__icontains=search) |
            Q(notes__icontains=search)
        )

    # Summary counts for filter tabs
    all_orders = ProcurementOrder.objects.all()
    counts = {
        'all':       all_orders.count(),
        'draft':     all_orders.filter(status='Draft').count(),
        'submitted': all_orders.filter(status='Submitted').count(),
        'confirmed': all_orders.filter(status='Confirmed').count(),
        'shipped':   all_orders.filter(status='Shipped').count(),
        'received':  all_orders.filter(status='Received').count(),
    }

    suppliers = Supplier.objects.filter(status='Active').order_by('company_name')

    return render(request, 'procurement/procurement_list.html', {
        'orders':           orders,
        'counts':           counts,
        'status_filter':    status_filter,
        'supplier_filter':  supplier_filter,
        'search':           search,
        'suppliers':        suppliers,
    })


@login_required
@role_required('Admin', 'Warehouse')
def procurement_detail_view(request, po_id):
    """
    Full PO detail — items, status timeline, action buttons,
    and the receiving form when status is Shipped.
    """
    po    = get_object_or_404(
        ProcurementOrder.objects.select_related('supplier', 'ordered_by', 'approved_by'),
        pk=po_id
    )
    items = po.items.select_related('material', 'material__category')

    # Prepare receiving form if the PO is Shipped
    receiving_form = None
    if po.status == 'Shipped' and not po.stock_received:
        receiving_form = ReceivingForm(po, request.POST or None)

    return render(request, 'procurement/procurement_detail.html', {
        'po':             po,
        'items':          items,
        'next_statuses':  po.get_next_statuses(),
        'status_steps':   ['Draft', 'Submitted', 'Confirmed', 'Shipped', 'Received'],
        'receiving_form': receiving_form,
    })


@login_required
@role_required('Admin', 'Warehouse')
@db_transaction.atomic
def procurement_create_view(request):
    """
    Create a new procurement order (Draft status).

    The order starts as Draft so the Warehouse can review it
    before submitting to the supplier. Only after it's Submitted
    does the supplier know about it.

    Items are added inline via ProcurementItemFormSet.
    The @atomic decorator rolls back everything if any item fails.
    """
    order_form   = ProcurementOrderForm(request.POST or None)
    item_formset = ProcurementItemFormSet(request.POST or None, prefix='po_items')

    # Pre-select Magna Prime if it exists
    if request.method == 'GET':
        try:
            magna = Supplier.objects.get(is_primary=True)
            order_form = ProcurementOrderForm(initial={'supplier': magna})
        except Supplier.DoesNotExist:
            pass

    if request.method == 'POST':
        if order_form.is_valid() and item_formset.is_valid():

            # Save PO header
            po             = order_form.save(commit=False)
            po.ordered_by  = request.user
            po.status      = 'Draft'
            po.save()

            # Save line items
            item_formset.instance = po
            items = item_formset.save(commit=False)

            for item in items:
                # Auto-fill unit_cost from material's current_cost if blank
                if not item.unit_cost:
                    item.unit_cost = item.material.current_cost
                # Default received_qty = 0 (will be updated when goods arrive)
                item.received_qty = 0
                item.save()

            for deleted in item_formset.deleted_objects:
                deleted.delete()

            po.recalculate_total()

            log_action(
                user=request.user, action_type='CREATE_PROCUREMENT',
                table_affected='procurement_procurementorder', record_id=po.pk,
                description=(
                    f"Created PO#{po.pk} — {po.supplier.company_name}. "
                    f"Items: {po.total_items}. "
                    f"Total: ₱{po.total_amount}."
                ),
                request=request
            )

            messages.success(
                request,
                f"PO#{po.pk} created as Draft. "
                f"Total: ₱{po.total_amount}. "
                "Review and submit when ready."
            )
            return redirect('procurement:procurement_detail', po_id=po.pk)

    return render(request, 'procurement/procurement_form.html', {
        'order_form':    order_form,
        'item_formset':  item_formset,
        'form_title':    'Create Procurement Order',
        'materials_json': _materials_json(),
    })


@login_required
@role_required('Admin', 'Warehouse')
@db_transaction.atomic
def procurement_edit_view(request, po_id):
    """
    Edit a Draft PO — change items, quantities, or header details.
    Only allowed while the PO is still a Draft.
    Once Submitted, it is locked.
    """
    po = get_object_or_404(ProcurementOrder, pk=po_id)

    if not po.is_editable:
        messages.error(
            request,
            f"PO#{po.pk} is '{po.status}' and can no longer be edited. "
            "Only Draft orders can be modified."
        )
        return redirect('procurement:procurement_detail', po_id=po_id)

    order_form   = ProcurementUpdateForm(request.POST or None, instance=po)
    item_formset = ProcurementItemFormSet(
        request.POST or None, instance=po, prefix='po_items'
    )

    if request.method == 'POST' and order_form.is_valid() and item_formset.is_valid():
        order_form.save()

        items = item_formset.save(commit=False)
        for item in items:
            if not item.unit_cost:
                item.unit_cost = item.material.current_cost
            item.received_qty = 0
            item.save()
        for deleted in item_formset.deleted_objects:
            deleted.delete()

        po.recalculate_total()

        log_action(
            user=request.user, action_type='OTHER',
            table_affected='procurement_procurementorder', record_id=po.pk,
            description=f"Edited PO#{po.pk}. New total: ₱{po.total_amount}.",
            request=request
        )

        messages.success(request, f"PO#{po.pk} updated. Total: ₱{po.total_amount}.")
        return redirect('procurement:procurement_detail', po_id=po_id)

    return render(request, 'procurement/procurement_form.html', {
        'order_form':    order_form,
        'item_formset':  item_formset,
        'po':            po,
        'form_title':    f'Edit PO#{po.pk}',
        'materials_json': _materials_json(),
    })


# ─────────────────────────────────────────────────────────────
# STATUS UPDATE VIEW
# ─────────────────────────────────────────────────────────────

@login_required
@role_required('Admin', 'Warehouse')
def procurement_update_status_view(request, po_id):
    """
    Advances the PO to the next status.

    Status Shipped → Received is handled separately by
    procurement_receive_view, which needs to collect received quantities.

    All other transitions are handled here (Draft → Submitted,
    Submitted → Confirmed, Confirmed → Shipped, and all → Cancelled).
    """
    po         = get_object_or_404(ProcurementOrder, pk=po_id)
    new_status = request.POST.get('new_status', '').strip()

    if request.method != 'POST':
        return redirect('procurement:procurement_detail', po_id=po_id)

    # Redirect to the receiving view for the Received transition
    if new_status == 'Received':
        return redirect('procurement:procurement_receive', po_id=po_id)

    # Validate the transition
    allowed = po.get_next_statuses()
    if new_status not in allowed:
        messages.error(
            request,
            f"Cannot move PO#{po.pk} from '{po.status}' to '{new_status}'."
        )
        return redirect('procurement:procurement_detail', po_id=po_id)

    old_status = po.status
    po.status  = new_status

    # Record who approved/confirmed the PO
    if new_status in ('Confirmed', 'Shipped') and not po.approved_by:
        po.approved_by = request.user

    po.save()

    log_action(
        user=request.user, action_type='OTHER',
        table_affected='procurement_procurementorder', record_id=po.pk,
        description=(
            f"PO#{po.pk} status: {old_status} → {new_status}. "
            f"Supplier: {po.supplier.company_name}."
        ),
        request=request
    )

    messages.success(request, f"PO#{po.pk} moved to '{new_status}'.")
    return redirect('procurement:procurement_detail', po_id=po_id)


# ─────────────────────────────────────────────────────────────
# RECEIVING VIEW  ← The most important view in this module
# ─────────────────────────────────────────────────────────────

@login_required
@role_required('Admin', 'Warehouse')
@db_transaction.atomic
def procurement_receive_view(request, po_id):
    """
    Records what actually arrived and updates inventory.

    This is the key view that connects procurement to inventory.

    Flow:
    1. User enters received_qty for each item (defaults to ordered_qty)
    2. User enters the DR number and actual arrival date
    3. On POST:
       a. Update each ProcurementItem.received_qty
       b. Call apply_stock_in() for every item where received_qty > 0
       c. Mark PO as Received and set stock_received = True
       d. Set actual_delivery_date

    The @atomic decorator means if ANY stock-in fails, nothing is saved.
    This prevents partial inventory updates that leave the PO in an
    inconsistent state.
    """
    po = get_object_or_404(ProcurementOrder, pk=po_id)

    if po.status not in ('Shipped', 'Confirmed'):
        messages.error(
            request,
            f"PO#{po.pk} must be 'Shipped' or 'Confirmed' to record receipt. "
            f"Current status: '{po.status}'."
        )
        return redirect('procurement:procurement_detail', po_id=po_id)

    if po.stock_received:
        messages.warning(
            request,
            f"PO#{po.pk} has already been received and stock has been updated."
        )
        return redirect('procurement:procurement_detail', po_id=po_id)

    form = ReceivingForm(po, request.POST or None)

    if request.method == 'POST' and form.is_valid():
        dr_number   = form.cleaned_data.get('dr_number', '')
        actual_date = form.cleaned_data['actual_delivery_date']
        recv_notes  = form.cleaned_data.get('notes', '')

        stock_updates = []     # Collect descriptions for the audit log

        # ── Process each item ────────────────────────────────
        for item in po.items.select_related('material'):
            field_name   = f'received_qty_{item.pk}'
            received_qty = form.cleaned_data.get(field_name, 0)

            # Update the item's received quantity
            item.received_qty = received_qty
            item.save()

            # Add to inventory only if goods actually arrived
            if received_qty > 0:
                apply_stock_in(
                    material       = item.material,
                    quantity       = received_qty,
                    user           = request.user,
                    reference_type = 'PROCUREMENT',
                    reference_id   = po.pk,
                    remarks        = (
                        f"PO#{po.pk} received — {po.supplier.company_name}. "
                        f"DR#{dr_number or 'N/A'}. "
                        f"Received {received_qty} of {item.ordered_qty} {item.material.unit}."
                    ),
                )
                stock_updates.append(
                    f"+{received_qty} {item.material.unit} {item.material.name}"
                )

                # Warn about shortages in the success message
                if item.is_short_delivered:
                    messages.warning(
                        request,
                        f"Short delivery: {item.material.name} — "
                        f"ordered {item.ordered_qty}, received {received_qty}. "
                        f"Shortage: {item.shortage} {item.material.unit}."
                    )

        # ── Mark PO as Received ──────────────────────────────
        po.status               = 'Received'
        po.stock_received       = True
        po.dr_number            = dr_number
        po.actual_delivery_date = actual_date
        if recv_notes:
            po.notes = (po.notes + "\n\nReceiving notes: " + recv_notes).strip()
        po.save()

        log_action(
            user=request.user, action_type='CREATE_PROCUREMENT',
            table_affected='procurement_procurementorder', record_id=po.pk,
            description=(
                f"PO#{po.pk} received from {po.supplier.company_name}. "
                f"DR#{dr_number or 'N/A'}. "
                f"Stock updates: {'; '.join(stock_updates) or 'None'}."
            ),
            request=request
        )

        messages.success(
            request,
            f"PO#{po.pk} received. "
            f"{len(stock_updates)} item(s) added to inventory. "
            f"DR#: {dr_number or 'Not recorded'}."
        )
        return redirect('procurement:procurement_detail', po_id=po_id)

    # GET — show the receiving form pre-filled with ordered quantities
    items = po.items.select_related('material', 'material__category')

    return render(request, 'procurement/procurement_receive_form.html', {
        'po':    po,
        'items': items,
        'form':  form,
    })


# ─────────────────────────────────────────────────────────────
# PRIVATE HELPERS
# ─────────────────────────────────────────────────────────────

def _materials_json():
    """
    JSON list of active materials with cost info for JS auto-fill.
    """
    import json
    materials = Material.objects.filter(is_active=True).values(
        'id', 'name', 'current_cost', 'unit'
    )
    return json.dumps(list(materials), default=str)