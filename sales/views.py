# sales/views.py
# All views for the Sales module. Organised into three groups:
#
# CLIENT VIEWS  — list, create, edit, toggle
# ORDER VIEWS   — list, detail, create, update status, update payment
# ITEM VIEWS    — edit items on an existing Pending order

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction as db_transaction
from django.db.models import Q, Sum

from accounts.utils import log_action
from accounts.decorators import role_required, admin_required, sales_required
from materials.models import Material
from inventory.utils import apply_stock_out

from .models import Client, Order, OrderItem
from .forms import (
    ClientForm, OrderForm, OrderItemFormSet,
    PaymentStatusForm, OrderNotesForm,
)


# ─────────────────────────────────────────────────────────────
# CLIENT VIEWS
# ─────────────────────────────────────────────────────────────

@login_required
@role_required('Admin', 'Sales', 'Warehouse')
def client_list_view(request):
    """
    Lists all clients with search and type filtering.
    Warehouse can view (they need to know who orders come from).
    """
    clients = Client.objects.filter(is_active=True).order_by('client_name')

    search      = request.GET.get('search', '').strip()
    type_filter = request.GET.get('type', '')

    if search:
        clients = clients.filter(
            Q(client_name__icontains=search) |
            Q(contact_person__icontains=search) |
            Q(phone__icontains=search)
        )
    if type_filter:
        clients = clients.filter(client_type=type_filter)

    return render(request, 'sales/client_list.html', {
        'clients':     clients,
        'search':      search,
        'type_filter': type_filter,
    })


@login_required
@role_required('Admin', 'Sales')
def client_create_view(request):
    """Add a new client. Sales and Admin only."""
    form = ClientForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        client = form.save()

        log_action(
            user=request.user, action_type='OTHER',
            table_affected='sales_client', record_id=client.pk,
            description=f"Added client: {client.client_name}",
            request=request
        )
        messages.success(request, f"Client '{client.client_name}' added.")
        return redirect('sales:client_list')

    return render(request, 'sales/client_form.html', {
        'form': form, 'form_title': 'Add Client',
    })


@login_required
@role_required('Admin', 'Sales')
def client_edit_view(request, client_id):
    """Edit an existing client."""
    client = get_object_or_404(Client, pk=client_id)
    form   = ClientForm(request.POST or None, instance=client)

    if request.method == 'POST' and form.is_valid():
        form.save()
        log_action(
            user=request.user, action_type='OTHER',
            table_affected='sales_client', record_id=client.pk,
            description=f"Edited client: {client.client_name}",
            request=request
        )
        messages.success(request, f"Client '{client.client_name}' updated.")
        return redirect('sales:client_list')

    return render(request, 'sales/client_form.html', {
        'form': form,
        'form_title': f'Edit Client: {client.client_name}',
        'client': client,
    })


@login_required
@role_required('Admin', 'Sales')
def client_toggle_view(request, client_id):
    """Toggle client active/inactive. POST only."""
    client = get_object_or_404(Client, pk=client_id)

    if request.method == 'POST':
        client.is_active = not client.is_active
        client.save()
        state = "activated" if client.is_active else "deactivated"
        messages.success(request, f"Client '{client.client_name}' {state}.")
        log_action(
            user=request.user, action_type='OTHER',
            table_affected='sales_client', record_id=client.pk,
            description=f"Client {state}: {client.client_name}",
            request=request
        )
    return redirect('sales:client_list')


# ─────────────────────────────────────────────────────────────
# ORDER LIST & DETAIL
# ─────────────────────────────────────────────────────────────

