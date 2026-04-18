# architecture/urls.py

from django.urls import path
from . import views

app_name = 'architecture'

urlpatterns = [

    # ── Project URLs ───────────────────────────────────────────
    path('projects/',
         views.project_list_view,          name='project_list'),

    path('projects/create/',
         views.project_create_view,        name='project_create'),

    path('projects/<int:project_id>/',
         views.project_detail_view,        name='project_detail'),

    path('projects/<int:project_id>/edit/',
         views.project_edit_view,          name='project_edit'),

    path('projects/<int:project_id>/status/',
         views.project_update_status_view, name='project_status'),

    # ── BOQ URLs ───────────────────────────────────────────────
    # Create a new BOQ version for a project
    path('projects/<int:project_id>/boq/create/',
         views.boq_create_view,   name='boq_create'),

    # View a specific BOQ version
    path('boq/<int:boq_id>/',
         views.boq_detail_view,   name='boq_detail'),

    # Mark a BOQ as final/approved
    path('boq/<int:boq_id>/finalise/',
         views.boq_finalise_view, name='boq_finalise'),

    # ── Material Request URLs ──────────────────────────────────
    path('requests/',
         views.material_request_list_view,   name='material_request_list'),

    # Create from a specific project's detail page
    path('projects/<int:project_id>/requests/create/',
         views.material_request_create_view, name='material_request_create_for_project'),

    # Standalone create (project selected via dropdown)
    path('requests/create/',
         views.material_request_create_view, name='material_request_create'),

    path('requests/<int:request_id>/',
         views.material_request_detail_view, name='material_request_detail'),

    path('requests/<int:request_id>/approve/',
         views.material_request_approve_view, name='material_request_approve'),

    path('requests/<int:request_id>/reject/',
         views.material_request_reject_view,  name='material_request_reject'),
]