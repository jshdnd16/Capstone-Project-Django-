# inventory/urls.py
# URL patterns for the inventory app.
# All routes are mounted under /inventory/ in the root urls.py.

from django.urls import path
from . import views

app_name = 'inventory'

urlpatterns = [

    # ── Overview & Detail ──────────────────────────────────────
    # /inventory/             → Current stock levels for all materials
    path('',
         views.stock_overview_view,
         name='stock_overview'),

    # /inventory/history/     → Full transaction log (all movements)
    path('history/',
         views.transaction_history_view,
         name='transaction_history'),

    # /inventory/<id>/detail/ → Stock card for one specific material
    path('<int:material_id>/detail/',
         views.material_stock_detail_view,
         name='material_detail'),

    # ── Stock Actions ──────────────────────────────────────────
    # /inventory/stock-in/    → Add incoming stock
    path('stock-in/',
         views.stock_in_view,
         name='stock_in'),

    # /inventory/stock-out/   → Deduct outgoing stock
    path('stock-out/',
         views.stock_out_view,
         name='stock_out'),

    # /inventory/adjustment/  → Manual correction after physical count
    path('adjustment/',
         views.stock_adjustment_view,
         name='adjustment'),
]