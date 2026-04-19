# delivery/admin.py

from django.contrib import admin
from .models import Delivery, DeliveryStatusLog


class DeliveryStatusLogInline(admin.TabularInline):
    model       = DeliveryStatusLog
    extra       = 0
    readonly_fields = ['old_status', 'new_status', 'changed_by', 'notes', 'changed_at']

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Delivery)
class DeliveryAdmin(admin.ModelAdmin):
    list_display  = [
        'pk', 'delivery_type', 'destination_client',
        'driver_name', 'schedule_date', 'status',
    ]
    list_filter   = ['status', 'delivery_type', 'delivery_team']
    search_fields = ['driver_name', 'end_location', 'dr_number']
    readonly_fields = ['created_at', 'updated_at', 'delivered_at']
    inlines       = [DeliveryStatusLogInline]


@admin.register(DeliveryStatusLog)
class DeliveryStatusLogAdmin(admin.ModelAdmin):
    list_display  = ['delivery', 'old_status', 'new_status', 'changed_by', 'changed_at']
    readonly_fields = ['delivery', 'old_status', 'new_status', 'changed_by', 'changed_at']

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False