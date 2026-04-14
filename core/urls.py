# core/urls.py
# URL patterns for the core app (dashboard and shared pages).

from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    # Main dashboard — all users land here
    path('dashboard/', views.dashboard_view, name='dashboard'),
]