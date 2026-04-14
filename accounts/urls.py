# accounts/urls.py
# URL patterns for the accounts app.
# Each URL pattern maps a URL to a view function.
#
# These will be included in the main mitra_project/urls.py
# under the prefix /accounts/

from django.urls import path
from . import views

# app_name creates a namespace so we can use 'accounts:login' in templates
# instead of just 'login' — avoids conflicts with other apps
app_name = 'accounts'

urlpatterns = [
    # Authentication URLs
    path('login/',  views.login_view,  name='login'),   # /accounts/login/
    path('logout/', views.logout_view, name='logout'),  # /accounts/logout/

    # User management URLs (Admin only)
    path('users/',                        views.user_list_view,          name='user_list'),
    path('users/create/',                 views.user_create_view,        name='user_create'),
    path('users/<int:user_id>/edit/',     views.user_edit_view,          name='user_edit'),
    path('users/<int:user_id>/toggle/',   views.user_toggle_status_view, name='user_toggle'),

    # Audit log (Admin only)
    path('audit-log/', views.audit_log_view, name='audit_log'),
]