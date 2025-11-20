# PATH: /Archen/orders/admin.py
from django.contrib import admin
from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0


class OrderAdmin(admin.ModelAdmin):
    # Show QR code in admin list to verify backfill and uniqueness of codes
    list_display = ['customer_name', 'order_date', 'status', 'qr_code']
    list_filter = ['status']
    search_fields = ['customer_name', 'subscription_code']
    inlines = [OrderItemInline]


admin.site.register(Order, OrderAdmin)
admin.site.register(OrderItem)
