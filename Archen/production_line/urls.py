# PATH: /Archen/production_line/urls.py
from django.urls import path
from . import views

app_name = 'production_line'

urlpatterns = [
    # Dependent dropdown + job info APIs
    path('api/parts/', views.api_parts_by_model, name='api_parts'),
    path('api/products/', views.api_products_by_model, name='api_products'),
    path('api/job-info/', views.api_job_info, name='api_job_info'),
    path('api/jobs/search', views.api_job_search, name='api_job_search'),
    path('api/product-requires-workpage/', views.api_product_requires_workpage, name='api_product_requires_workpage'),
    path('api/open-jobs-counts/', views.api_open_jobs_counts, name='api_open_jobs_counts'),
    # Production line tiles (landing/home)
    # Rename the default route name from 'list' to 'index' to improve clarity.
    path('', views.index, name='index'),

    # Router after login (manager -> list, worker -> entry)
    path('route/', views.work_router_view, name='work_router'),

    # Unified work entry form
    path('work/', views.work_entry_view, name='work_entry'),

    # Manager: select a section for work entry
    path('work/manager/', views.work_entry_select_view, name='work_entry_select'),
    # Manager: daily work entry form for a chosen section
    path('work/manager/<str:section>/', views.work_entry_manager_view, name='work_entry_manager'),

    path('section/<str:section>/', views.section_dashboard_view, name='section_dashboard'),

    # Nested unit pages (e.g., carpentry or upholstery units)
    path('unit/<str:unit>/', views.unit_view, name='unit'),

    path("api/job-details", views.api_job_details, name="api_job_details"),  

]

# ----------------------------------------------------------------------
# Simplified unit and section routes
#
# To provide cleaner URLs for the production line, routes with the

# below.  These patterns map directly to the same views but expose
# top‑level addresses such as ``carpentry/`` and ``carpentry/cutting/``.

urlpatterns += [
    # Carpentry unit landing page: lists carpentry sub‑sections
    path('carpentry/', views.unit_view, kwargs={'unit': 'carpentry'}, name='carpentry'),
    # Carpentry sub‑sections: cutting, cnc_tools, assembly
    path('carpentry/<str:section>/', views.section_dashboard_view, name='carpentry_section'),

    # Standalone sections (no nested unit)
    path('workpage/', views.section_dashboard_view, kwargs={'section': 'workpage'}, name='workpage'),
    path('undercoating/', views.section_dashboard_view, kwargs={'section': 'undercoating'}, name='undercoating'),
    path('painting/', views.section_dashboard_view, kwargs={'section': 'painting'}, name='painting'),
    path('packaging/', views.section_dashboard_view, kwargs={'section': 'packaging'}, name='packaging'),

    # Upholstery unit: lists sewing and upholstery sub‑sections
    path('upholstery/', views.unit_view, kwargs={'unit': 'upholstery_unit'}, name='upholstery'),
    # Upholstery sub‑sections: sewing and upholstery
    path('upholstery/<str:section>/', views.section_dashboard_view, name='upholstery_section'),
]
