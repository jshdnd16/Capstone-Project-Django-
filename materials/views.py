# materials/views.py
# All CRUD views for Categories, Suppliers, and Materials.
#
# Access levels (defined by @role_required decorators):
# - Categories: View → all roles | Create/Edit/Delete → Admin only
# - Suppliers:  View → all roles | Create/Edit → Admin + Warehouse | Toggle → Admin only
# - Materials:  View → all roles | Create/Edit → Admin + Warehouse | Delete → Admin only

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.urls import reverse

from .models import Category, Supplier, Material
from .forms import CategoryForm, SupplierForm, MaterialForm
from accounts.utils import log_action
from accounts.decorators import admin_required, role_required


# ─────────────────────────────────────────────────────────────
# CATEGORY VIEWS
# ─────────────────────────────────────────────────────────────

@login_required
@role_required('Admin', 'Warehouse', 'Sales', 'Architect', 'Driver')
def category_list_view(request):
    """
    Lists all material categories.
    All logged-in users can view; only Admin can add/edit/delete.
    """
    categories = Category.objects.all()

    return render(request, 'materials/category_list.html', {
        'categories': categories,
    })


@login_required
@admin_required
def category_create_view(request):
    """Create a new category. Admin only."""
    form = CategoryForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        category = form.save()

        log_action(
            user=request.user,
            action_type='OTHER',
            table_affected='materials_category',
            record_id=category.pk,
            description=f"Created category: {category.category_name}",
            request=request
        )

        messages.success(request, f"Category '{category.category_name}' created.")
        return redirect('materials:category_list')

    return render(request, 'materials/category_form.html', {
        'form': form,
        'form_title': 'Add Category',
    })


@login_required
@admin_required
def category_edit_view(request, category_id):
    """Edit an existing category. Admin only."""
    category = get_object_or_404(Category, pk=category_id)
    form = CategoryForm(request.POST or None, instance=category)

    if request.method == 'POST' and form.is_valid():
        form.save()

        log_action(
            user=request.user,
            action_type='OTHER',
            table_affected='materials_category',
            record_id=category.pk,
            description=f"Edited category: {category.category_name}",
            request=request
        )

        messages.success(request, f"Category '{category.category_name}' updated.")
        return redirect('materials:category_list')

    return render(request, 'materials/category_form.html', {
        'form': form,
        'form_title': f'Edit Category: {category.category_name}',
        'category': category,
    })


@login_required
@admin_required
def category_delete_view(request, category_id):
    """
    Deletes a category, but only if no materials are using it.
    The PROTECT constraint on Material.category means Django would raise
    a ProtectedError if we tried to delete a category in use — we catch
    this early with a friendly error message instead.
    """
    category = get_object_or_404(Category, pk=category_id)

    # Safety check: refuse if materials are assigned to this category
    material_count = category.materials.count()
    if material_count > 0:
        messages.error(
            request,
            f"Cannot delete '{category.category_name}' — {material_count} material(s) are "
            "assigned to it. Reassign those materials first."
        )
        return redirect('materials:category_list')

    if request.method == 'POST':
        name = category.category_name
        category.delete()

        log_action(
            user=request.user,
            action_type='DELETE',
            table_affected='materials_category',
            description=f"Deleted category: {name}",
            request=request
        )

        messages.success(request, f"Category '{name}' deleted.")
        return redirect('materials:category_list')

    # GET request → show confirmation page
    return render(request, 'materials/confirm_delete.html', {
        'object_name': category.category_name,
        'object_type': 'Category',
        'cancel_url': reverse('materials:category_list'),
    })


# ─────────────────────────────────────────────────────────────
# SUPPLIER VIEWS
# ─────────────────────────────────────────────────────────────

