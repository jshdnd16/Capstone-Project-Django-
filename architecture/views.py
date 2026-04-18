# architecture/views.py
# Views for the Architecture module. Organised into three groups:
#
# PROJECT VIEWS         → list, detail, create, edit, update status
# BOQ VIEWS             → create new version, view, finalise
# MATERIAL REQUEST VIEWS → create, detail, approve/reject, fulfil

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction as db_transaction
from django.db.models import Q, Sum

from accounts.utils import log_action
from accounts.decorators import role_required, admin_required
from inventory.utils import apply_stock_out
from materials.models import Material

from .models import Project, BOQHeader, BOQItem, MaterialRequest, MaterialRequestItem
from .forms import (
    ProjectForm, BOQHeaderForm, BOQItemFormSet,
    MaterialRequestForm, MaterialRequestItemFormSet,
    ApprovalForm,
)


# ─────────────────────────────────────────────────────────────
# PROJECT VIEWS
# ─────────────────────────────────────────────────────────────

@login_required
@role_required('Admin', 'Architect', 'Sales', 'Warehouse')
def project_list_view(request):
    """
    Lists all projects. Architects see only their own.
    Admin/Sales/Warehouse see all for visibility.
    """
    projects = Project.objects.select_related('architect').order_by('-created_at')

    # Architects see only their own projects
    role = request.user.get_role_name()
    if role == 'Architect':
        projects = projects.filter(architect=request.user)

    # ── Filters ──
    status_filter = request.GET.get('status', '')
    search        = request.GET.get('search', '').strip()

    if status_filter:
        projects = projects.filter(status=status_filter)
    if search:
        projects = projects.filter(
            Q(project_name__icontains=search) |
            Q(client_name__icontains=search) |
            Q(location__icontains=search)
        )

    # Summary counts for filter tabs
    all_projects = Project.objects.all()
    if role == 'Architect':
        all_projects = all_projects.filter(architect=request.user)

    counts = {
        'all':       all_projects.count(),
        'planning':  all_projects.filter(status='Planning').count(),
        'ongoing':   all_projects.filter(status='Ongoing').count(),
        'on_hold':   all_projects.filter(status='On Hold').count(),
        'completed': all_projects.filter(status='Completed').count(),
    }

    return render(request, 'architecture/project_list.html', {
        'projects':      projects,
        'counts':        counts,
        'status_filter': status_filter,
        'search':        search,
    })


@login_required
@role_required('Admin', 'Architect', 'Sales', 'Warehouse')
def project_detail_view(request, project_id):
    """
    Full project detail: BOQ history, material requests, and quick actions.
    The hub for all project-related operations.
    """
    project  = get_object_or_404(Project, pk=project_id)
    boqs     = project.boqs.select_related('created_by').order_by('-version')
    requests = project.material_requests.select_related('architect').order_by('-request_date')

    return render(request, 'architecture/project_detail.html', {
        'project':  project,
        'boqs':     boqs,
        'requests': requests,
    })


@login_required
@role_required('Admin', 'Architect')
def project_create_view(request):
    """Create a new project. Architect and Admin only."""
    form = ProjectForm(request.POST or None)

    # Pre-fill architect field if the current user is an Architect
    if request.method == 'GET':
        role = request.user.get_role_name()
        if role == 'Architect':
            form = ProjectForm(initial={'architect': request.user})

    if request.method == 'POST' and form.is_valid():
        project = form.save()
        log_action(
            user=request.user, action_type='CREATE_PROJECT',
            table_affected='architecture_project', record_id=project.pk,
            description=f"Created project: {project.project_name} for {project.client_name}",
            request=request
        )
        messages.success(request, f"Project '{project.project_name}' created.")
        return redirect('architecture:project_detail', project_id=project.pk)

    return render(request, 'architecture/project_form.html', {
        'form': form, 'form_title': 'Create New Project',
    })


@login_required
@role_required('Admin', 'Architect')
def project_edit_view(request, project_id):
    """Edit an existing project."""
    project = get_object_or_404(Project, pk=project_id)

    # Architects can only edit their own projects
    if request.user.get_role_name() == 'Architect' and project.architect != request.user:
        messages.error(request, "You can only edit your own projects.")
        return redirect('architecture:project_list')

    form = ProjectForm(request.POST or None, instance=project)

    if request.method == 'POST' and form.is_valid():
        form.save()
        log_action(
            user=request.user, action_type='OTHER',
            table_affected='architecture_project', record_id=project.pk,
            description=f"Edited project: {project.project_name}",
            request=request
        )
        messages.success(request, f"Project '{project.project_name}' updated.")
        return redirect('architecture:project_detail', project_id=project.pk)

    return render(request, 'architecture/project_form.html', {
        'form': form,
        'form_title': f'Edit Project: {project.project_name}',
        'project': project,
    })


