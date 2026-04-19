# procurement/urls.py

from django.urls import path
from . import views

app_name = 'procurement'

urlpatterns = [

    # ── Dashboard ──────────────────────────────────────────────
    # /procurement/              → Procurement dashboard
    path('',
         views.procurement_dashboard_view, name='procurement_dashboard'),

    # ── List & Detail ──────────────────────────────────────────
    # /procurement/orders/       → All procurement orders
    path('orders/',
         views.procurement_list_view,   name='procurement_list'),

    # /procurement/orders/<id>/  → Full PO detail
    path('orders/<int:po_id>/',
         views.procurement_detail_view, name='procurement_detail'),

    # ── Create & Edit ──────────────────────────────────────────
    # /procurement/orders/create/
    path('orders/create/',
         views.procurement_create_view, name='procurement_create'),

    # /procurement/orders/<id>/edit/
    path('orders/<int:po_id>/edit/',
         views.procurement_edit_view,   name='procurement_edit'),

    # ── Status & Receiving ─────────────────────────────────────
    # /procurement/orders/<id>/status/  → Advance status (POST)
    path('orders/<int:po_id>/status/',
         views.procurement_update_status_view, name='procurement_status'),

    # /procurement/orders/<id>/receive/ → Record actual receipt + stock-in
    path('orders/<int:po_id>/receive/',
         views.procurement_receive_view, name='procurement_receive'),
]