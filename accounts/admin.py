# accounts/admin.py
# This registers our models with Django's built-in admin panel.
# Customizing ModelAdmin lets us control how data looks in /admin/.

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import Role, User, TransactionLog


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    """Admin configuration for Role model."""

    # Columns shown in the list view at /admin/accounts/role/
    list_display = ['role_name', 'created_at']
    search_fields = ['role_name']


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """
    Admin configuration for our custom User model.
    We extend BaseUserAdmin to keep Django's built-in
    password management while adding our custom fields.
    """

    # Columns shown in the user list
    list_display = ['username', 'fullname', 'role', 'department', 'status', 'date_joined']

    # Filters on the right sidebar
    list_filter = ['role', 'department', 'status']

    # Fields you can search
    search_fields = ['username', 'fullname', 'email']

    # Add our custom fields to the user detail/edit form
    # fieldsets controls what groups of fields appear on the edit page
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Mitra Information', {
            'fields': ('fullname', 'role', 'department', 'status', 'created_by')
        }),
    )

    # Fields shown when CREATING a new user (the add form)
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Mitra Information', {
            'fields': ('fullname', 'email', 'role', 'department')
        }),
    )


@admin.register(TransactionLog)
class TransactionLogAdmin(admin.ModelAdmin):
    """Admin configuration for the audit log. Read-only — logs should not be edited."""

    list_display = ['created_at', 'user', 'action_type', 'table_affected', 'record_id', 'ip_address']
    list_filter = ['action_type', 'table_affected']
    search_fields = ['user__username', 'description']
    readonly_fields = ['user', 'action_type', 'table_affected', 'record_id',
                       'description', 'ip_address', 'created_at']

    # Prevent anyone from adding or deleting logs through admin
    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False