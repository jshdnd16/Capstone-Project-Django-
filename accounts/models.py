# accounts/models.py
# This file defines our database models for users and roles.
# We extend Django's built-in AbstractUser so we keep all the
# default auth features (login, password hashing) while adding
# our own fields like role, department, and created_by.

from django.contrib.auth.models import AbstractUser
from django.db import models


class Role(models.Model):
    """
    Defines the different roles in the system.
    Each user is assigned ONE role which controls what they can do.
    
    Roles:
    - Admin: Full access, creates user accounts
    - Sales: Manages orders, clients, deliveries
    - Architect: Manages projects, BOQ, material requests
    - Warehouse: Manages inventory, procurement
    - Driver: Updates delivery status only
    """

    ROLE_CHOICES = [
        ('Admin', 'Admin'),
        ('Sales', 'Sales'),
        ('Architect', 'Architect'),
        ('Warehouse', 'Warehouse'),
        ('Driver', 'Driver'),
    ]

    role_name = models.CharField(
        max_length=50,
        unique=True,
        choices=ROLE_CHOICES,
        help_text="The name of this role"
    )

    # permissions stored as JSON — e.g. {"can_approve_orders": true}
    # This lets us add fine-grained permissions without new columns
    permissions = models.JSONField(
        default=dict,
        blank=True,
        help_text='JSON object of permissions, e.g. {"can_approve_orders": true}'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        # This controls how a Role shows up in the admin panel and dropdowns
        return self.role_name

    class Meta:
        ordering = ['role_name']
        verbose_name = "Role"
        verbose_name_plural = "Roles"


class User(AbstractUser):
    """
    Custom User model that extends Django's built-in AbstractUser.
    
    Why extend AbstractUser?
    - We keep Django's built-in login, password hashing, admin panel
    - We add our own fields: role, department, created_by, status
    
    IMPORTANT: AUTH_USER_MODEL in settings.py points to this model.
    No user can self-register — only Admin creates accounts (per business rules).
    """

    DEPARTMENT_CHOICES = [
        ('Sales', 'Sales'),
        ('Architecture', 'Architecture'),
        ('Warehouse', 'Warehouse'),
        ('Logistics', 'Logistics'),
        ('Management', 'Management'),
    ]

    STATUS_CHOICES = [
        ('Active', 'Active'),
        ('Inactive', 'Inactive'),
    ]

    # Full name — the username field from AbstractUser is the login credential
    fullname = models.CharField(
        max_length=150,
        help_text="Employee's full name"
    )

    # Role: assigned by Admin (Foreign Key → Role model)
    # on_delete=SET_NULL means if the role is deleted, user.role becomes NULL
    role = models.ForeignKey(
        'Role',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users',
        help_text="Role assigned by Admin"
    )

    # Which department does this person work in?
    department = models.CharField(
        max_length=50,
        choices=DEPARTMENT_CHOICES,
        default='Sales'
    )

    # Is this account active or has it been deactivated?
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='Active'
    )

    # Who created this account? (Admin's user_id)
    # self-referencing ForeignKey — points to another User
    created_by = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_users',
        help_text="Admin who created this account"
    )

    def __str__(self):
        return f"{self.fullname} ({self.username})"

    def get_role_name(self):
        """Helper method to safely get role name without errors if role is None"""
        return self.role.role_name if self.role else "No Role"

    def has_permission(self, permission_key):
        """
        Check if this user has a specific permission.
        
        Usage: user.has_permission('can_approve_orders')
        Returns True/False
        """
        if not self.role:
            return False
        return self.role.permissions.get(permission_key, False)

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"


class TransactionLog(models.Model):
    """
    Audit log — records every important action in the system.
    
    This satisfies the panelist comment about security (Obj 6.5).
    Every time someone logs in, creates an order, adjusts inventory,
    etc., a log entry is created automatically.
    
    Examples of what gets logged:
    - "Sales Juan created order #105 for Buildrite Hardware"
    - "Warehouse Maria adjusted Buildrite Waterproofing stock: -5 bags"
    - "Admin Carlo created new user account: juan_dela_cruz"
    """

    ACTION_CHOICES = [
        ('LOGIN', 'User Login'),
        ('LOGOUT', 'User Logout'),
        ('CREATE_USER', 'Created User Account'),
        ('CREATE_ORDER', 'Created Sales Order'),
        ('UPDATE_ORDER', 'Updated Sales Order'),
        ('CREATE_MATERIAL_REQUEST', 'Created Material Request'),
        ('UPDATE_INVENTORY', 'Updated Inventory'),
        ('CREATE_PROCUREMENT', 'Created Procurement Order'),
        ('UPDATE_DELIVERY', 'Updated Delivery Status'),
        ('CREATE_PROJECT', 'Created Project'),
        ('APPROVE', 'Approved Record'),
        ('DELETE', 'Deleted Record'),
        ('OTHER', 'Other Action'),
    ]

    # Who performed this action?
    user = models.ForeignKey(
        'User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='transaction_logs'
    )

    # What type of action was it?
    action_type = models.CharField(max_length=50, choices=ACTION_CHOICES)

    # Which database table was affected?
    table_affected = models.CharField(
        max_length=100,
        blank=True,
        help_text="e.g. orders, inventory, material_requests"
    )

    # Which specific record was affected? (the ID of that row)
    record_id = models.IntegerField(
        null=True,
        blank=True,
        help_text="e.g. order_id=105"
    )

    # Human-readable description of what happened
    description = models.TextField(
        blank=True,
        help_text='e.g. "Sales Juan created order for Buildrite Hardware"'
    )

    # IP address — for tracking where logins came from (security)
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="IP address of the user at time of action"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"[{self.created_at:%Y-%m-%d %H:%M}] {self.action_type} by {self.user}"

    class Meta:
        ordering = ['-created_at']   # Most recent logs first
        verbose_name = "Transaction Log"
        verbose_name_plural = "Transaction Logs"