@login_required
@role_required('Admin', 'Architect')
def project_update_status_view(request, project_id):
    """
    Quick status update for a project. POST only.
    Used by the detail page's status buttons.
    """
    project    = get_object_or_404(Project, pk=project_id)
    new_status = request.POST.get('new_status', '')

    valid = [c[0] for c in Project.STATUS_CHOICES]
    if request.method == 'POST' and new_status in valid:
        old_status    = project.status
        project.status = new_status
        project.save()
        log_action(
            user=request.user, action_type='OTHER',
            table_affected='architecture_project', record_id=project.pk,
            description=f"Project '{project.project_name}' status: {old_status} → {new_status}",
            request=request
        )
        messages.success(request, f"Project status updated to '{new_status}'.")

    return redirect('architecture:project_detail', project_id=project.pk)


# ─────────────────────────────────────────────────────────────
# BOQ VIEWS
# ─────────────────────────────────────────────────────────────

@login_required
@role_required('Admin', 'Architect')
@db_transaction.atomic
def boq_create_view(request, project_id):
    """
    Creates a new BOQ version for the given project.

    Version number is automatically set to max(existing) + 1.
    If there are no previous BOQs, starts at version 1.

    The Architect fills in the items; the header version/project
    are set by the view before saving.
    """
    project = get_object_or_404(Project, pk=project_id)

    # Auto-calculate next version number
    last_version = project.boqs.aggregate(max_v=Sum('version'))['max_v'] or 0
    next_version = (project.boqs.count()) + 1

    header_form   = BOQHeaderForm(request.POST or None)
    item_formset  = BOQItemFormSet(request.POST or None, prefix='boq_items')

    if request.method == 'POST' and header_form.is_valid() and item_formset.is_valid():
        # Save the header
        boq              = header_form.save(commit=False)
        boq.project      = project
        boq.version      = next_version
        boq.created_by   = request.user
        boq.save()

        # Save items
        item_formset.instance = boq
        items = item_formset.save(commit=False)
        for item in items:
            # Auto-fill unit_cost from the material's current cost if blank
            if not item.unit_cost:
                item.unit_cost = item.material.current_cost
            item.save()
        for deleted in item_formset.deleted_objects:
            deleted.delete()

        boq.recalculate_total()

        # If marked as final, unmark all other versions for this project
        if boq.is_final:
            project.boqs.exclude(pk=boq.pk).update(is_final=False)

        log_action(
            user=request.user, action_type='OTHER',
            table_affected='architecture_boq', record_id=boq.pk,
            description=(
                f"Created BOQ v{boq.version} for project '{project.project_name}'. "
                f"Items: {boq.items.count()}. Estimate: ₱{boq.total_estimate}."
                + (" [FINAL]" if boq.is_final else " [Draft]")
            ),
            request=request
        )

        messages.success(
            request,
            f"BOQ v{boq.version} created. Total estimate: ₱{boq.total_estimate}."
            + (" Marked as FINAL." if boq.is_final else " Saved as Draft.")
        )
        return redirect('architecture:boq_detail', boq_id=boq.pk)

    return render(request, 'architecture/boq_form.html', {
        'project':      project,
        'header_form':  header_form,
        'item_formset': item_formset,
        'next_version': next_version,
        'form_title':   f'Create BOQ v{next_version} — {project.project_name}',
        'materials_json': _materials_json(),
    })


@login_required
@role_required('Admin', 'Architect', 'Sales', 'Warehouse')
def boq_detail_view(request, boq_id):
    """View a BOQ with all its line items."""
    boq   = get_object_or_404(BOQHeader, pk=boq_id)
    items = boq.items.select_related('material', 'material__category', 'supplier')

    # Group totals by source type
    sales_total    = items.filter(source_type='Sales Inventory').aggregate(
        t=Sum('total_cost'))['t'] or 0
    external_total = items.filter(source_type='External').aggregate(
        t=Sum('total_cost'))['t'] or 0

    return render(request, 'architecture/boq_detail.html', {
        'boq':            boq,
        'items':          items,
        'sales_total':    sales_total,
        'external_total': external_total,
    })