@login_required
@role_required('Admin', 'Sales', 'Warehouse')
def order_list_view(request):
    """
    Lists all orders. Sales only sees their own orders unless Admin.
    Supports filtering by status, payment status, and search.
    """
    orders = Order.objects.select_related(
        'client', 'created_by'
    ).order_by('-order_date')

    # Sales personnel only see orders they created
    # Admin and Warehouse see all orders
    user_role = request.user.get_role_name()
    if user_role == 'Sales':
        orders = orders.filter(created_by=request.user)

    # ── Filters ──
    status_filter  = request.GET.get('status', '')
    payment_filter = request.GET.get('payment', '')
    search         = request.GET.get('search', '').strip()

    if status_filter:
        orders = orders.filter(status=status_filter)
    if payment_filter:
        orders = orders.filter(payment_status=payment_filter)
    if search:
        orders = orders.filter(
            Q(client__client_name__icontains=search) |
            Q(pk__icontains=search)
        )

    # Summary counts for the filter tabs
    all_orders = Order.objects.all()
    if user_role == 'Sales':
        all_orders = all_orders.filter(created_by=request.user)

    counts = {
        'all':       all_orders.count(),
        'pending':   all_orders.filter(status='Pending').count(),
        'confirmed': all_orders.filter(status='Confirmed').count(),
        'preparing': all_orders.filter(status='Preparing').count(),
        'delivery':  all_orders.filter(status='Out for Delivery').count(),
        'completed': all_orders.filter(status='Completed').count(),
    }

    return render(request, 'sales/order_list.html', {
        'orders':         orders,
        'counts':         counts,
        'status_filter':  status_filter,
        'payment_filter': payment_filter,
        'search':         search,
    })


@login_required
@role_required('Admin', 'Sales', 'Warehouse')
def order_detail_view(request, order_id):
    """
    Full order detail — items, totals, status timeline, and action buttons.
    This page is the hub for all order operations.
    """
    order = get_object_or_404(
        Order.objects.select_related('client', 'created_by'),
        pk=order_id
    )
    items = order.items.select_related('material', 'material__category')

    payment_form = PaymentStatusForm(instance=order)
    notes_form   = OrderNotesForm(instance=order)

    return render(request, 'sales/order_detail.html', {
        'order':         order,
        'items':         items,
        'next_statuses': order.get_next_statuses(),
        'status_steps': [
            'Pending',
            'Confirmed',
            'Preparing',
            'Out for Delivery',
            'Completed',
        ],
        'payment_form':  payment_form,
        'notes_form':    notes_form,
    })


# ─────────────────────────────────────────────────────────────
# ORDER CREATION
# ─────────────────────────────────────────────────────────────

@login_required
@role_required('Admin', 'Sales')
@db_transaction.atomic
def order_create_view(request):
    """
    Creates a new order with one or more line items in a single form.

    Uses Django's inlineformset_factory so the header (Order) and all
    items (OrderItems) are saved together in one POST request.

    The @db_transaction.atomic decorator means: if saving ANY item fails,
    the entire order (including the header row) is rolled back. This
    prevents partially-saved orphan orders.
    """
    order_form   = OrderForm(request.POST or None)
    # prefix='items' namespaces the formset fields to avoid name clashes
    item_formset = OrderItemFormSet(request.POST or None, prefix='items')

    if request.method == 'POST':
        if order_form.is_valid() and item_formset.is_valid():

            # 1. Save the order header (don't commit yet — set created_by first)
            order            = order_form.save(commit=False)
            order.created_by = request.user
            order.save()

            # 2. Attach and save all item rows from the formset
            item_formset.instance = order
            items = item_formset.save(commit=False)

            for item in items:
                # Auto-fill price_at_sale from the material's current selling price
                # if the Sales person left it blank (a quality-of-life default)
                if not item.price_at_sale:
                    item.price_at_sale = item.material.selling_price
                item.save()

            # Handle deleted rows from the formset
            for deleted in item_formset.deleted_objects:
                deleted.delete()

            # 3. Recalculate the order total from all saved items
            order.recalculate_total()

            log_action(
                user=request.user, action_type='CREATE_ORDER',
                table_affected='sales_order', record_id=order.pk,
                description=(
                    f"Created Order #{order.pk} for {order.client.client_name}. "
                    f"Total: ₱{order.total_amount}. Items: {order.items.count()}."
                ),
                request=request
            )

            messages.success(
                request,
                f"Order #{order.pk} created for {order.client.client_name}. "
                f"Total: ₱{order.total_amount}."
            )
            return redirect('sales:order_detail', order_id=order.pk)

    return render(request, 'sales/order_form.html', {
        'order_form':   order_form,
        'item_formset': item_formset,
        'form_title':   'Create New Order',
        # Pass materials data as JSON for the JS price auto-fill feature
        'materials_json': _materials_json(),
    })


