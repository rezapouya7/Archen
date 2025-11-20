# PATH: /Archen/maintenance/urls.py
# Archen/Archen/maintenance/urls.py
"""
URL configuration for the maintenance app.  Exposes endpoints for
maintenance actions such as purging logs, zeroing inventory,
rebuilding stocks, and downloading/restoring backups.
"""

from django.urls import path
from . import views

app_name = 'maintenance'

urlpatterns = [
    # Main maintenance page (manager only)
    path('', views.maintenance_view, name='maintenance'),
    # Perform an action (POST only)
    path('action/', views.maintenance_action, name='maintenance_action'),
    # Backup download endpoint
    path('backup/', views.maintenance_backup, name='maintenance_backup'),
    # Restore upload endpoint
    path('restore/', views.maintenance_restore, name='maintenance_restore'),

    # --- Per‑app backup/restore endpoints ---
    # Inventory
    path('backup/inventory/', views.backup_inventory, name='backup_inventory'),
    path('restore/inventory/', views.restore_inventory, name='restore_inventory'),
    # Accounting
    path('backup/accounting/', views.backup_accounting, name='backup_accounting'),
    path('restore/accounting/', views.restore_accounting, name='restore_accounting'),
    # Production line
    path('backup/production/', views.backup_production, name='backup_production'),
    path('restore/production/', views.restore_production, name='restore_production'),
    # Jobs
    path('backup/jobs/', views.backup_jobs, name='backup_jobs'),
    path('restore/jobs/', views.restore_jobs, name='restore_jobs'),
    # Orders
    path('backup/orders/', views.backup_orders, name='backup_orders'),
    path('restore/orders/', views.restore_orders, name='restore_orders'),
    # Users
    path('backup/users/', views.backup_users, name='backup_users'),
    path('restore/users/', views.restore_users, name='restore_users'),
]
