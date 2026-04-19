# delivery/views.py
# All delivery views, organised into three groups:
#
# SCHEDULING VIEWS  → list, detail, create, edit
# STATUS VIEWS      → advance status, complete (mark as Received)
# DRIVER VIEWS      → driver's own dashboard and mobile-friendly detail

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction as db_transaction
from django.db.models import Q
from django.utils import timezone

from accounts.utils import log_action
from accounts.decorators import role_required, admin_required
from sales.models import Order
from architecture.models import MaterialRequest

from .models import Delivery, DeliveryStatusLog
from .forms import (
    DeliveryCreateForm, DeliveryUpdateForm,
    StatusUpdateForm, CompletionForm,
)


# ─────────────────────────────────────────────────────────────
# SCHEDULING VIEWS
# ─────────────────────────────────────────────────────────────

@login_required
@role_required('Admin', 'Sales', 'Warehouse', 'Driver')
def delivery_list_view(request):
    """
    Lists all deliveries.
    Drivers only see their own assigned deliveries.
    All other roles see everything.
    """
    role      = request.user.get_role_name()
    deliveries = Delivery.objects.select_related(
        'order__client', 'request__project', 'driver'
    ).order_by('-schedule_date', '-created_at')

    # Drivers see only their deliveries
    if role == 'Driver':
        deliveries = deliveries.filter(driver=request.user)

    # ── Filters ──
    status_filter = request.GET.get('status', '')
    type_filter   = request.GET.get('type', '')
    search        = request.GET.get('search', '').strip()
    date_filter   = request.GET.get('date', '')

    if status_filter:
        deliveries = deliveries.filter(status=status_filter)
    if type_filter:
        deliveries = deliveries.filter(delivery_type=type_filter)
    if date_filter:
        deliveries = deliveries.filter(schedule_date=date_filter)
    if search:
        deliveries = deliveries.filter(
            Q(driver_name__icontains=search)       |
            Q(end_location__icontains=search)      |
            Q(order__client__client_name__icontains=search) |
            Q(request__project__project_name__icontains=search) |
            Q(dr_number__icontains=search)
        )

    # Summary counts for filter tabs
    base_qs = Delivery.objects.all()
    if role == 'Driver':
        base_qs = base_qs.filter(driver=request.user)

    counts = {
        'all':       base_qs.count(),
        'scheduled': base_qs.filter(status='Scheduled').count(),
        'out':       base_qs.filter(status='Out for Delivery').count(),
        'arrived':   base_qs.filter(status='Arrived').count(),
        'received':  base_qs.filter(status='Received').count(),
    }

    return render(request, 'delivery/delivery_list.html', {
        'deliveries':    deliveries,
        'counts':        counts,
        'status_filter': status_filter,
        'type_filter':   type_filter,
        'search':        search,
        'date_filter':   date_filter,
    })


@login_required
@role_required('Admin', 'Sales', 'Warehouse', 'Driver')
def delivery_detail_view(request, delivery_id):
    """
    Full delivery detail with status timeline, action buttons,
    and the completion form (DR number, received_by, delays).
    """
    delivery = get_object_or_404(
        Delivery.objects.select_related(
            'order__client', 'request__project',
            'driver', 'created_by'
        ),
        pk=delivery_id
    )

    # Drivers can only see their own deliveries
    role = request.user.get_role_name()
    if role == 'Driver' and delivery.driver != request.user:
        messages.error(request, "You can only view your own assigned deliveries.")
        return redirect('delivery:delivery_list')

    status_logs     = delivery.status_logs.select_related('changed_by')
    next_statuses   = delivery.get_next_statuses()
    completion_form = CompletionForm(instance=delivery)

    return render(request, 'delivery/delivery_detail.html', {
        'delivery':        delivery,
        'status_logs':     status_logs,
        'next_statuses':   next_statuses,
        'completion_form': completion_form,
        'status_form':     StatusUpdateForm(),
    })


