# PATH: /Archen/reports/admin.py
from django.contrib import admin

from .models import Report


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    """
    Admin interface for Report model. Shows report title, creation timestamp
    and attached file in list display and allows search by title.
    """
    list_display = ('title', 'created_at', 'file')
    search_fields = ('title',)
