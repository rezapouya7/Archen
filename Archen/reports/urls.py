# PATH: /Archen/reports/urls.py

from django.urls import path
from . import views

app_name = 'reports'

urlpatterns = [
    path('jobs/', views.jobs, name='jobs'),
    path('jobs/<str:job_number>/', views.job_detail, name='job_detail'),
    path('', views.index, name='list'),
    # Live metrics API for auto-refreshing reports dashboard
    path('api/metrics/', views.metrics_api, name='metrics_api'),
    path('scrap/', views.scrap_report, name='scrap'),
    # Job details panel (AJAX) and export endpoints for dashboard
    path('job-details/', views.job_details_panel, name='job_details_panel'),
    path('job-details/<str:job_number>/export/<str:fmt>/', views.job_details_export, name='job_details_export'),
    # Order details panel (AJAX) for dashboard
    path('order-details/', views.order_details_panel, name='order_details_panel'),
    path('order-details/<int:order_id>/export/<str:fmt>/', views.order_details_export, name='order_details_export'),
    # Log details panel (AJAX) and export
    path('log-details/', views.log_details_panel, name='log_details_panel'),
    path('log-details/<int:log_id>/export/<str:fmt>/', views.log_details_export, name='log_details_export'),
    # Logs list export (xlsx/pdf) with client-provided filters
    path('logs/export/<str:fmt>/', views.logs_list_export, name='logs_list_export'),
]
