# inventory/models.py
# Two models power the entire inventory system:
#
# Inventory             → ONE row per material. Tracks the CURRENT stock level.
#                         Think of it as the "balance" row in a ledger.
#
# InventoryTransaction  → ONE row per stock movement (in, out, adjustment).
#                         The full history of everything that changed stock.
#                         Think of it as the individual "debit/credit" lines.
#
# Every time stock changes, we:
#   1. Create an InventoryTransaction record (the trail)
#   2. Update the matching Inventory.quantity (the balance)

from django.db import models
from django.conf import settings
from materials.models import Material


class Inventory(models.Model):
    """
    Stores the CURRENT quantity on hand for each material.
    
    There is exactly ONE Inventory row per material (enforced by unique=True on material).
    When stock changes, this row is updated. The full history lives in InventoryTransaction.
    
    warehouse_location examples:
    - "Main Warehouse"      (Mitra's primary stock room)
    - "Sales Counter"       (items held at the sales desk)
    - "Project Site"        (items pulled for architecture projects)
    """

    material = models.OneToOneField(
        Material,
        on_delete=models.CASCADE,   # If a material is hard-deleted, its inventory row goes too
        related_name='inventory'
    )
    quantity = models.IntegerField(
        default=0,
        help_text="Current quantity on hand. Updated automatically on each transaction."
    )
    warehouse_location = models.CharField(
        max_length=100,
        default='Main Warehouse',
        blank=True
    )
    last_updated = models.DateTimeField(auto_now=True)  # Auto-stamps every save

    def __str__(self):
        return f"{self.material.name} — {self.quantity} {self.material.unit}"

    @property
    def is_low_stock(self):
        """
        Returns True if current quantity is at or below the material's reorder level.
        Used to highlight low-stock items in the UI with a warning badge.
        """
        return self.quantity <= self.material.reorder_level

    @property
    def is_out_of_stock(self):
        """Returns True if there is literally zero stock."""
        return self.quantity <= 0

    @property
    def stock_value(self):
        """
        The total cost value of stock on hand.
        Formula: quantity × current_cost
        Used for inventory valuation reports.
        """
        return self.quantity * self.material.current_cost

    class Meta:
        ordering = ['material__name']
        verbose_name = 'Inventory'
        verbose_name_plural = 'Inventory'


class InventoryTransaction(models.Model):
    """
    A permanent, append-only record of every stock movement.
    
    Transaction types:
    - IN          : Stock received (from procurement, returns, initial stock)
    - OUT         : Stock issued (for a sales order or architecture project)
    - ADJUSTMENT  : Manual correction (recount found a discrepancy, spoilage, etc.)
    - TRANSFER    : Move stock between locations
    
    reference_type / reference_id:
    These link the transaction to its source document.
    In Phase 3 we use 'MANUAL'. Future phases will link to orders/procurement.
    
    Example:
      type=IN, reference_type=PROCUREMENT, reference_id=12
      → "Received 50 bags from Procurement Order #12"
    """

    TRANSACTION_TYPE_CHOICES = [
        ('IN',         'Stock In'),
        ('OUT',        'Stock Out'),
        ('ADJUSTMENT', 'Adjustment'),
        ('TRANSFER',   'Transfer'),
    ]

    REFERENCE_TYPE_CHOICES = [
        ('MANUAL',        'Manual Entry'),
        ('SALES_ORDER',   'Sales Order'),
        ('ARCH_REQUEST',  'Architecture Request'),
        ('PROCUREMENT',   'Procurement Order'),
        ('ADJUSTMENT',    'Stock Adjustment'),
        ('INITIAL',       'Initial Stock'),
        ('RETURN',        'Return / Reversal'),
    ]

    material = models.ForeignKey(
        Material,
        on_delete=models.PROTECT,   # Never delete a material that has transactions
        related_name='transactions'
    )

    # Who performed this transaction?
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='inventory_transactions'
    )

    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPE_CHOICES)

    # A positive number always. The sign is determined by transaction_type.
    # IN = +quantity, OUT = -quantity, ADJUSTMENT can be ±
    quantity = models.IntegerField(
        help_text="Always positive. The direction is determined by transaction_type."
    )

    # What was the stock level AFTER this transaction?
    # We snapshot this so we can reconstruct history even if inventory changes later.
    quantity_before = models.IntegerField(
        help_text="Stock quantity before this transaction was applied."
    )
    quantity_after = models.IntegerField(
        help_text="Stock quantity after this transaction was applied."
    )

    # Link to the source document (order, procurement, etc.)
    reference_type = models.CharField(
        max_length=30,
        choices=REFERENCE_TYPE_CHOICES,
        default='MANUAL'
    )
    reference_id = models.IntegerField(
        null=True,
        blank=True,
        help_text="The PK of the related document (order_id, procurement_id, etc.)"
    )

    # Human-readable note about why this transaction happened
    remarks = models.TextField(
        blank=True,
        help_text='e.g., "Received from Magna Prime DR#1234", "Issued for Project Lucena Renovation"'
    )

    transaction_date = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp is set automatically when the transaction is saved."
    )

    def __str__(self):
        direction = "+" if self.transaction_type == 'IN' else "-"
        return (
            f"[{self.transaction_date:%Y-%m-%d}] "
            f"{self.transaction_type} {direction}{self.quantity} "
            f"{self.material.unit} of {self.material.name}"
        )

    class Meta:
        ordering = ['-transaction_date']    # Most recent first
        verbose_name = 'Inventory Transaction'
        verbose_name_plural = 'Inventory Transactions'