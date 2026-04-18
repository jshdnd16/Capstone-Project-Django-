# architecture/models.py
# Four models power the Architecture module:
#
# Project           → The construction or design job.
#                     One project may have multiple BOQ versions and
#                     multiple material requests over its lifetime.
#
# BOQHeader         → The "cover page" of a Bill of Quantities.
#                     Versioned — each revision gets a new BOQHeader row
#                     so we never overwrite the previous approved version.
#
# BOQItem           → A single line in the BOQ: which material, how many,
#                     at what estimated cost, from which source.
#
# MaterialRequest   → A formal request from the Architect to pull materials
#                     from the Sales warehouse (or source externally).
#                     Triggers a stock deduction when fulfilled.
#
# MaterialRequestItem → A single material line inside a MaterialRequest.
#                       Tracks both required_qty and fulfilled_qty separately
#                       so partial fulfillments are handled correctly.

from django.db import models
from django.conf import settings
from materials.models import Material, Supplier


class Project(models.Model):
    """
    Represents a construction or design-and-build project.

    Projects are created by Architects and may span months.
    Each project can have multiple BOQ revisions (for scope changes)
    and multiple material requests (for phased delivery).

    status flow:
        Planning → Ongoing → On Hold → Completed
    """

    STATUS_CHOICES = [
        ('Planning',   'Planning'),
        ('Ongoing',    'Ongoing'),
        ('On Hold',    'On Hold'),
        ('Completed',  'Completed'),
        ('Cancelled',  'Cancelled'),
    ]

    project_name = models.CharField(
        max_length=200,
        help_text="Short descriptive name, e.g., 'Lucena Residential Renovation'"
    )
    client_name = models.CharField(
        max_length=200,
        help_text="Name of the project owner or client"
    )
    location = models.TextField(
        help_text="Full project site address within Quezon Province"
    )

    # The Architect assigned to this project
    architect = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='projects',
        help_text="Architect responsible for this project"
    )

    start_date = models.DateField(null=True, blank=True)
    end_date   = models.DateField(null=True, blank=True)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='Planning'
    )
    budget = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Estimated total project budget in PHP"
    )
    description = models.TextField(
        blank=True,
        help_text="Project scope, special notes, or instructions"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.project_name} ({self.client_name})"

    @property
    def active_boq(self):
        """
        Returns the most recent FINAL (approved) BOQ for this project.
        Falls back to the latest draft if no final BOQ exists yet.
        Used in templates to show the current BOQ at a glance.
        """
        final = self.boqs.filter(is_final=True).order_by('-version').first()
        if final:
            return final
        return self.boqs.order_by('-version').first()

    @property
    def total_boq_estimate(self):
        """Total cost from the active BOQ, or 0 if no BOQ exists."""
        boq = self.active_boq
        return boq.total_estimate if boq else 0

    @property
    def pending_requests(self):
        """Count of material requests still awaiting approval."""
        return self.material_requests.filter(status='Pending').count()

    class Meta:
        ordering   = ['-created_at']
        verbose_name = 'Project'
        verbose_name_plural = 'Projects'


class BOQHeader(models.Model):
    """
    The header row of a Bill of Quantities.

    Each time an Architect revises the BOQ, a NEW BOQHeader is created
    with an incremented version number. The old BOQ is never deleted —
    this gives a complete audit trail of scope changes.

    is_final = True  → This version has been approved and is in use.
    is_final = False → Draft, still being edited.

    Only one BOQ should be marked is_final=True per project at a time.
    The view enforces this by unfinalising previous versions when a new
    one is finalised.
    """

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='boqs'
    )
    version = models.IntegerField(
        default=1,
        help_text="Incremented each time a revised BOQ is created"
    )
    total_estimate = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
        help_text="Sum of all BOQ item totals. Recalculated on save."
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='boqs_created'
    )
    is_final = models.BooleanField(
        default=False,
        help_text="Mark True when this BOQ version is approved and in use"
    )
    notes = models.TextField(
        blank=True,
        help_text="Revision notes — what changed from the previous version"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        status = "FINAL" if self.is_final else "Draft"
        return f"BOQ v{self.version} — {self.project.project_name} [{status}]"

    def recalculate_total(self):
        """
        Recomputes total_estimate from all BOQItem subtotals.
        Call this after adding/editing/deleting BOQ items.
        """
        from django.db.models import Sum
        result = self.items.aggregate(total=Sum('total_cost'))
        self.total_estimate = result['total'] or 0
        self.save(update_fields=['total_estimate'])

    class Meta:
        ordering   = ['-version']
        verbose_name = 'BOQ'
        verbose_name_plural = 'BOQs'
        # Enforce unique version numbers per project
        unique_together = [('project', 'version')]


class BOQItem(models.Model):
    """
    A single line item inside a Bill of Quantities.

    source_type controls where this material will come from:
    - Sales Inventory : Pull from Mitra's warehouse (Buildrite/Sinclair)
    - External        : Order from an outside supplier (architecture-specific)

    unit_cost is recorded at BOQ creation time — like price_at_sale in orders,
    this preserves the estimate even if material prices change later.
    """

    SOURCE_CHOICES = [
        ('Sales Inventory', 'Sales Inventory (Mitra Warehouse)'),
        ('External',        'External Supplier'),
    ]

    boq      = models.ForeignKey(BOQHeader, on_delete=models.CASCADE, related_name='items')
    material = models.ForeignKey(
        Material,
        on_delete=models.PROTECT,
        related_name='boq_items'
    )

    required_qty = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Estimated quantity needed for this project"
    )
    unit_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Estimated cost per unit at time of BOQ creation"
    )
    total_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="required_qty × unit_cost — calculated automatically"
    )

    source_type = models.CharField(
        max_length=20,
        choices=SOURCE_CHOICES,
        default='Sales Inventory'
    )
    # If sourced externally, which supplier?
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='boq_items',
        help_text="External supplier (only if source_type = External)"
    )
    notes = models.CharField(max_length=200, blank=True)

    def save(self, *args, **kwargs):
        """Auto-calculate total_cost before every save."""
        self.total_cost = self.required_qty * self.unit_cost
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.material.name} × {self.required_qty} [{self.source_type}]"

    class Meta:
        verbose_name = 'BOQ Item'
        verbose_name_plural = 'BOQ Items'