@login_required
@role_required('Admin', 'Sales')
@db_transaction.atomic
def order_edit_items_view(request, order_id):
    """
    Edit the items on a Pending order.
    Once an order is Confirmed, items are locked — status must be changed first.
    """
    order = get_object_or_404(Order, pk=order_id)

    if not order.can_edit_items():
        messages.error(
            request,
            f"Order #{order.pk} is '{order.status}' and can no longer be edited. "
            "Only Pending orders can have their items changed."
        )
        return redirect('sales:order_detail', order_id=order.pk)

    item_formset = OrderItemFormSet(
        request.POST or None,
        instance=order,
        prefix='items'
    )

    if request.method == 'POST' and item_formset.is_valid():
        items = item_formset.save(commit=False)

        for item in items:
            if not item.price_at_sale:
                item.price_at_sale = item.material.selling_price
            item.save()

        for deleted in item_formset.deleted_objects:
            deleted.delete()

        order.recalculate_total()

        log_action(
            user=request.user, action_type='UPDATE_ORDER',
            table_affected='sales_order', record_id=order.pk,
            description=f"Edited items on Order #{order.pk}. New total: ₱{order.total_amount}.",
            request=request
        )

        messages.success(request, f"Order #{order.pk} items updated. New total: ₱{order.total_amount}.")
        return redirect('sales:order_detail', order_id=order.pk)

    return render(request, 'sales/order_form.html', {
        'order_form':   None,       # No header form needed — editing items only
        'item_formset': item_formset,
        'order':        order,
        'form_title':   f'Edit Items — Order #{order.pk}',
        'materials_json': _materials_json(),
    })


# ─────────────────────────────────────────────────────────────
# ORDER STATUS & PAYMENT UPDATES
# ─────────────────────────────────────────────────────────────

@login_required
@role_required('Admin', 'Sales')
@db_transaction.atomic
def order_update_status_view(request, order_id):
    """
    Advances an order to the next status in the workflow.
    Validates that the transition is legal (no skipping steps).

    KEY BUSINESS RULE:
    When status moves to 'Preparing', we deduct stock for each item.
    We only do this ONCE (tracked by order.stock_deducted flag) to
    prevent double-deductions if someone clicks the button twice.
    """
    order      = get_object_or_404(Order, pk=order_id)
    new_status = request.POST.get('new_status', '')

    if request.method != 'POST':
        return redirect('sales:order_detail', order_id=order.pk)

    # Validate the transition is legal
    allowed = order.get_next_statuses()
    if new_status not in allowed:
        messages.error(
            request,
            f"Cannot move Order #{order.pk} from '{order.status}' to '{new_status}'."
        )
        return redirect('sales:order_detail', order_id=order.pk)

    old_status = order.status
    order.status = new_status

    # ── Stock Deduction on 'Preparing' ──
    # This is when warehouse staff start physically pulling items from shelves.
    if new_status == 'Preparing' and not order.stock_deducted:
        stock_errors = []

        for item in order.items.select_related('material'):
            try:
                apply_stock_out(
                    material       = item.material,
                    quantity       = item.quantity,
                    user           = request.user,
                    reference_type = 'SALES_ORDER',
                    reference_id   = order.pk,
                    remarks        = (
                        f"Order #{order.pk} — {order.client.client_name}. "
                        f"Deducted {item.quantity} {item.material.unit}."
                    ),
                )
            except ValueError as e:
                stock_errors.append(str(e))

        if stock_errors:
            # If ANY item has insufficient stock, abort the entire status change.
            # The @atomic decorator rolls back all stock_out calls made so far.
            messages.error(
                request,
                "Cannot move to Preparing — insufficient stock for some items: "
                + " | ".join(stock_errors)
            )
            return redirect('sales:order_detail', order_id=order.pk)

        # All stock deductions succeeded — mark the flag so we never deduct again
        order.stock_deducted = True

    order.save()

    log_action(
        user=request.user, action_type='UPDATE_ORDER',
        table_affected='sales_order', record_id=order.pk,
        description=(
            f"Order #{order.pk} status changed: {old_status} → {new_status}. "
            f"Client: {order.client.client_name}."
            + (" (Stock deducted from inventory.)" if new_status == 'Preparing' else "")
        ),
        request=request
    )

    messages.success(
        request,
        f"Order #{order.pk} moved to '{new_status}'."
        + (" Stock has been deducted from inventory." if new_status == 'Preparing' else "")
    )
    return redirect('sales:order_detail', order_id=order.pk)


