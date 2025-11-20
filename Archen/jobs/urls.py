"""URL configuration for the jobs app.

These routes expose list, create, edit and bulk delete endpoints for
managing production jobs.  The empty path ('') maps to the job list so
that ``/jobs/`` lists all jobs by default.  Namespacing is used to
prevent conflicts with other apps.
"""

from django.urls import path
from . import views


app_name = 'jobs'

urlpatterns = [
    path('', views.job_list_view, name='job_list'),
    path('add/', views.job_add_view, name='job_add'),
    path('edit/<int:pk>/', views.job_edit_view, name='job_edit'),
    path('bulk_delete/', views.job_bulk_delete_view, name='job_bulk_delete'),
    path('export/list/xlsx/', views.jobs_list_export_xlsx, name='export_xlsx'),
]
