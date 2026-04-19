# procurement/models.py
# Two models power the Procurement module:
#
# ProcurementOrder  → The "purchase order" header. One PO per supplier
#                     per ordering event. Tracks status, expected delivery,
#                     and total cost.
#
# ProcurementItem   → One line per material inside the PO. Records both
#                     ordered_qty (what we asked for) and received_qty
#                     (what actually arrived). These can differ if a
#                     supplier partially fulfils an order.
#
# When a ProcurementOrder moves to 'Received', the view calls
# apply_stock_in() for each item using received_qty, not ordered_qty.
# This correctly handles short deliveries.
#
# The stock_received flag prevents double-counting if someone
# accidentally clicks "Receive" twice.

from django.db import models
from django.conf import settings
from materials.models import Material, Supplier


class ProcurementOrder(models.Model):
    """
    A purchase order sent to a supplier — usually Magna Prime.

    Status workflow:
        Draft → Submitted → Confirmed → Shipped → Received
          ↓ (can cancel from any non-terminal state)
        Cancelled

    - Draft      : Being prepared, not yet sent to supplier
    - Submitted  : Order has been emailed / called in to supplier
    - Confirmed  : Supplier confirmed the order and delivery date
    - Shipped    : Goods are in transit
    - Received   : Goods arrived; stock has been updated
    - Cancelled  : Order was cancelled before receipt

    order_method tracks HOW the PO was sent (email, phone, website)
    because Magna Prime accepts orders through different channels.
    """

    STATUS_CHOICES = [
        ('Draft',      'Draft'),
        ('Submitted',  'Submitted'),
        ('Confirmed',  'Confirmed'),
        ('Shipped',    'Shipped'),
        ('Received',   'Received'),
        ('Cancelled',  'Cancelled'),
    ]

    # Which statuses can follow which
    STATUS_TRANSITIONS = {
        'Draft':     ['Submitted', 'Cancelled'],
        'Submitted': ['Confirmed', 'Cancelled'],
        'Confirmed': ['Shipped',   'Cancelled'],
        'Shipped':   ['Received',  'Cancelled'],
        'Received':  [],
        'Cancelled': [],
    }

    ORDER_METHOD_CHOICES = [
        ('Email',   'Email'),
        ('Phone',   'Phone Call'),
        ('Website', 'Supplier Website'),
        ('In-person', 'In-person / Walk-in'),
    ]

    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.PROTECT,
        related_name='procurement_orders',
        help_text="Supplier this order is placed with (usually Magna Prime)"
    )
    ordered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='procurement_orders',
        help_text="Warehouse staff who created this PO"
    )

    # Key dates
    order_date             = models.DateTimeField(auto_now_add=True)
    expected_delivery_date = models.DateField(
        null=True, blank=True,
        help_text="Date supplier is expected to deliver (usually 5–7 days)"
    )
    actual_delivery_date   = models.DateField(
        null=True, blank=True,
        help_text="Date goods actually arrived at the warehouse"
    )

    total_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
        help_text="Sum of all item subtotals. Recalculated automatically."
    )
    status       = models.CharField(
        max_length=15,
        choices=STATUS_CHOICES,
        default='Draft'
    )
    order_method = models.CharField(
        max_length=15,
        choices=ORDER_METHOD_CHOICES,
        default='Email'
    )

    # DR number assigned when goods arrive
    dr_number = models.CharField(
        max_length=50, blank=True,
        help_text="Delivery Receipt number from the supplier"
    )

    # Prevents double stock-in if "Receive" is clicked more than once
    stock_received = models.BooleanField(
        default=False,
        help_text="True once inventory has been updated for this PO"
    )

    notes = models.TextField(blank=True)

    # Admin / supervisor who confirmed or approved this PO
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='approved_procurements',
        help_text="Admin who confirmed / approved this PO"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"PO#{self.pk} — {self.supplier.company_name} ({self.status})"

    def get_next_statuses(self):
        """Returns the list of valid next statuses."""
        return self.STATUS_TRANSITIONS.get(self.status, [])

    def recalculate_total(self):
        """
        Recomputes total_amount from all item subtotals.
        Always call this after adding/editing/deleting items.
        """
        from django.db.models import Sum
        result = self.items.aggregate(total=Sum('subtotal'))
        self.total_amount = result['total'] or 0
        self.save(update_fields=['total_amount'])

    @property
    def is_editable(self):
        """
        Items and details can only be changed while the PO is still a Draft.
        Once Submitted, it is locked — you'd need to cancel and re-create.
        """
        return self.status == 'Draft'

    @property
    def total_items(self):
        return self.items.count()

    @property
    def is_overdue(self):
        """
        True if the expected delivery date has passed and goods
        haven't arrived yet. Used to highlight overdue POs.
        """
        from django.utils import timezone
        if self.expected_delivery_date and self.status not in ('Received', 'Cancelled'):
            return self.expected_delivery_date < timezone.localdate()
        return False

    class Meta:
        ordering   = ['-order_date']
        verbose_name = 'Procurement Order'
        verbose_name_plural = 'Procurement Orders'


class ProcurementItem(models.Model):
    """
    A single line in a procurement order.

    ordered_qty  : How many units we asked the supplier for.
    received_qty : How many units actually arrived (set when PO is received).
                   Defaults to ordered_qty — updated if short-delivered.

    subtotal is based on ordered_qty × unit_cost, not received_qty.
    This preserves the original purchase commitment even if fewer arrived.
    The inventory update (apply_stock_in) uses received_qty.
    """

    order    = models.ForeignKey(
        ProcurementOrder,
        on_delete=models.CASCADE,
        related_name='items'
    )
    material = models.ForeignKey(
        Material,
        on_delete=models.PROTECT,
        related_name='procurement_items'
    )

    ordered_qty  = models.IntegerField(
        help_text="Quantity ordered from supplier"
    )
    received_qty = models.IntegerField(
        default=0,
        help_text="Quantity actually received — filled in when marking PO as Received"
    )
    unit_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Cost per unit from the supplier — snapshot at time of ordering"
    )
    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="ordered_qty × unit_cost — calculated automatically"
    )

    def save(self, *args, **kwargs):
        """Auto-calculate subtotal on every save."""
        self.subtotal = self.ordered_qty * self.unit_cost
        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.material.name} × {self.ordered_qty} "
            f"(received: {self.received_qty})"
        )

    @property
    def is_short_delivered(self):
        """True if fewer units arrived than were ordered."""
        return self.received_qty < self.ordered_qty

    @property
    def shortage(self):
        """How many units are still outstanding."""
        return max(0, self.ordered_qty - self.received_qty)

    class Meta:
        verbose_name = 'Procurement Item'
        verbose_name_plural = 'Procurement Items'