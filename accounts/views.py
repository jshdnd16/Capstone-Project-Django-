# accounts/views.py
# Views handle HTTP requests and return HTTP responses.
# Each function (or class) here corresponds to one page/action.

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_POST

from .models import User, Role, TransactionLog
from .forms import LoginForm, UserCreateForm, UserEditForm
from .utils import log_action
from .decorators import admin_required   # We'll create this below


# ─────────────────────────────────────────────────────────────
# AUTHENTICATION VIEWS
# ─────────────────────────────────────────────────────────────

def login_view(request):
    """
    Displays the login form and handles login submissions.
    
    GET  → Show the login form
    POST → Validate credentials, log the user in, redirect to dashboard
    """

    # If user is already logged in, send them to the dashboard
    if request.user.is_authenticated:
        return redirect('core:dashboard')

    form = LoginForm(request.POST or None)

    if request.method == 'POST':
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']

            # authenticate() checks the username/password against the database
            user = authenticate(request, username=username, password=password)

            if user is not None:
                # Check if the account is active
                if user.status == 'Inactive':
                    messages.error(request, "Your account has been deactivated. Contact the Admin.")
                    return render(request, 'accounts/login.html', {'form': form})

                # Log the user into the session
                login(request, user)

                # Record this login in the audit log
                log_action(
                    user=user,
                    action_type='LOGIN',
                    description=f"{user.fullname} logged in",
                    request=request
                )

                messages.success(request, f"Welcome back, {user.fullname}!")
                return redirect('core:dashboard')
            else:
                messages.error(request, "Invalid username or password.")

    return render(request, 'accounts/login.html', {'form': form})


def logout_view(request):
    """
    Logs the user out and redirects to the login page.
    Only accepts POST requests (security best practice — 
    GET logout can be triggered by a malicious link).
    """

    if request.user.is_authenticated:
        log_action(
            user=request.user,
            action_type='LOGOUT',
            description=f"{request.user.fullname} logged out",
            request=request
        )

    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect('accounts:login')


# ─────────────────────────────────────────────────────────────
# USER MANAGEMENT VIEWS (Admin only)
# ─────────────────────────────────────────────────────────────

@login_required
@admin_required
def user_list_view(request):
    """
    Shows a list of all user accounts.
    Only accessible by Admin users.
    """

    users = User.objects.select_related('role').order_by('fullname')

    # Allow filtering by department and status via URL query params
    # e.g. /accounts/users/?department=Sales&status=Active
    department_filter = request.GET.get('department', '')
    status_filter = request.GET.get('status', '')

    if department_filter:
        users = users.filter(department=department_filter)
    if status_filter:
        users = users.filter(status=status_filter)

    context = {
        'users': users,
        'department_filter': department_filter,
        'status_filter': status_filter,
        'departments': User.DEPARTMENT_CHOICES,
    }
    return render(request, 'accounts/user_list.html', context)


@login_required
@admin_required
def user_create_view(request):
    """
    Shows the form to create a new user account.
    Only Admin can create accounts (no self-registration).
    
    GET  → Show empty form
    POST → Validate and save new user
    """

    form = UserCreateForm(request.POST or None)

    if request.method == 'POST':
        if form.is_valid():
            # Save the form but don't commit to DB yet
            user = form.save(commit=False)

            # Record who created this account
            user.created_by = request.user

            # Hash the password properly using Django's built-in method
            user.set_password(form.cleaned_data['password1'])
            user.save()

            # Log this action
            log_action(
                user=request.user,
                action_type='CREATE_USER',
                table_affected='accounts_user',
                record_id=user.pk,
                description=f"Admin {request.user.fullname} created account for {user.fullname} ({user.username})",
                request=request
            )

            messages.success(request, f"Account for {user.fullname} created successfully.")
            return redirect('accounts:user_list')

    return render(request, 'accounts/user_form.html', {
        'form': form,
        'form_title': 'Create New User Account'
    })


@login_required
@admin_required
def user_edit_view(request, user_id):
    """
    Allows Admin to edit an existing user account.
    Password can be changed separately via a different form.
    """

    # get_object_or_404 returns 404 error if the user doesn't exist
    target_user = get_object_or_404(User, pk=user_id)
    form = UserEditForm(request.POST or None, instance=target_user)

    if request.method == 'POST':
        if form.is_valid():
            form.save()

            log_action(
                user=request.user,
                action_type='OTHER',
                table_affected='accounts_user',
                record_id=target_user.pk,
                description=f"Admin {request.user.fullname} edited account for {target_user.fullname}",
                request=request
            )

            messages.success(request, f"Account for {target_user.fullname} updated.")
            return redirect('accounts:user_list')

    return render(request, 'accounts/user_form.html', {
        'form': form,
        'form_title': f'Edit User: {target_user.fullname}',
        'target_user': target_user,
    })


@login_required
@admin_required
def user_toggle_status_view(request, user_id):
    """
    Toggles a user account between Active and Inactive.
    This is the "soft delete" — we never hard delete user accounts
    because they may be linked to orders, logs, etc.
    """

    target_user = get_object_or_404(User, pk=user_id)

    # Prevent Admin from deactivating their own account
    if target_user == request.user:
        messages.error(request, "You cannot deactivate your own account.")
        return redirect('accounts:user_list')

    # Toggle the status
    if target_user.status == 'Active':
        target_user.status = 'Inactive'
        action_msg = f"Deactivated account for {target_user.fullname}"
    else:
        target_user.status = 'Active'
        action_msg = f"Activated account for {target_user.fullname}"

    target_user.save()

    log_action(
        user=request.user,
        action_type='OTHER',
        table_affected='accounts_user',
        record_id=target_user.pk,
        description=action_msg,
        request=request
    )

    messages.success(request, action_msg)
    return redirect('accounts:user_list')


@login_required
@admin_required
def audit_log_view(request):
    """
    Shows the full audit/transaction log.
    Useful for tracking who did what and when.
    Admin only.
    """

    logs = TransactionLog.objects.select_related('user').order_by('-created_at')[:200]
    # Limit to last 200 entries for performance

    return render(request, 'accounts/audit_log.html', {'logs': logs})