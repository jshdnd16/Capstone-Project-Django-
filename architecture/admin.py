# architecture/admin.py

from django.contrib import admin
from .models import Project, BOQHeader, BOQItem, MaterialRequest, MaterialRequestItem


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display  = ['project_name', 'client_name', 'architect', 'status', 'created_at']
    list_filter   = ['status']
    search_fields = ['project_name', 'client_name']


class BOQItemInline(admin.TabularInline):
    model   = BOQItem
    extra   = 0
    readonly_fields = ['total_cost']


@admin.register(BOQHeader)
class BOQHeaderAdmin(admin.ModelAdmin):
    list_display  = ['project', 'version', 'total_estimate', 'is_final', 'created_by', 'created_at']
    list_filter   = ['is_final']
    inlines       = [BOQItemInline]
    readonly_fields = ['total_estimate', 'created_at']


class MaterialRequestItemInline(admin.TabularInline):
    model   = MaterialRequestItem
    extra   = 0
    readonly_fields = ['subtotal']


@admin.register(MaterialRequest)
class MaterialRequestAdmin(admin.ModelAdmin):
    list_display  = ['pk', 'project', 'architect', 'status', 'total_amount', 'request_date']
    list_filter   = ['status']
    inlines       = [MaterialRequestItemInline]
    readonly_fields = ['total_amount', 'stock_deducted', 'request_date']