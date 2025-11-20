# PATH: /Archen/inventory/urls.py
from django.urls import path
from . import views

app_name = 'inventory'

urlpatterns = [

    path('products/', views.products_list, name='products_list'),
    path('products/add/', views.products_add, name='products_add'),
    path('products/<int:pk>/edit/', views.products_edit, name='products_edit'),
    path('products/<int:pk>/delete/', views.products_delete, name='products_delete'),
    path('products/bulk-delete/', views.products_bulk_delete, name='products_bulk_delete'),
    # Inline/bulk updates for product stage stocks
    path('products/inline_update/', views.products_inline_update, name='products_inline_update'),
    path('products/bulk_update/', views.products_bulk_update, name='products_bulk_update'),

    # Model management
    path('models/', views.models_list_view, name='models_list'),
    path('models/add/', views.model_create_view, name='model_create'),
    path('models/<int:pk>/edit/', views.model_edit_view, name='model_edit'),
    path('models/<int:pk>/delete/', views.model_delete_view, name='model_delete'),
    path('models/bulk-delete/', views.model_bulk_delete_view, name='model_bulk_delete'),

    # Dashboard
    path('', views.inventory_dashboard, name='dashboard'),

    # Parts
    path('parts/', views.parts_list_view, name='parts_list'),
    path('parts/add/', views.parts_create_view, name='parts_add'),
    path('parts/edit/<int:pk>/', views.parts_edit_view, name='parts_edit'),
    path('parts/bulk_delete/', views.parts_bulk_delete_view, name='parts_bulk_delete'),
    # Inline/bulk updates for parts stocks
    path('parts/inline_update/', views.parts_inline_update, name='parts_inline_update'),
    path('parts/bulk_update/', views.parts_bulk_update, name='parts_bulk_update'),

    # Materials
    path('materials/', views.materials_list, name='materials_list'),
    path('materials/add/', views.materials_add, name='materials_add'),
    path('materials/edit/<int:pk>/', views.materials_edit, name='materials_edit'),
    path(
        'materials/bulk_delete/',
        views.materials_bulk_delete,
        name='materials_bulk_delete'
    ),
]
