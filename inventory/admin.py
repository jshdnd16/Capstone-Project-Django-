# inventory/admin.py

from django.contrib import admin
from .models import Inventory, InventoryTransaction


@admin.register(Inventory)
class InventoryAdmin(admin.ModelAdmin):
    list_display  = ['material', 'quantity', 'warehouse_location', 'last_updated']
    list_filter   = ['warehouse_location']
    search_fields = ['material__name', 'material__sku']
    readonly_fields = ['last_updated']


@admin.register(InventoryTransaction)
class InventoryTransactionAdmin(admin.ModelAdmin):
    list_display  = [
        'transaction_date', 'material', 'transaction_type',
        'quantity', 'quantity_before', 'quantity_after', 'user'
    ]
    list_filter   = ['transaction_type', 'reference_type']
    search_fields = ['material__name', 'remarks']
    readonly_fields = [
        'material', 'user', 'transaction_type', 'quantity',
        'quantity_before', 'quantity_after', 'reference_type',
        'reference_id', 'remarks', 'transaction_date'
    ]

    # Nobody should be able to add or delete transactions through the admin —
    # they are permanent audit records
    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False