@login_required
@role_required('Admin', 'Sales')
def delivery_create_view(request):
    """
    Schedule a new delivery.
    Can be pre-filled from the Sales Order detail page (?order=ID)
    or from the Architecture Material Request detail page (?request=ID).
    """
    # Pre-fill from URL params
    initial = {}
    preload_order   = request.GET.get('order')
    preload_request = request.GET.get('request')

    if preload_order:
        initial['delivery_type'] = 'Sales Order'
        initial['order']         = preload_order
        # Auto-fill the destination from the order's client
        try:
            o = Order.objects.select_related('client').get(pk=preload_order)
            initial['end_location']  = o.client.address
        except Order.DoesNotExist:
            pass

    elif preload_request:
        initial['delivery_type'] = 'Architecture Request'
        initial['request']       = preload_request
        try:
            mr = MaterialRequest.objects.select_related('project').get(pk=preload_request)
            initial['end_location'] = mr.project.location
        except MaterialRequest.DoesNotExist:
            pass

    form = DeliveryCreateForm(request.POST or None, initial=initial)

    if request.method == 'POST' and form.is_valid():
        delivery            = form.save(commit=False)
        delivery.created_by = request.user
        delivery.save()

        # Create the first status log entry
        DeliveryStatusLog.objects.create(
            delivery   = delivery,
            old_status = '',
            new_status = 'Scheduled',
            changed_by = request.user,
            notes      = 'Delivery scheduled.',
        )

        # If this is for a Sales Order, advance the order to 'Out for Delivery'
        if delivery.order and delivery.order.status == 'Preparing':
            delivery.order.status = 'Out for Delivery'
            delivery.order.save()

        log_action(
            user=request.user, action_type='UPDATE_DELIVERY',
            table_affected='delivery_delivery', record_id=delivery.pk,
            description=(
                f"Scheduled Delivery #{delivery.pk} for {delivery.source_label}. "
                f"Driver: {delivery.driver_name}. Date: {delivery.schedule_date}."
            ),
            request=request
        )

        messages.success(
            request,
            f"Delivery #{delivery.pk} scheduled for {delivery.schedule_date}. "
            f"Driver: {delivery.driver_name}."
        )
        return redirect('delivery:delivery_detail', delivery_id=delivery.pk)

    # Determine available orders / requests for the dropdowns
    available_orders   = Order.objects.filter(
        status__in=['Preparing', 'Out for Delivery']
    ).select_related('client')
    available_requests = MaterialRequest.objects.filter(
        status__in=['Approved', 'Partially Fulfilled']
    ).select_related('project')

    return render(request, 'delivery/delivery_form.html', {
        'form':               form,
        'form_title':         'Schedule New Delivery',
        'available_orders':   available_orders,
        'available_requests': available_requests,
    })


@login_required
@role_required('Admin', 'Sales')
def delivery_edit_view(request, delivery_id):
    """
    Edit scheduling details. Only available while status = 'Scheduled'.
    Once a delivery is Out for Delivery, only the Driver can update it.
    """
    delivery = get_object_or_404(Delivery, pk=delivery_id)

    if delivery.status != 'Scheduled':
        messages.error(
            request,
            f"Delivery #{delivery.pk} is already '{delivery.status}'. "
            "Only Scheduled deliveries can be edited."
        )
        return redirect('delivery:delivery_detail', delivery_id=delivery_id)

    form = DeliveryUpdateForm(request.POST or None, instance=delivery)

    if request.method == 'POST' and form.is_valid():
        form.save()
        log_action(
            user=request.user, action_type='UPDATE_DELIVERY',
            table_affected='delivery_delivery', record_id=delivery.pk,
            description=f"Edited scheduling details for Delivery #{delivery.pk}.",
            request=request
        )
        messages.success(request, f"Delivery #{delivery.pk} updated.")
        return redirect('delivery:delivery_detail', delivery_id=delivery_id)

    return render(request, 'delivery/delivery_form.html', {
        'form':       form,
        'form_title': f'Edit Delivery #{delivery.pk}',
        'delivery':   delivery,
    })


# ─────────────────────────────────────────────────────────────
# STATUS VIEWS
# ─────────────────────────────────────────────────────────────

@login_required
@role_required('Admin', 'Sales', 'Driver')
@db_transaction.atomic
def delivery_update_status_view(request, delivery_id):
    """
    Advances or changes the delivery status.
    Drivers can advance their own deliveries.
    Sales and Admin can advance any delivery.

    Special behaviour when moving to 'Out for Delivery':
    → Updates the linked Sales Order status to 'Out for Delivery'.

    Special behaviour when moving to 'Received':
    → Redirects to the completion form to capture DR number and delay info.
    → Updates the linked Sales Order to 'Completed'.
    """
    delivery   = get_object_or_404(Delivery, pk=delivery_id)
    role       = request.user.get_role_name()

    # Drivers can only update their own deliveries
    if role == 'Driver' and delivery.driver != request.user:
        messages.error(request, "You can only update your own assigned deliveries.")
        return redirect('delivery:delivery_list')

    if request.method != 'POST':
        return redirect('delivery:delivery_detail', delivery_id=delivery_id)

    new_status = request.POST.get('new_status', '').strip()
    notes      = request.POST.get('notes', '').strip()

    # Validate the transition
    allowed = delivery.get_next_statuses()
    if new_status not in allowed:
        messages.error(
            request,
            f"Cannot move Delivery #{delivery.pk} from "
            f"'{delivery.status}' to '{new_status}'."
        )
        return redirect('delivery:delivery_detail', delivery_id=delivery_id)

    # If moving to Received, handle via the completion form instead
    if new_status == 'Received':
        return redirect('delivery:delivery_complete', delivery_id=delivery_id)

    old_status       = delivery.status
    delivery.status  = new_status
    delivery.save()

    # ── Side effects on status changes ──────────────────

    # When leaving for delivery: mark order as Out for Delivery
    if new_status == 'Out for Delivery' and delivery.order:
        if delivery.order.status in ('Preparing', 'Confirmed'):
            delivery.order.status = 'Out for Delivery'
            delivery.order.save()

    # When cancelled: revert order if nothing else is delivering it
    if new_status == 'Cancelled' and delivery.order:
        other_active = Delivery.objects.filter(
            order=delivery.order
        ).exclude(pk=delivery.pk).exclude(
            status__in=['Cancelled', 'Received']
        ).exists()
        if not other_active and delivery.order.status == 'Out for Delivery':
            delivery.order.status = 'Preparing'
            delivery.order.save()

    # ── Append status log ────────────────────────────────
    DeliveryStatusLog.objects.create(
        delivery   = delivery,
        old_status = old_status,
        new_status = new_status,
        changed_by = request.user,
        notes      = notes,
    )

    log_action(
        user=request.user, action_type='UPDATE_DELIVERY',
        table_affected='delivery_delivery', record_id=delivery.pk,
        description=(
            f"Delivery #{delivery.pk} status: {old_status} → {new_status}. "
            f"{('Notes: ' + notes) if notes else ''}"
        ),
        request=request
    )

    messages.success(
        request,
        f"Delivery #{delivery.pk} moved to '{new_status}'."
    )
    return redirect('delivery:delivery_detail', delivery_id=delivery_id)


