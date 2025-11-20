"""
Admin configuration for the jobs app.

Registers the ``ProductionJob`` model so that administrators can
manage jobs via the Django admin interface.  The model itself is
defined in ``jobs.models``.
"""

from django.contrib import admin
from .models import ProductionJob


@admin.register(ProductionJob)
class ProductionJobAdmin(admin.ModelAdmin):
    """Simple admin for production jobs."""
    list_display = ("job_number", "status", "job_label", "product", "part", "created_at", "finished_at")
    search_fields = ("job_number", "product__name", "part__name")
    list_filter = ("status", "job_label")