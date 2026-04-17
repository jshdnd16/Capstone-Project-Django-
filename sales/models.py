# sales/models.py
# Three models manage the entire customer sales flow:
#
# Client    → The customer (hardware store, walk-in, contractor).
#             A client can have many orders over time.
#
# Order     → A single sales transaction. One order per visit/call.
#             Links to a client and the Sales personnel who made it.
#             Tracks status (workflow) and payment status.
#
# OrderItem → A line item inside an order: which material, how many,
#             at what price. An order can have many items.
#             We snapshot the price at the time of sale — this is
#             critical because material prices may change later.
#
# Stock deduction:
#   When an Order moves to status 'Preparing', we automatically
#   call apply_stock_out() for each item. This is done in the
#   view (not here) to keep models thin.

from django.core.validators import MinValueValidator
from django.db import models
from django.conf import settings
from materials.models import Material


class Client(models.Model):
    """
    Represents a customer of Mitra's Sales department.

    Types:
    - Hardware Store  : Recurring business (Buildrite Hardware Tiaong, etc.)
    - Walk-in         : One-time or occasional cash buyers
    - Contractor      : Independent builders who buy in bulk
    """

    CLIENT_TYPE_CHOICES = [
        ('Hardware Store', 'Hardware Store'),
        ('Walk-in',        'Walk-in Customer'),
        ('Contractor',     'Contractor'),
    ]

    DELIVERY_ZONE_CHOICES = [
        ('North Quezon',   'North Quezon'),
        ('Central Quezon', 'Central Quezon'),
        ('South Quezon',   'South Quezon'),
        ('Lucena City',    'Lucena City'),
        ('Pick-up',        'Pick-up / No Delivery'),
    ]

    client_name    = models.CharField(max_length=200)
    contact_person = models.CharField(max_length=150, blank=True)
    phone          = models.CharField(max_length=20)
    address        = models.TextField(blank=True)
    client_type    = models.CharField(
        max_length=20,
        choices=CLIENT_TYPE_CHOICES,
        default='Hardware Store'
    )
    delivery_zone  = models.CharField(
        max_length=30,
        choices=DELIVERY_ZONE_CHOICES,
        default='Pick-up',
        help_text="Used for delivery routing in Phase 6"
    )
    notes = models.TextField(
        blank=True,
        help_text="Any special instructions, credit terms, or preferences"
    )
    is_active  = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.client_name

    @property
    def total_orders(self):
        """Total number of orders this client has placed."""
        return self.orders.count()

    @property
    def total_revenue(self):
        """
        Lifetime revenue from this client.
        Only counts Completed orders to reflect actual fulfilled sales.
        """
        from django.db.models import Sum
        result = self.orders.filter(
            status='Completed'
        ).aggregate(total=Sum('total_amount'))
        return result['total'] or 0

    class Meta:
        ordering   = ['client_name']
        verbose_name = 'Client'
        verbose_name_plural = 'Clients'


class Order(models.Model):
    """
    A single sales transaction — the "header" record for a sale.

    Status workflow (moves forward only, never backward except Cancel):
      Pending → Confirmed → Preparing → Out for Delivery → Completed
                                ↓
                            (stock deducted here)

    payment_status is tracked separately from order status because
    a Completed delivery may still have an outstanding balance.
    """

    STATUS_CHOICES = [
        ('Pending',           'Pending'),
        ('Confirmed',         'Confirmed'),
        ('Preparing',         'Preparing'),
        ('Out for Delivery',  'Out for Delivery'),
        ('Completed',         'Completed'),
        ('Cancelled',         'Cancelled'),
    ]

    # Valid transitions — what status can follow what
    # Used by the view to prevent illegal jumps
    STATUS_TRANSITIONS = {
        'Pending':          ['Confirmed', 'Cancelled'],
        'Confirmed':        ['Preparing', 'Cancelled'],
        'Preparing':        ['Out for Delivery', 'Cancelled'],
        'Out for Delivery': ['Completed'],
        'Completed':        [],
        'Cancelled':        [],
    }

    PAYMENT_STATUS_CHOICES = [
        ('Unpaid',   'Unpaid'),
        ('Partial',  'Partial'),
        ('Paid',     'Paid'),
    ]

    ORDER_TYPE_CHOICES = [
        ('Regular',  'Regular'),
        ('Preorder', 'Pre-order'),
        ('Bulk',     'Bulk Order'),
    ]

    client = models.ForeignKey(
        Client,
        on_delete=models.PROTECT,   # Can't delete a client who has orders
        related_name='orders'
    )
    # The Sales personnel who created this order
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_orders'
    )

    order_date     = models.DateTimeField(auto_now_add=True)
    total_amount   = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text="Sum of all order item subtotals. Recalculated on save."
    )
    status         = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='Pending'
    )
    payment_status = models.CharField(
        max_length=10,
        choices=PAYMENT_STATUS_CHOICES,
        default='Unpaid'
    )
    order_type     = models.CharField(
        max_length=10,
        choices=ORDER_TYPE_CHOICES,
        default='Regular'
    )

    # Was stock already deducted for this order?
    # Prevents double-deduction if the status is changed multiple times.
    stock_deducted = models.BooleanField(
        default=False,
        help_text="True once inventory has been deducted for this order."
    )

    notes = models.TextField(blank=True, help_text="Special instructions or delivery notes")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Order #{self.pk} — {self.client.client_name} ({self.status})"

    def recalculate_total(self):
        """
        Recomputes total_amount from the sum of all OrderItem subtotals.
        Call this after adding/editing/deleting order items.
        """
        from django.db.models import Sum
        result = self.items.aggregate(total=Sum('subtotal'))
        self.total_amount = result['total'] or 0
        self.save(update_fields=['total_amount'])

    def get_next_statuses(self):
        """
        Returns the list of valid next statuses for this order's current status.
        Used in the template to build the status-change button options.
        """
        return self.STATUS_TRANSITIONS.get(self.status, [])

    def can_edit_items(self):
        """
        Items can only be edited while the order is still Pending.
        Once Confirmed, the order is locked.
        """
        return self.status == 'Pending'

    class Meta:
        ordering   = ['-order_date']
        verbose_name = 'Order'
        verbose_name_plural = 'Orders'


class OrderItem(models.Model):
    """
    A single line item inside an Order.

    price_at_sale is a SNAPSHOT of the selling price at the time of the order.
    This is crucial — if a material's price changes later, historical orders
    must still reflect what the customer was actually charged.
    """

    order    = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,   # Deleting an order removes its items
        related_name='items'
    )
    material = models.ForeignKey(
        Material,
        on_delete=models.PROTECT,   # Can't delete a material that appears on orders
        related_name='order_items'
    )

    quantity     = models.IntegerField(
        validators=[MinValueValidator(1)],
        help_text="Must be at least 1"
    )
    # Snapshot: the price charged to the client for this specific order
    price_at_sale = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Selling price at the time of this order — preserved for history"
    )
    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="quantity × price_at_sale — calculated automatically"
    )

    def save(self, *args, **kwargs):
        """
        Always recalculate subtotal before saving.
        This prevents subtotal from ever going out of sync.
        """
        self.subtotal = self.quantity * self.price_at_sale
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.quantity}× {self.material.name} @ ₱{self.price_at_sale}"

    class Meta:
        verbose_name = 'Order Item'
        verbose_name_plural = 'Order Items'