@login_required
@role_required('Admin', 'Architect')
def boq_finalise_view(request, boq_id):
    """
    Marks a BOQ as the final/approved version.
    Automatically un-marks all other BOQ versions for the same project.
    POST only.
    """
    boq = get_object_or_404(BOQHeader, pk=boq_id)

    if request.method == 'POST':
        # Unmark all other BOQs for this project
        boq.project.boqs.exclude(pk=boq.pk).update(is_final=False)
        boq.is_final = True
        boq.save()

        log_action(
            user=request.user, action_type='APPROVE',
            table_affected='architecture_boq', record_id=boq.pk,
            description=(
                f"BOQ v{boq.version} for '{boq.project.project_name}' "
                "marked as FINAL."
            ),
            request=request
        )
        messages.success(request, f"BOQ v{boq.version} is now marked as FINAL.")

    return redirect('architecture:boq_detail', boq_id=boq.pk)


# ─────────────────────────────────────────────────────────────
# MATERIAL REQUEST VIEWS
# ─────────────────────────────────────────────────────────────

@login_required
@role_required('Admin', 'Architect', 'Warehouse')
def material_request_list_view(request):
    """
    Lists all material requests.
    Architects see only their own; Admin and Warehouse see all.
    """
    requests = MaterialRequest.objects.select_related(
        'project', 'architect'
    ).order_by('-request_date')

    role = request.user.get_role_name()
    if role == 'Architect':
        requests = requests.filter(architect=request.user)

    status_filter = request.GET.get('status', '')
    search        = request.GET.get('search', '').strip()

    if status_filter:
        requests = requests.filter(status=status_filter)
    if search:
        requests = requests.filter(
            Q(project__project_name__icontains=search) |
            Q(project__client_name__icontains=search)
        )

    # Counts for filter tabs
    base_qs = MaterialRequest.objects.all()
    if role == 'Architect':
        base_qs = base_qs.filter(architect=request.user)

    counts = {
        'all':       base_qs.count(),
        'pending':   base_qs.filter(status='Pending').count(),
        'approved':  base_qs.filter(status='Approved').count(),
        'partial':   base_qs.filter(status='Partially Fulfilled').count(),
        'fulfilled': base_qs.filter(status='Fulfilled').count(),
    }

    return render(request, 'architecture/material_request_list.html', {
        'requests':      requests,
        'counts':        counts,
        'status_filter': status_filter,
        'search':        search,
    })


@login_required
@role_required('Admin', 'Architect')
@db_transaction.atomic
def material_request_create_view(request, project_id=None):
    """
    Create a material request for a project.
    Can be called from the project detail page (?project=ID pre-fills)
    or from the standalone "New Request" button.
    """
    # Pre-select a project if linked from the project detail page
    initial = {}
    if project_id:
        project = get_object_or_404(Project, pk=project_id)
        initial['project'] = project

    request_form = MaterialRequestForm(
        request.POST or None,
        initial=initial,
        architect=request.user
    )
    item_formset = MaterialRequestItemFormSet(
        request.POST or None,
        prefix='mr_items'
    )

    if request.method == 'POST' and request_form.is_valid() and item_formset.is_valid():
        # Save the request header
        mat_request           = request_form.save(commit=False)
        mat_request.architect = request.user
        mat_request.save()

        # Save line items
        item_formset.instance = mat_request
        items = item_formset.save(commit=False)
        for item in items:
            if not item.unit_cost:
                item.unit_cost = item.material.current_cost
            item.save()
        for deleted in item_formset.deleted_objects:
            deleted.delete()

        mat_request.recalculate_total()

        log_action(
            user=request.user, action_type='CREATE_MATERIAL_REQUEST',
            table_affected='architecture_materialrequest', record_id=mat_request.pk,
            description=(
                f"Material Request #{mat_request.pk} created for "
                f"'{mat_request.project.project_name}'. "
                f"Items: {mat_request.request_items.count()}. "
                f"Total: ₱{mat_request.total_amount}."
            ),
            request=request
        )

        messages.success(
            request,
            f"Material Request #{mat_request.pk} submitted. "
            "Awaiting Admin approval."
        )
        return redirect('architecture:material_request_detail',
                        request_id=mat_request.pk)

    return render(request, 'architecture/material_request_form.html', {
        'request_form': request_form,
        'item_formset': item_formset,
        'form_title':   'New Material Request',
        'materials_json': _materials_json(),
    })