@login_required
@role_required('Admin', 'Warehouse', 'Sales', 'Architect', 'Driver')
def supplier_list_view(request):
    """
    Lists all suppliers with optional filters.
    All roles can view; Admin + Warehouse can edit.
    """
    suppliers = Supplier.objects.all()

    # Optional filters from query params: /materials/suppliers/?status=Active&type=Manufacturer
    status_filter = request.GET.get('status', '')
    type_filter = request.GET.get('type', '')

    if status_filter:
        suppliers = suppliers.filter(status=status_filter)
    if type_filter:
        suppliers = suppliers.filter(supplier_type=type_filter)

    return render(request, 'materials/supplier_list.html', {
        'suppliers': suppliers,
        'status_filter': status_filter,
        'type_filter': type_filter,
    })


@login_required
@role_required('Admin', 'Warehouse')
def supplier_create_view(request):
    """Create a new supplier. Admin and Warehouse staff only."""
    form = SupplierForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        supplier = form.save()

        log_action(
            user=request.user,
            action_type='OTHER',
            table_affected='materials_supplier',
            record_id=supplier.pk,
            description=f"Created supplier: {supplier.company_name}",
            request=request
        )

        messages.success(request, f"Supplier '{supplier.company_name}' added.")
        return redirect('materials:supplier_list')

    return render(request, 'materials/supplier_form.html', {
        'form': form,
        'form_title': 'Add Supplier',
    })


@login_required
@role_required('Admin', 'Warehouse')
def supplier_edit_view(request, supplier_id):
    """Edit an existing supplier."""
    supplier = get_object_or_404(Supplier, pk=supplier_id)
    form = SupplierForm(request.POST or None, instance=supplier)

    if request.method == 'POST' and form.is_valid():
        form.save()

        log_action(
            user=request.user,
            action_type='OTHER',
            table_affected='materials_supplier',
            record_id=supplier.pk,
            description=f"Edited supplier: {supplier.company_name}",
            request=request
        )

        messages.success(request, f"Supplier '{supplier.company_name}' updated.")
        return redirect('materials:supplier_list')

    return render(request, 'materials/supplier_form.html', {
        'form': form,
        'form_title': f'Edit Supplier: {supplier.company_name}',
        'supplier': supplier,
    })


@login_required
@admin_required
def supplier_toggle_view(request, supplier_id):
    """
    Toggles a supplier between Active / Inactive.
    POST only — prevents accidental toggles from a GET link.
    """
    supplier = get_object_or_404(Supplier, pk=supplier_id)

    if request.method == 'POST':
        if supplier.status == 'Active':
            supplier.status = 'Inactive'
            msg = f"Deactivated supplier: {supplier.company_name}"
        else:
            supplier.status = 'Active'
            msg = f"Activated supplier: {supplier.company_name}"

        supplier.save()

        log_action(
            user=request.user,
            action_type='OTHER',
            table_affected='materials_supplier',
            record_id=supplier.pk,
            description=msg,
            request=request
        )

        messages.success(request, msg)

    return redirect('materials:supplier_list')


@login_required
@admin_required
def supplier_delete_view(request, supplier_id):
    """Delete a supplier if no materials are linked to it."""
    supplier = get_object_or_404(Supplier, pk=supplier_id)
    linked_materials = supplier.materials.count()

    if linked_materials > 0:
        messages.error(
            request,
            f"Cannot delete '{supplier.company_name}' because {linked_materials} material(s) are still linked to it. Reassign or remove those materials first."
        )
        return redirect('materials:supplier_list')

    if request.method == 'POST':
        name = supplier.company_name
        supplier.delete()

        log_action(
            user=request.user,
            action_type='DELETE',
            table_affected='materials_supplier',
            description=f"Deleted supplier: {name}",
            request=request
        )

        messages.success(request, f"Supplier '{name}' deleted.")
        return redirect('materials:supplier_list')

    return render(request, 'materials/confirm_delete.html', {
        'object_name': supplier.company_name,
        'object_type': 'Supplier',
        'cancel_url': reverse('materials:supplier_list'),
        'warning': 'Deleting a supplier is permanent and can only happen if no materials are linked to it.',
    })


