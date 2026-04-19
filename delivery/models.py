# delivery/models.py
# One model handles all deliveries — both Sales Orders and
# Architecture Material Requests — through a unified design.
#
# Delivery       → The "trip" record. One truck trip = one Delivery.
#                  Links to EITHER an Order or a MaterialRequest,
#                  never both at the same time.
#
# DeliveryStatusLog → An append-only history of every status change.
#                     Gives a full timeline of "who moved it to what
#                     status, at what time" for every delivery.
#
# Design decisions:
# - order_id and request_id are both nullable; exactly one should be set.
#   The view enforces this rule.
# - Status is text-based (not GPS) per the project scope limitations.
# - Delay flags are stored as separate booleans so we can filter
#   "how many deliveries were delayed by weather this month?" later.

from django.db import models
from django.conf import settings


class Delivery(models.Model):
    """
    Represents a physical delivery trip.

    delivery_type controls which source document it's linked to:
    - 'Sales Order'        → links to sales.Order via order
    - 'Architecture Request' → links to architecture.MaterialRequest via request

    Status workflow:
        Scheduled → Out for Delivery → Arrived → Received
                                                 (Delivery complete)
        Any status can move to → Cancelled (if trip is aborted)

    Delay flags are Boolean so they can be counted in reports:
    - weather_delay       : Rain prevented safe delivery
    - driver_unavailable  : Assigned driver couldn't make the trip
    - closed_store_delay  : Hardware store was closed on arrival
    """

    DELIVERY_TYPE_CHOICES = [
        ('Sales Order',          'Sales Order'),
        ('Architecture Request', 'Architecture Request'),
    ]

    STATUS_CHOICES = [
        ('Scheduled',        'Scheduled'),
        ('Out for Delivery', 'Out for Delivery'),
        ('Arrived',          'Arrived'),
        ('Received',         'Received'),
        ('Cancelled',        'Cancelled'),
    ]

    # Valid status transitions — the view checks this before saving
    STATUS_TRANSITIONS = {
        'Scheduled':        ['Out for Delivery', 'Cancelled'],
        'Out for Delivery': ['Arrived', 'Cancelled'],
        'Arrived':          ['Received', 'Cancelled'],
        'Received':         [],
        'Cancelled':        [],
    }

    DELIVERY_TEAM_CHOICES = [
        ('Mitra',         'Mitra (own team)'),
        ('Manufacturer',  'Manufacturer / Supplier delivery'),
        ('Third-party',   'Third-party courier'),
    ]

    # ── Source document link ──────────────────────────────
    # Exactly ONE of these should be set; the other stays NULL.
    delivery_type = models.CharField(
        max_length=25,
        choices=DELIVERY_TYPE_CHOICES,
        default='Sales Order',
    )
    order = models.ForeignKey(
        'sales.Order',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='deliveries',
        help_text="Set if delivering a Sales Order"
    )
    request = models.ForeignKey(
        'architecture.MaterialRequest',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='deliveries',
        help_text="Set if delivering an Architecture Material Request"
    )

    # ── People & Vehicle ──────────────────────────────────
    driver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='deliveries_as_driver',
        help_text="Mitra driver assigned to this trip"
    )
    driver_name = models.CharField(
        max_length=150,
        help_text="Name of driver (stored as text so history is preserved "
                  "even if the user account is later changed)"
    )
    delivery_team = models.CharField(
        max_length=20,
        choices=DELIVERY_TEAM_CHOICES,
        default='Mitra'
    )
    vehicle_plate = models.CharField(
        max_length=20,
        blank=True,
        help_text="Truck or vehicle plate number"
    )

    # ── Scheduling ────────────────────────────────────────
    schedule_date  = models.DateField(
        help_text="Planned delivery date"
    )
    start_location = models.CharField(
        max_length=200,
        default='Mitra Planners and Builders — Main Warehouse',
        help_text="Origin address (hub or warehouse)"
    )
    end_location = models.CharField(
        max_length=200,
        help_text="Delivery destination (hardware store or project site)"
    )
    route_notes = models.TextField(
        blank=True,
        help_text="Directions, landmarks, or routing instructions"
    )

    # ── Delay Tracking ────────────────────────────────────
    # Stored as separate flags so we can aggregate by delay type later
    weather_delay          = models.BooleanField(
        default=False,
        help_text="True if rain or weather prevented / delayed delivery"
    )
    driver_unavailable_delay = models.BooleanField(
        default=False,
        help_text="True if the assigned driver was unavailable"
    )
    closed_store_delay     = models.BooleanField(
        default=False,
        help_text="True if the destination was closed on arrival"
    )
    delay_remarks = models.TextField(
        blank=True,
        help_text="Free-text explanation of any delays"
    )

    # ── Completion ────────────────────────────────────────
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='Scheduled'
    )
    delivered_at = models.DateTimeField(
        null=True, blank=True,
        help_text="Timestamp when status moved to Received"
    )
    received_by = models.CharField(
        max_length=150,
        blank=True,
        help_text="Name of person who signed / received the delivery"
    )
    dr_number = models.CharField(
        max_length=50,
        blank=True,
        help_text="Delivery Receipt number issued upon completion"
    )
    notes = models.TextField(
        blank=True,
        help_text="Any additional delivery notes"
    )

    # ── Timestamps ────────────────────────────────────────
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='deliveries_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        source = f"Order #{self.order_id}" if self.order_id else f"MR#{self.request_id}"
        return f"Delivery #{self.pk} — {source} ({self.status})"

    def get_next_statuses(self):
        """Returns valid next statuses for the current status."""
        return self.STATUS_TRANSITIONS.get(self.status, [])

    @property
    def source_label(self):
        """Human-readable source document reference."""
        if self.order_id:
            return f"Sales Order #{self.order_id} — {self.order.client.client_name}"
        if self.request_id:
            return f"Material Request #{self.request_id} — {self.request.project.project_name}"
        return "—"

    @property
    def destination_client(self):
        """Returns the client/project name for display."""
        if self.order:
            return self.order.client.client_name
        if self.request:
            return self.request.project.client_name
        return "—"

    @property
    def is_delayed(self):
        """True if any delay flag is set."""
        return self.weather_delay or self.driver_unavailable_delay or self.closed_store_delay

    @property
    def is_complete(self):
        return self.status == 'Received'

    @property
    def is_active(self):
        return self.status in ('Scheduled', 'Out for Delivery', 'Arrived')

    class Meta:
        ordering = ['-schedule_date', '-created_at']
        verbose_name = 'Delivery'
        verbose_name_plural = 'Deliveries'


class DeliveryStatusLog(models.Model):
    """
    An append-only audit trail of every status change on a delivery.
    Never edited or deleted — only created.

    Lets us answer: "What time did this delivery leave the warehouse?"
    or "Who marked it as Received?"
    """

    delivery   = models.ForeignKey(
        Delivery,
        on_delete=models.CASCADE,
        related_name='status_logs'
    )
    old_status = models.CharField(max_length=20, blank=True)
    new_status = models.CharField(max_length=20)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='delivery_status_changes'
    )
    notes      = models.TextField(blank=True)
    changed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return (
            f"Delivery #{self.delivery_id}: "
            f"{self.old_status} → {self.new_status} "
            f"at {self.changed_at:%Y-%m-%d %H:%M}"
        )

    class Meta:
        ordering = ['changed_at']
        verbose_name = 'Delivery Status Log'
        verbose_name_plural = 'Delivery Status Logs'