# procurement/admin.py

from django.contrib import admin
from .models import ProcurementOrder, ProcurementItem


class ProcurementItemInline(admin.TabularInline):
    model   = ProcurementItem
    extra   = 0
    readonly_fields = ['subtotal']


@admin.register(ProcurementOrder)
class ProcurementOrderAdmin(admin.ModelAdmin):
    list_display  = [
        'pk', 'supplier', 'ordered_by', 'status',
        'total_amount', 'order_date', 'expected_delivery_date',
    ]
    list_filter   = ['status', 'supplier', 'order_method']
    search_fields = ['supplier__company_name', 'dr_number']
    readonly_fields = [
        'order_date', 'created_at', 'updated_at',
        'stock_received', 'total_amount',
    ]
    inlines       = [ProcurementItemInline]


@admin.register(ProcurementItem)
class ProcurementItemAdmin(admin.ModelAdmin):
    list_display  = ['order', 'material', 'ordered_qty', 'received_qty', 'unit_cost', 'subtotal']
    readonly_fields = ['subtotal']