@login_required
@role_required('Admin', 'Sales')
def order_update_payment_view(request, order_id):
    """Updates only the payment status of an order (POST only)."""
    order = get_object_or_404(Order, pk=order_id)

    if request.method == 'POST':
        form = PaymentStatusForm(request.POST, instance=order)
        if form.is_valid():
            form.save()
            log_action(
                user=request.user, action_type='UPDATE_ORDER',
                table_affected='sales_order', record_id=order.pk,
                description=(
                    f"Payment status for Order #{order.pk} "
                    f"updated to '{order.payment_status}'."
                ),
                request=request
            )
            messages.success(
                request,
                f"Payment status updated to '{order.payment_status}'."
            )

    return redirect('sales:order_detail', order_id=order.pk)


@login_required
@role_required('Admin', 'Sales')
def order_update_notes_view(request, order_id):
    """Updates only the notes field on an order (POST only)."""
    order = get_object_or_404(Order, pk=order_id)

    if request.method == 'POST':
        form = OrderNotesForm(request.POST, instance=order)
        if form.is_valid():
            form.save()
            messages.success(request, "Order notes updated.")

    return redirect('sales:order_detail', order_id=order.pk)


@login_required
@role_required('Admin', 'Sales')
def order_cancel_view(request, order_id):
    """
    Cancels an order. Only allowed if stock has NOT been deducted yet
    (i.e., order hasn't reached Preparing status).
    If stock WAS already deducted, Admin must manually do a Stock In adjustment.
    """
    order = get_object_or_404(Order, pk=order_id)

    if request.method == 'POST':
        if order.status in ('Completed', 'Cancelled'):
            messages.error(request, f"Order #{order.pk} cannot be cancelled — it is already {order.status}.")
            return redirect('sales:order_detail', order_id=order.pk)

        if order.stock_deducted:
            messages.warning(
                request,
                f"Order #{order.pk} cancelled. NOTE: Stock was already deducted when the order "
                "moved to Preparing. Please create a Stock In adjustment to restore inventory."
            )
        else:
            messages.success(request, f"Order #{order.pk} cancelled.")

        order.status = 'Cancelled'
        order.save()

        log_action(
            user=request.user, action_type='UPDATE_ORDER',
            table_affected='sales_order', record_id=order.pk,
            description=f"Order #{order.pk} cancelled. Client: {order.client.client_name}.",
            request=request
        )

    return redirect('sales:order_list')


# ─────────────────────────────────────────────────────────────
# PRIVATE HELPERS
# ─────────────────────────────────────────────────────────────

def _materials_json():
    """
    Returns a JSON-serialisable list of active materials with their
    current selling prices. Used by JavaScript to auto-fill the
    price_at_sale field when a material is selected on the order form.
    """
    import json
    materials = Material.objects.filter(is_active=True).values(
        'id', 'name', 'selling_price', 'unit'
    )
    return json.dumps(list(materials), default=str)