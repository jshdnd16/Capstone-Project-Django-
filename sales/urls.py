# sales/urls.py
# URL patterns for the sales app.
# All routes are mounted under /sales/ in the root urls.py.

from django.urls import path
from . import views

app_name = 'sales'

urlpatterns = [

    # ── Client URLs ────────────────────────────────────────────
    path('clients/',
         views.client_list_view,   name='client_list'),

    path('clients/create/',
         views.client_create_view, name='client_create'),

    path('clients/<int:client_id>/edit/',
         views.client_edit_view,   name='client_edit'),

    path('clients/<int:client_id>/toggle/',
         views.client_toggle_view, name='client_toggle'),

    # ── Order URLs ─────────────────────────────────────────────
    # /sales/orders/          → Order list
    path('orders/',
         views.order_list_view,    name='order_list'),

    # /sales/orders/create/   → New order form
    path('orders/create/',
         views.order_create_view,  name='order_create'),

    # /sales/orders/<id>/     → Order detail page
    path('orders/<int:order_id>/',
         views.order_detail_view,  name='order_detail'),

    # /sales/orders/<id>/edit-items/  → Edit line items (Pending only)
    path('orders/<int:order_id>/edit-items/',
         views.order_edit_items_view, name='order_edit_items'),

    # /sales/orders/<id>/status/  → Advance order status (POST)
    path('orders/<int:order_id>/status/',
         views.order_update_status_view, name='order_update_status'),

    # /sales/orders/<id>/payment/  → Update payment status (POST)
    path('orders/<int:order_id>/payment/',
         views.order_update_payment_view, name='order_update_payment'),

    # /sales/orders/<id>/notes/  → Update notes (POST)
    path('orders/<int:order_id>/notes/',
         views.order_update_notes_view, name='order_update_notes'),

    # /sales/orders/<id>/cancel/  → Cancel order (POST)
    path('orders/<int:order_id>/cancel/',
         views.order_cancel_view, name='order_cancel'),
]