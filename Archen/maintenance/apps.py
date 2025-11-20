# PATH: /Archen/maintenance/apps.py
# Archen/Archen/maintenance/apps.py
"""
Configuration for the maintenance app.  This app encapsulates
destructive administrative actions such as purging logs and
rebuilding inventory.  It is intentionally separated from the
production_line app to avoid accidental invocation by workers.
"""

from django.apps import AppConfig


class MaintenanceConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'maintenance'