@login_required
@role_required('Admin', 'Architect', 'Warehouse')
def material_request_detail_view(request, request_id):
    """Full detail of a material request — items, status, and action buttons."""
    mat_request = get_object_or_404(
        MaterialRequest.objects.select_related('project', 'architect'),
        pk=request_id
    )
    items = mat_request.request_items.select_related(
        'material', 'material__category', 'supplier'
    )
    approval_form = ApprovalForm()

    return render(request, 'architecture/material_request_detail.html', {
        'mat_request':   mat_request,
        'items':         items,
        'approval_form': approval_form,
    })


@login_required
@admin_required
@db_transaction.atomic
def material_request_approve_view(request, request_id):
    """
    Admin approves a material request.

    For items sourced from Sales Inventory:
      → Deduct stock immediately using apply_stock_out()

    For External items:
      → No stock deduction — these come from outside suppliers.
        Tracked separately for procurement purposes (Phase 7).

    If any Sales Inventory item has insufficient stock, the entire
    approval is aborted (atomic transaction rolls back).
    """
    mat_request = get_object_or_404(MaterialRequest, pk=request_id)

    if request.method != 'POST':
        return redirect('architecture:material_request_detail', request_id=request_id)

    if mat_request.status != 'Pending':
        messages.error(
            request,
            f"Request #{mat_request.pk} is already '{mat_request.status}'. "
            "Only Pending requests can be approved."
        )
        return redirect('architecture:material_request_detail', request_id=request_id)

    admin_notes = request.POST.get('admin_notes', '').strip()
    stock_errors = []

    # ── Deduct stock for Sales Inventory items ──
    if not mat_request.stock_deducted:
        for item in mat_request.request_items.filter(source_type='Sales Inventory'):
            try:
                apply_stock_out(
                    material       = item.material,
                    quantity       = int(item.required_qty),
                    user           = request.user,
                    reference_type = 'ARCH_REQUEST',
                    reference_id   = mat_request.pk,
                    remarks        = (
                        f"Material Request #{mat_request.pk} — "
                        f"{mat_request.project.project_name}. "
                        f"Issued {item.required_qty} {item.material.unit}."
                    ),
                )
                # Mark this item as fully fulfilled
                item.fulfilled_qty = item.required_qty
                item.save()
            except ValueError as e:
                stock_errors.append(str(e))

        if stock_errors:
            messages.error(
                request,
                "Cannot approve — insufficient stock for some items: "
                + " | ".join(stock_errors)
            )
            return redirect('architecture:material_request_detail', request_id=request_id)

        mat_request.stock_deducted = True

    # ── Update request status ──
    mat_request.status      = 'Approved'
    mat_request.admin_notes = admin_notes

    # Check if all items are fully fulfilled
    all_items   = mat_request.request_items.all()
    all_done    = all(item.is_fully_fulfilled for item in all_items)
    mat_request.status = 'Fulfilled' if all_done else 'Approved'

    mat_request.save()

    log_action(
        user=request.user, action_type='APPROVE',
        table_affected='architecture_materialrequest', record_id=mat_request.pk,
        description=(
            f"Approved Material Request #{mat_request.pk} for "
            f"'{mat_request.project.project_name}'. "
            "Stock deducted from inventory."
        ),
        request=request
    )

    messages.success(
        request,
        f"Material Request #{mat_request.pk} approved. "
        "Inventory updated for Sales Inventory items."
    )
    return redirect('architecture:material_request_detail', request_id=request_id)


@login_required
@admin_required
def material_request_reject_view(request, request_id):
    """Admin rejects a pending material request."""
    mat_request = get_object_or_404(MaterialRequest, pk=request_id)

    if request.method == 'POST' and mat_request.status == 'Pending':
        admin_notes             = request.POST.get('admin_notes', '').strip()
        mat_request.status      = 'Rejected'
        mat_request.admin_notes = admin_notes
        mat_request.save()

        log_action(
            user=request.user, action_type='OTHER',
            table_affected='architecture_materialrequest', record_id=mat_request.pk,
            description=f"Rejected Material Request #{mat_request.pk}. Reason: {admin_notes}",
            request=request
        )
        messages.warning(request, f"Material Request #{mat_request.pk} rejected.")

    return redirect('architecture:material_request_detail', request_id=request_id)


# ─────────────────────────────────────────────────────────────
# PRIVATE HELPERS
# ─────────────────────────────────────────────────────────────

def _materials_json():
    """
    JSON list of active materials with cost and selling prices.
    Used by JS to auto-fill unit_cost when a material is selected.
    """
    import json
    materials = Material.objects.filter(is_active=True).values(
        'id', 'name', 'current_cost', 'selling_price', 'unit'
    )
    return json.dumps(list(materials), default=str)