@login_required
@role_required('Admin', 'Sales', 'Driver')
@db_transaction.atomic
def delivery_complete_view(request, delivery_id):
    """
    Marks a delivery as Received and records the completion details:
    - Delivery Receipt (DR) number
    - Name of person who signed / received
    - Any delay flags and remarks

    Also marks the linked Sales Order as Completed.
    """
    delivery = get_object_or_404(Delivery, pk=delivery_id)
    role     = request.user.get_role_name()

    if role == 'Driver' and delivery.driver != request.user:
        messages.error(request, "You can only complete your own deliveries.")
        return redirect('delivery:delivery_list')

    if delivery.status not in ('Arrived', 'Out for Delivery'):
        messages.error(
            request,
            f"Delivery #{delivery.pk} must be 'Arrived' or "
            "'Out for Delivery' before marking as Received."
        )
        return redirect('delivery:delivery_detail', delivery_id=delivery_id)

    form = CompletionForm(request.POST or None, instance=delivery)

    if request.method == 'POST' and form.is_valid():
        old_status       = delivery.status
        delivery         = form.save(commit=False)
        delivery.status  = 'Received'
        delivery.delivered_at = timezone.now()
        delivery.save()

        # ── Mark the linked order as Completed ──────────
        if delivery.order and delivery.order.status == 'Out for Delivery':
            delivery.order.status = 'Completed'
            delivery.order.save()

        # ── Log the status change ────────────────────────
        DeliveryStatusLog.objects.create(
            delivery   = delivery,
            old_status = old_status,
            new_status = 'Received',
            changed_by = request.user,
            notes      = (
                f"DR#{delivery.dr_number}. "
                f"Received by: {delivery.received_by}. "
                + (f"Delays: {delivery.delay_remarks}" if delivery.is_delayed else "No delays.")
            ),
        )

        log_action(
            user=request.user, action_type='UPDATE_DELIVERY',
            table_affected='delivery_delivery', record_id=delivery.pk,
            description=(
                f"Delivery #{delivery.pk} completed (Received). "
                f"DR#: {delivery.dr_number}. "
                f"Received by: {delivery.received_by}. "
                + (f"DELAYED — {delivery.delay_remarks}" if delivery.is_delayed else "")
            ),
            request=request
        )

        messages.success(
            request,
            f"Delivery #{delivery.pk} marked as Received. "
            f"DR#: {delivery.dr_number or 'Not recorded'}."
            + (" Order marked Completed." if delivery.order else "")
        )
        return redirect('delivery:delivery_detail', delivery_id=delivery_id)

    return render(request, 'delivery/delivery_complete_form.html', {
        'form':     form,
        'delivery': delivery,
    })


# ─────────────────────────────────────────────────────────────
# DRIVER DASHBOARD
# ─────────────────────────────────────────────────────────────

@login_required
@role_required('Admin', 'Sales', 'Driver')
def driver_dashboard_view(request):
    """
    Mobile-friendly dashboard for Drivers.
    Shows today's deliveries at the top, then upcoming ones.
    Designed for quick access on a smartphone in the truck.
    """
    from django.utils import timezone
    today = timezone.localdate()

    role = request.user.get_role_name()

    # If Admin or Sales is viewing the driver dashboard, show all drivers
    # If a Driver is viewing, show only their deliveries
    base_qs = Delivery.objects.select_related(
        'order__client', 'request__project', 'driver'
    )
    if role == 'Driver':
        base_qs = base_qs.filter(driver=request.user)

    today_deliveries    = base_qs.filter(
        schedule_date=today,
        status__in=['Scheduled', 'Out for Delivery', 'Arrived']
    ).order_by('schedule_date')

    upcoming_deliveries = base_qs.filter(
        schedule_date__gt=today,
        status='Scheduled'
    ).order_by('schedule_date')[:10]

    recent_completed = base_qs.filter(
        status='Received'
    ).order_by('-delivered_at')[:5]

    return render(request, 'delivery/driver_dashboard.html', {
        'today':              today,
        'today_deliveries':   today_deliveries,
        'upcoming_deliveries': upcoming_deliveries,
        'recent_completed':   recent_completed,
    })