# materials/urls.py
# URL patterns for the materials app.
# These are included in the main urls.py under the /materials/ prefix.

from django.urls import path
from . import views

app_name = 'materials'

urlpatterns = [

    # ── Category URLs ──────────────────────────────────
    path('categories/',                          views.category_list_view,   name='category_list'),
    path('categories/create/',                   views.category_create_view, name='category_create'),
    path('categories/<int:category_id>/edit/',   views.category_edit_view,   name='category_edit'),
    path('categories/<int:category_id>/delete/', views.category_delete_view, name='category_delete'),

    # ── Supplier URLs ──────────────────────────────────
    path('suppliers/',                           views.supplier_list_view,   name='supplier_list'),
    path('suppliers/create/',                    views.supplier_create_view, name='supplier_create'),
    path('suppliers/<int:supplier_id>/edit/',    views.supplier_edit_view,   name='supplier_edit'),
    path('suppliers/<int:supplier_id>/toggle/',  views.supplier_toggle_view, name='supplier_toggle'),

    # ── Material URLs ──────────────────────────────────
    # The empty path '' maps to /materials/ → material list
    path('',                                     views.material_list_view,   name='material_list'),
    path('create/',                              views.material_create_view, name='material_create'),
    path('<int:material_id>/edit/',              views.material_edit_view,   name='material_edit'),
    path('<int:material_id>/delete/',            views.material_delete_view, name='material_delete'),
]