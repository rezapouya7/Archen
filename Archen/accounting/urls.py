# PATH: /Archen/accounting/urls.py
from django.urls import path
from . import views

app_name = 'accounting'

urlpatterns = [
    # Landing page for accounting dashboard
    path('', views.dashboard, name='dashboard'),
    path('update-record/', views.update_finance_record, name='update_record'),
    path('bulk-delete/', views.bulk_delete_records, name='bulk_delete'),
]
