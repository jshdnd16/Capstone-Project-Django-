# inventory/utils.py
# The core business logic for applying stock transactions.
#
# All three transaction types (IN, OUT, ADJUSTMENT) go through
# apply_transaction() — this is the single source of truth for
# how stock changes. Views call this function; they never update
# Inventory.quantity directly.
#
# Using a single function:
# - Prevents bugs from duplicated logic
# - Ensures the audit trail (InventoryTransaction) is ALWAYS written
# - Makes it easy to add validation in one place

from django.db import transaction as db_transaction
from .models import Inventory, InventoryTransaction


def get_or_create_inventory(material):
    """
    Retrieves the Inventory row for a material, or creates one
    with quantity=0 if it doesn't exist yet.
    
    This handles the case where a material was added to the catalog
    but no stock has been recorded yet.
    """
    inv, _ = Inventory.objects.get_or_create(
        material=material,
        defaults={'quantity': 0}
    )
    return inv


@db_transaction.atomic
def apply_stock_in(material, quantity, user, reference_type='MANUAL',
                   reference_id=None, remarks=''):
    """
    Adds stock to inventory and creates an audit transaction.
    
    @db_transaction.atomic means: if anything fails mid-way,
    ALL database changes are rolled back. Either both the
    Inventory update AND the Transaction record succeed, or neither does.
    This prevents phantom stock entries or mismatched balances.
    
    Returns the updated Inventory object.
    """
    inv = get_or_create_inventory(material)

    quantity_before = inv.quantity
    inv.quantity    += quantity        # Add to current stock
    inv.save()
    quantity_after  = inv.quantity

    # Create the permanent audit trail entry
    InventoryTransaction.objects.create(
        material         = material,
        user             = user,
        transaction_type = 'IN',
        quantity         = quantity,
        quantity_before  = quantity_before,
        quantity_after   = quantity_after,
        reference_type   = reference_type,
        reference_id     = reference_id,
        remarks          = remarks,
    )

    return inv


@db_transaction.atomic
def apply_stock_out(material, quantity, user, reference_type='MANUAL',
                    reference_id=None, remarks=''):
    """
    Deducts stock from inventory and creates an audit transaction.
    Raises ValueError if there isn't enough stock (safety check).
    """
    inv = get_or_create_inventory(material)

    if inv.quantity < quantity:
        raise ValueError(
            f"Insufficient stock for {material.name}. "
            f"Available: {inv.quantity}, Requested: {quantity}"
        )

    quantity_before = inv.quantity
    inv.quantity   -= quantity         # Deduct from current stock
    inv.save()
    quantity_after  = inv.quantity

    InventoryTransaction.objects.create(
        material         = material,
        user             = user,
        transaction_type = 'OUT',
        quantity         = quantity,
        quantity_before  = quantity_before,
        quantity_after   = quantity_after,
        reference_type   = reference_type,
        reference_id     = reference_id,
        remarks          = remarks,
    )

    return inv


@db_transaction.atomic
def apply_adjustment(material, new_quantity, user, reason='', remarks=''):
    """
    Sets stock to a specific quantity (from a physical recount)
    and records the adjustment with a before/after snapshot.
    
    The 'quantity' stored in the transaction is the absolute change (delta),
    which can be positive (stock was MORE than recorded) or negative (LESS).
    """
    inv = get_or_create_inventory(material)

    quantity_before = inv.quantity
    delta           = new_quantity - quantity_before    # How much changed
    inv.quantity    = new_quantity
    inv.save()
    quantity_after  = inv.quantity

    full_remarks = f"Reason: {reason}. {remarks}".strip('. ')

    InventoryTransaction.objects.create(
        material         = material,
        user             = user,
        transaction_type = 'ADJUSTMENT',
        # Store the absolute change for the transaction record
        quantity         = abs(delta) if delta != 0 else 0,
        quantity_before  = quantity_before,
        quantity_after   = quantity_after,
        reference_type   = 'ADJUSTMENT',
        remarks          = full_remarks,
    )

    return inv, delta