# sales/admin.py

from django.contrib import admin
from .models import Client, Order, OrderItem


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display  = ['client_name', 'client_type', 'phone', 'delivery_zone', 'is_active']
    list_filter   = ['client_type', 'delivery_zone', 'is_active']
    search_fields = ['client_name', 'contact_person', 'phone']


class OrderItemInline(admin.TabularInline):
    """Shows order items directly inside the Order admin page."""
    model      = OrderItem
    extra      = 0
    readonly_fields = ['subtotal']


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display  = [
        'pk', 'client', 'created_by', 'order_date',
        'total_amount', 'status', 'payment_status',
    ]
    list_filter   = ['status', 'payment_status', 'order_type']
    search_fields = ['client__client_name', 'pk']
    inlines       = [OrderItemInline]
    readonly_fields = ['order_date', 'created_at', 'updated_at', 'stock_deducted']


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display  = ['order', 'material', 'quantity', 'price_at_sale', 'subtotal']
    readonly_fields = ['subtotal']