# ─────────────────────────────────────────────────────────────
# MATERIAL VIEWS
# ─────────────────────────────────────────────────────────────

@login_required
@role_required('Admin', 'Warehouse', 'Sales', 'Architect', 'Driver')
def material_list_view(request):
    """
    Lists active materials with search and filter support.
    
    Search: by name or SKU
    Filters: by category, by type (Sales Inventory vs External)
    """
    # .select_related() fetches related category and supplier in one SQL query
    # instead of making separate queries for each row (N+1 problem prevention)
    materials = Material.objects.select_related('category', 'supplier').filter(is_active=True)

    # Read filter/search parameters from the URL
    search = request.GET.get('search', '').strip()
    category_filter = request.GET.get('category', '')
    type_filter = request.GET.get('type', '')

    # Q objects allow OR conditions in Django queries
    if search:
        materials = materials.filter(
            Q(name__icontains=search) | Q(sku__icontains=search)
        )
    if category_filter:
        materials = materials.filter(category_id=category_filter)
    if type_filter == 'sales':
        materials = materials.filter(is_sales_inventory=True)
    elif type_filter == 'external':
        materials = materials.filter(is_sales_inventory=False)

    categories = Category.objects.all()

    return render(request, 'materials/material_list.html', {
        'materials': materials,
        'categories': categories,
        'search': search,
        'category_filter': category_filter,
        'type_filter': type_filter,
        'total_count': materials.count(),
    })


@login_required
@role_required('Admin', 'Warehouse')
def material_create_view(request):
    """Add a new material to the catalog. Admin and Warehouse only."""
    form = MaterialForm(request.POST or None, request.FILES or None)

    if request.method == 'POST' and form.is_valid():
        material = form.save()

        log_action(
            user=request.user,
            action_type='OTHER',
            table_affected='materials_material',
            record_id=material.pk,
            description=f"Added material: {material.name} (SKU: {material.sku or 'N/A'})",
            request=request
        )

        messages.success(request, f"Material '{material.name}' added to catalog.")
        return redirect('materials:material_list')

    return render(request, 'materials/material_form.html', {
        'form': form,
        'form_title': 'Add Material',
    })


@login_required
@role_required('Admin', 'Warehouse')
def material_edit_view(request, material_id):
    """Edit an existing material."""
    material = get_object_or_404(Material, pk=material_id)
    form = MaterialForm(request.POST or None, request.FILES or None, instance=material)

    if request.method == 'POST' and form.is_valid():
        form.save()

        log_action(
            user=request.user,
            action_type='OTHER',
            table_affected='materials_material',
            record_id=material.pk,
            description=f"Edited material: {material.name}",
            request=request
        )

        messages.success(request, f"Material '{material.name}' updated.")
        return redirect('materials:material_list')

    return render(request, 'materials/material_form.html', {
        'form': form,
        'form_title': f'Edit: {material.name}',
        'material': material,
    })


@login_required
@admin_required
def material_delete_view(request, material_id):
    """
    Soft-deletes a material by setting is_active=False.
    
    Why soft delete? Because this material may already be referenced in
    past procurement records or orders (in future phases). Hard-deleting
    would break those references or be blocked by database constraints.
    """
    material = get_object_or_404(Material, pk=material_id)

    if request.method == 'POST':
        material.is_active = False
        material.save()

        log_action(
            user=request.user,
            action_type='DELETE',
            table_affected='materials_material',
            record_id=material.pk,
            description=f"Deactivated (soft-deleted) material: {material.name}",
            request=request
        )

        messages.success(request, f"'{material.name}' has been removed from the catalog.")
        return redirect('materials:material_list')

    return render(request, 'materials/confirm_delete.html', {
        'object_name': material.name,
        'object_type': 'Material',
        'cancel_url': reverse('materials:material_list'),
        'warning': 'The material will be hidden from the catalog but historical records are preserved.',
    })