# PATH: /Archen/orders/urls.py
from django.urls import path
from . import views

app_name = "orders"

urlpatterns = [
    path("", views.OrderListView.as_view(), name="list"),
    path("create/", views.OrderCreateView.as_view(), name="create"),
    path("edit/<int:pk>/", views.OrderUpdateView.as_view(), name="edit"),
    path("bulk-delete/", views.OrderBulkDeleteView.as_view(), name="bulk_delete"),
    path("export/list/xlsx/", views.orders_list_export_xlsx, name="export_xlsx"),
    # AJAX endpoint to fetch products by selected product model names.
    path("products-by-models/", views.ProductsByModelsView.as_view(), name="products_by_models"),
    # AJAX endpoint to fetch jobs (production job numbers) by selected models and products.
    path("jobs-by-selection/", views.JobsBySelectionView.as_view(), name="jobs_by_selection"),
    path("stage/<int:pk>/", views.OrderStageUpdateView.as_view(), name="stage_update"),
    path("api/live-orders/", views.LiveOrdersFeedView.as_view(), name="live_orders_feed"),
    # Warranty card display
    path("warranty/", views.warranty_card, name="warranty"),
    # Warranty card by serial (short URL to avoid very long query strings)
    path("warranty/s/<str:serial>/", views.warranty_card_serial, name="warranty_serial"),
    # Public warranty / order summary by QR serial (no login required)
    path("public/<str:serial>/", views.public_order_summary, name="public_order_summary"),
    # Printable label page for an order
    path("label/<int:pk>/", views.order_label, name="label"),
    path("qr/<str:code>.svg", views.qr_image_svg, name="qr_image"),
]
