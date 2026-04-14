# mitra_project/urls.py
# The ROOT URL configuration for the entire project.
# All URL patterns from all apps are collected here.
# Think of this as the "main switchboard" for routing.

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect

urlpatterns = [
    # Redirect the root URL to the dashboard
    path('', lambda request: redirect('core:dashboard'), name='root'),

    # Django admin panel (built-in)
    path('admin/', admin.site.urls),

    # Accounts app (login, logout, user management)
    path('accounts/', include('accounts.urls', namespace='accounts')),

    # Core app (dashboard, home page)
    path('', include('core.urls', namespace='core')),

    # Materials app (Phase 2) ← ADD THIS LINE
    path('materials/', include('materials.urls', namespace='materials')),
]

# Serve media files during development
# In production, your web server (Nginx/Apache) handles this
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])