class MaterialRequest(models.Model):
    """
    A formal request from the Architecture department to pull materials
    from the Sales Inventory warehouse (or order from external suppliers).

    Status flow:
        Pending → Approved → Partially Fulfilled → Fulfilled
                ↓
            Rejected

    When status moves to 'Approved', the view deducts stock from
    inventory for items sourced from Sales Inventory.
    External items bypass inventory and are tracked separately.
    """

    STATUS_CHOICES = [
        ('Pending',              'Pending'),
        ('Approved',             'Approved'),
        ('Partially Fulfilled',  'Partially Fulfilled'),
        ('Fulfilled',            'Fulfilled'),
        ('Rejected',             'Rejected'),
    ]

    FULFILLMENT_SOURCE_CHOICES = [
        ('Sales Inventory', 'Sales Inventory'),
        ('External',        'External Supplier'),
        ('Mixed',           'Mixed Sources'),
    ]

    project = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        related_name='material_requests'
    )
    architect = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='material_requests',
        help_text="Architect who submitted this request"
    )

    request_date   = models.DateTimeField(auto_now_add=True)
    total_amount   = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text="Sum of all item subtotals. Recalculated on save."
    )
    status = models.CharField(
        max_length=25,
        choices=STATUS_CHOICES,
        default='Pending'
    )
    fulfillment_source = models.CharField(
        max_length=20,
        choices=FULFILLMENT_SOURCE_CHOICES,
        default='Sales Inventory'
    )

    # Has stock been deducted for this request?
    # Prevents double-deduction on re-approval.
    stock_deducted = models.BooleanField(default=False)

    notes = models.TextField(blank=True)
    # Admin notes when approving or rejecting
    admin_notes = models.TextField(
        blank=True,
        help_text="Notes from Admin when approving or rejecting"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"MR#{self.pk} — {self.project.project_name} ({self.status})"

    def recalculate_total(self):
        """Recompute total from all request item subtotals."""
        from django.db.models import Sum
        result = self.request_items.aggregate(total=Sum('subtotal'))
        self.total_amount = result['total'] or 0
        self.save(update_fields=['total_amount'])

    class Meta:
        ordering   = ['-request_date']
        verbose_name = 'Material Request'
        verbose_name_plural = 'Material Requests'


class MaterialRequestItem(models.Model):
    """
    A single material line inside a MaterialRequest.

    fulfilled_qty tracks how much was actually issued.
    For partial fulfillments: fulfilled_qty < required_qty.
    For full fulfillments: fulfilled_qty == required_qty.
    """

    SOURCE_CHOICES = [
        ('Sales Inventory', 'Sales Inventory'),
        ('External',        'External Supplier'),
    ]

    request  = models.ForeignKey(
        MaterialRequest,
        on_delete=models.CASCADE,
        related_name='request_items'
    )
    material = models.ForeignKey(
        Material,
        on_delete=models.PROTECT,
        related_name='material_request_items'
    )

    required_qty  = models.DecimalField(max_digits=10, decimal_places=2)
    fulfilled_qty = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="How much was actually issued from the warehouse"
    )
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal  = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="required_qty × unit_cost — calculated automatically"
    )

    source_type = models.CharField(
        max_length=20,
        choices=SOURCE_CHOICES,
        default='Sales Inventory'
    )
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='material_request_items'
    )

    def save(self, *args, **kwargs):
        """Auto-calculate subtotal before every save."""
        self.subtotal = self.required_qty * self.unit_cost
        super().save(*args, **kwargs)

    @property
    def is_fully_fulfilled(self):
        return self.fulfilled_qty >= self.required_qty

    @property
    def remaining_qty(self):
        return max(0, self.required_qty - self.fulfilled_qty)

    def __str__(self):
        return f"{self.material.name} × {self.required_qty} (fulfilled: {self.fulfilled_qty})"

    class Meta:
        verbose_name = 'Material Request Item'
        verbose_name_plural = 'Material Request Items'