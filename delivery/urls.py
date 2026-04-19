# delivery/urls.py

from django.urls import path
from . import views

app_name = 'delivery'

urlpatterns = [

    # ── List & Detail ───────────────────────────────────────────
    # /delivery/              → All deliveries (filtered by role)
    path('',
         views.delivery_list_view,   name='delivery_list'),

    # /delivery/<id>/         → Full delivery detail
    path('<int:delivery_id>/',
         views.delivery_detail_view, name='delivery_detail'),

    # ── Scheduling ─────────────────────────────────────────────
    # /delivery/schedule/     → Create / schedule a new delivery
    path('schedule/',
         views.delivery_create_view, name='delivery_create'),

    # /delivery/<id>/edit/    → Edit scheduling details
    path('<int:delivery_id>/edit/',
         views.delivery_edit_view,   name='delivery_edit'),

    # ── Status Updates ─────────────────────────────────────────
    # /delivery/<id>/status/  → Advance status (POST)
    path('<int:delivery_id>/status/',
         views.delivery_update_status_view, name='delivery_status'),

    # /delivery/<id>/complete/ → Mark as Received + DR form
    path('<int:delivery_id>/complete/',
         views.delivery_complete_view, name='delivery_complete'),

    # ── Driver Dashboard ────────────────────────────────────────
    # /delivery/driver/       → Driver's today-focused dashboard
    path('driver/',
         views.driver_dashboard_view, name='driver_dashboard'),
]