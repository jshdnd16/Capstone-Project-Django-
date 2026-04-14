# materials/admin.py
# Registers our three models with Django's built-in /admin/ panel.

from django.contrib import admin
from .models import Category, Supplier, Material


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display  = ['category_name', 'description', 'created_at']
    search_fields = ['category_name']


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display  = ['company_name', 'contact_person', 'phone', 'supplier_type', 'status', 'is_primary']
    list_filter   = ['supplier_type', 'status', 'is_primary']
    search_fields = ['company_name', 'contact_person']


@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display  = ['name', 'sku', 'category', 'supplier', 'unit',
                     'current_cost', 'selling_price', 'is_sales_inventory', 'is_active']
    list_filter   = ['category', 'supplier', 'is_sales_inventory', 'is_active']
    search_fields = ['name', 'sku']
    readonly_fields = ['created_at', 'updated_at']