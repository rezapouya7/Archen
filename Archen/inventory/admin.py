# PATH: /Archen/inventory/admin.py
# -*- coding: utf-8 -*-
"""Django admin registrations for Inventory app."""
from django.contrib import admin
from . import models


class ProductComponentInline(admin.TabularInline):
    """Inline for Product ↔ Part BOM lines."""
    model = models.ProductComponent
    extra = 1
    autocomplete_fields = ("part",)
    fields = ("part", "qty")
    min_num = 0


class ProductMaterialInline(admin.TabularInline):
    """Inline for Product ↔ Material BOM lines."""
    model = models.ProductMaterial
    extra = 1
    autocomplete_fields = ("material",)
    fields = ("material", "qty")
    min_num = 0


@admin.register(models.ProductModel)
class ProductModelAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name", "description")
    ordering = ("name",)


@admin.register(models.Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "product_model", "created_at", "updated_at")
    list_filter = ("product_model",)
    search_fields = ("name", "description", "product_model__name")
    autocomplete_fields = ("product_model",)
    inlines = (ProductComponentInline, ProductMaterialInline)
    readonly_fields = ("created_at", "updated_at")


@admin.register(models.Part)
class PartAdmin(admin.ModelAdmin):
    list_display = ("name", "product_model", "stock_cut", "stock_cnc_tools", "threshold")
    list_filter = ("product_model",)
    search_fields = ("name", "description", "product_model__name")
    autocomplete_fields = ("product_model",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(models.Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ("name", "unit", "quantity", "threshold", "supplier", "price")
    list_filter = ("unit", "supplier")
    search_fields = ("name", "supplier")
    autocomplete_fields = ("stage",)


@admin.register(models.ProductComponent)
class ProductComponentAdmin(admin.ModelAdmin):
    list_display = ("product", "part", "qty")
    search_fields = ("product__name", "part__name")
    autocomplete_fields = ("product", "part")


@admin.register(models.ProductMaterial)
class ProductMaterialAdmin(admin.ModelAdmin):
    list_display = ("product", "material", "qty")
    search_fields = ("product__name", "material__name")
    autocomplete_fields = ("product", "material")
