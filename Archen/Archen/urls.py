# PATH: /Archen/Archen/urls.py
from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView
from django.conf import settings
from .views import dashboard_view
from users.views import RememberLoginView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('favicon.ico', RedirectView.as_view(url=settings.STATIC_URL + 'favicon.ico', permanent=False)),

    # Auth (login only; logout is handled in users.urls via a custom view)
    path('users/login/', RememberLoginView.as_view(), name='login'),

    # Dashboard landing (managers stay here; workers are routed to work entry)
    path('', dashboard_view, name='dashboard'),
    path('dashboard/', RedirectView.as_view(pattern_name='dashboard', permanent=False)),

    # Apps
    # path('products/', include('products.urls')),  # removed products app
    path('orders/', include('orders.urls')),
    path('inventory/', include('inventory.urls')),
    path('production_line/', include('production_line.urls')),
    path('reports/', include('reports.urls')),

    # Jobs app routes (list/create/edit/bulk delete)
    path('jobs/', include('jobs.urls')),

    # Modularized maintenance and accounting apps
    path('maintenance/', include('maintenance.urls')),
    path('accounting/', include('accounting.urls')),

    # Accounts (namespaced include to enable 'users:...' reverse names)
    path('users/', include(('users.urls', 'users'), namespace='users')),

    # PWA endpoints (manifest, service worker, etc.) — keep at the end
    path('', include('pwa.urls')),
]

if settings.DEBUG:
    from django.conf.urls.static import static
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
