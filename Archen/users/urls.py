# PATH: /Archen/users/urls.py
from django.urls import path
from .views import (
    logout_view,
    user_list_view,
    users_export_xlsx,
    user_create_view,
    user_edit_view,
    user_toggle_active_view,
    user_bulk_delete_view,
    user_stats_view,
)

app_name = 'users'

urlpatterns = [
    # Logout handled here (accepts POST and GET; redirects to 'login')
    path('logout/', logout_view, name='logout'),

    path('list/', user_list_view, name='user_list'),
    path('list/export/xlsx/', users_export_xlsx, name='export_xlsx'),
    path('add/', user_create_view, name='user_add'),
    path('edit/<int:pk>/', user_edit_view, name='user_edit'),
    path('toggle/<int:pk>/', user_toggle_active_view, name='user_toggle'),
    path('bulk_delete/', user_bulk_delete_view, name='bulk_delete'),
    # Lightweight JSON stats endpoint for live counters
    path('stats/', user_stats_view, name='user_stats'),
]
