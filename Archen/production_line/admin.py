# PATH: /Archen/production_line/admin.py
from django.contrib import admin
from .models import ProductionLine, ProductionLog, ProductStock


@admin.register(ProductionLine)
class ProductionLineAdmin(admin.ModelAdmin):
    list_display = ("id", "name")
    search_fields = ("name",)


@admin.register(ProductionLog)
class ProductionLogAdmin(admin.ModelAdmin):
    """
    Custom admin for ProductionLog that adapts to the available model fields. The
    ProductionLog model has evolved from quantity-based fields to job-based tracking
    with boolean flags (`is_scrap`, `is_external`).  When the new fields are
    present, they will be shown; otherwise, fallback to old fields so that the
    admin does not error during migrations.
    """

    search_fields = (
        "user__full_name",
        "part__name",
        "product__name",
        # Allow searching by job number when the job relation exists.
        "job__job_number",
    )

    def get_list_display(self, request):
        # Start with common fields
        fields = ["jdate", "section", "user"]
        # Show job if present
        if hasattr(self.model, "job"):
            fields.append("job")
        # Always show part and product if they exist
        if hasattr(self.model, "part"):
            fields.append("part")
        if hasattr(self.model, "product"):
            fields.append("product")
        # Show boolean flags if present
        if hasattr(self.model, "is_scrap"):
            fields.append("is_scrap")
        if hasattr(self.model, "is_external"):
            fields.append("is_external")
        fields.append("logged_at")
        return tuple(fields)

    def get_list_filter(self, request):
        # Basic filters always present
        filters = ["section", "jdate", "user__role"]
        # Add boolean filters when available
        if hasattr(self.model, "is_scrap"):
            filters.append("is_scrap")
        if hasattr(self.model, "is_external"):
            filters.append("is_external")
        return tuple(filters)


@admin.register(ProductStock)
class ProductStockAdmin(admin.ModelAdmin):
    list_display = ("product", "stock_undercoating", "stock_painting", "stock_sewing", "stock_upholstery", "stock_assembly", "stock_packaging")
    search_fields = ("product__name",)


# [auto] Removed non-model admin registration: admin.site.register(SectionChoices)
