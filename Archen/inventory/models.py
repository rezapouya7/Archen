# PATH: /Archen/inventory/models.py
# -*- coding: utf-8 -*-
"""
Inventory domain models for a manufacturing/assembly system.

- ProductModel: product family/platform catalog.
- Product: sellable/buildable items under a ProductModel.
- Part: manufacturable/stocked sub-assemblies tied to a ProductModel.
- Material: raw inputs with stock and thresholds.
- ProductComponent: Parts BOM (Product ↔ Part with integer qty).
- ProductMaterial: Materials BOM (Product ↔ Material with decimal qty).

Design highlights:
- Normalized FKs (no free-text product types).
- Strong integrity via PROTECT/SET_NULL, unique_together, indexes,
and check constraints.
- i18n-ready verbose_names (fa-IR) with gettext_lazy.
- Timestamps on key models.
"""
from django.db import models
from django.db.models import Q, CheckConstraint
from django.utils.translation import gettext_lazy as _


# ---------------------------
# Core catalog / master data
# ---------------------------
class ProductModel(models.Model):
    name = models.CharField(
        max_length=50,
        unique=True,
        verbose_name=_("نام مدل"),
    )
    description = models.TextField(
        blank=True,
        verbose_name=_("توضیحات"),
    )

    class Meta:
        verbose_name = _("مدل")
        verbose_name_plural = _("مدل‌های محصول")
        ordering = ["name"]
        indexes = [
            models.Index(fields=["name"]),
        ]

    def __str__(self) -> str:
        return self.name


class Product(models.Model):
    name = models.CharField(
        max_length=100,
        # Allow duplicate product names across different models.  Enforce
        # uniqueness in combination with the product_model via unique_together
        # defined on the Meta class instead of a single unique constraint on
        # the name field alone.  Without this change, attempting to create
        # another product with the same name but a different model would
        # trigger a ``unique`` validation error and an English‑language
        # message (“Product with this نام محصول already exists.”) which
        # cannot be translated via the form.  See related discussion in
        # inventory/forms.ProductForm.clean().
        unique=False,
        verbose_name=_("نام محصول"),
    )
    product_model = models.ForeignKey(
        "inventory.ProductModel",
        on_delete=models.PROTECT,
        related_name="products",
        verbose_name=_("مدل"),
    )
    description = models.TextField(
        blank=True,
        verbose_name=_("توضیحات"),
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("ایجاد"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("به‌روزرسانی"))

    class Meta:
        verbose_name = _("محصول")
        verbose_name_plural = _("محصولات")
        # Enforce that a product name may be reused only across different
        # models.  Each (name, product_model) pair must remain unique.
        unique_together = ("name", "product_model")
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["product_model"]),
        ]

    # Convenience helpers
    def parts_bom(self):
        """Return queryset of ProductComponent rows (parts BOM)."""
        return self.bom_items.select_related("part")

    def materials_bom(self):
        """Return queryset of ProductMaterial rows (materials BOM)."""
        return self.material_bom_items.select_related("material")

    def __str__(self) -> str:
        return f"{self.product_model} - {self.name}"


    # ForeignKey.  Code throughout the project should refer to
    # ``product_model`` or ``product_model.name`` directly.  No fallback
    # property is defined here to prevent accidental use of the old API.


class Material(models.Model):
    """
    Raw input stored in warehouse. `quantity` and `threshold` are warehouse-level figures.
    """
    name = models.CharField(
        max_length=100,
        unique=True,
        verbose_name=_("نام ماده اولیه"),
    )

    quantity = models.FloatField(
        blank=True,
        null=True,
        verbose_name=_("مقدار"),
    )
    unit = models.CharField(
        max_length=50,
        blank=True,
        verbose_name=_("واحد"),
    )
    threshold = models.FloatField(
        default=0,
        verbose_name=_("حد آستانه موجودی"),
        help_text=_("در صورت کمتر شدن مقدار از این حد، وضعیت هشدار می‌شود."),
    )

    supplier = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_("تأمین‌کننده"),
    )
    price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name=_("قیمت"),
    )

    stage = models.ForeignKey(
        "production_line.ProductionLine",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="materials",
        verbose_name=_("ایستگاه"),
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("ایجاد"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("به‌روزرسانی"))

    class Meta:
        verbose_name = _("ماده اولیه")
        verbose_name_plural = _("مواد اولیه")
        ordering = ["name"]
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["stage"]),
        ]
        constraints = [
            CheckConstraint(check=Q(threshold__gte=0), name="material_threshold_gte_0"),
            CheckConstraint(
                check=Q(price__isnull=True) | Q(price__gte=0),
                name="material_price_gte_0_or_null",
            ),
            CheckConstraint(
                check=Q(quantity__isnull=True) | Q(quantity__gte=0),
                name="material_quantity_gte_0_or_null",
            ),
        ]

    def is_below_threshold(self) -> bool:
        """Return True if the current quantity is below the threshold (treat None as zero)."""
        qty = self.quantity or 0
        thr = self.threshold or 0
        return qty < thr

    def __str__(self) -> str:
        return self.name


class Part(models.Model):
    """
    Manufacturable/stocked sub-assemblies or components tied to a ProductModel.
    """
    name = models.CharField(
        max_length=100,
        verbose_name=_("نام قطعه"),
    )
    product_model = models.ForeignKey(
        "inventory.ProductModel",
        on_delete=models.PROTECT,
        related_name="parts",
        verbose_name=_("مدل"),
    )

    stock_cut = models.PositiveIntegerField(
        default=0,
        verbose_name=_("موجودی برش"),
    )
    stock_cnc_tools = models.PositiveIntegerField(
        default=0,
        verbose_name=_("موجودی سی‌ان‌سی و ابزار"),
    )
    threshold = models.PositiveIntegerField(
        default=0,
        verbose_name=_("آستانه هشدار"),
    )

    description = models.TextField(
        blank=True,
        verbose_name=_("توضیحات"),
        help_text=_("توضیحات دلخواه برای قطعه (اختیاری)"),
    )

    stage = models.ForeignKey(
        "production_line.ProductionLine",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="parts",
        verbose_name=_("ایستگاه"),
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("ایجاد"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("به‌روزرسانی"))

    class Meta:
        verbose_name = _("قطعه")
        verbose_name_plural = _("قطعات")
        ordering = ["name"]
        unique_together = ("name", "product_model")
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["stage"]),
            models.Index(fields=["product_model"]),
        ]
        constraints = [
            CheckConstraint(check=Q(stock_cut__gte=0), name="part_stock_cut_gte_0"),
            CheckConstraint(check=Q(stock_cnc_tools__gte=0), name="part_stock_cnc_gte_0"),
            CheckConstraint(check=Q(threshold__gte=0), name="part_threshold_gte_0"),
        ]

    def is_below_threshold(self) -> bool:
        """Return True if either stock bucket is below its threshold."""
        thr = self.threshold or 0
        cut = self.stock_cut or 0
        cnc = self.stock_cnc_tools or 0
        return (cut < thr) or (cnc < thr)

    def __str__(self) -> str:
        return f"{self.product_model} - {self.name}"


    # field on Part.  All references to that attribute have been removed.
    # Consumers should use ``product_model`` or ``product_model.name`` to
    # identify the model associated with a part.


# ---------------------------
# Bills of Materials (BOM)
# ---------------------------
class ProductComponent(models.Model):
    """
    Parts BOM for a Product: each record means `product` requires `part` × `qty`.
    """
    product = models.ForeignKey(
        "inventory.Product",
        on_delete=models.CASCADE,          # Deleting a product removes its BOM rows
        related_name="bom_items",
        verbose_name=_("محصول"),
    )
    part = models.ForeignKey(
        "inventory.Part",
        on_delete=models.PROTECT,          # Prevent deleting a part referenced in a BOM
        related_name="used_in_bom",
        verbose_name=_("قطعه"),
    )
    qty = models.PositiveIntegerField(
        default=1,
        verbose_name=_("تعداد موردنیاز"),
    )

    class Meta:
        verbose_name = _("جزء (قطعه) تشکیل‌دهنده")
        verbose_name_plural = _("اجزاء (قطعه) تشکیل‌دهندهٔ محصول")
        unique_together = ("product", "part")
        indexes = [
            models.Index(fields=["product"]),
            models.Index(fields=["part"]),
        ]
        constraints = [
            CheckConstraint(check=Q(qty__gte=1), name="product_component_qty_gte_1"),
        ]

    def __str__(self) -> str:
        return f"{self.product} ↦ {self.part} × {self.qty}"


class ProductMaterial(models.Model):
    """
    Materials BOM for a Product: each record means `product` requires `material` × `qty`.

    `qty` uses Decimal for precise weights/volumes according to Material.unit.
    """
    product = models.ForeignKey(
        "inventory.Product",
        on_delete=models.CASCADE,          # Deleting a product removes its material BOM rows
        related_name="material_bom_items",
        verbose_name=_("محصول"),
    )
    material = models.ForeignKey(
        "inventory.Material",
        on_delete=models.PROTECT,          # Prevent deleting a material referenced in a BOM
        related_name="used_in_bom",
        verbose_name=_("ماده اولیه"),
    )
    qty = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        default=1,
        verbose_name=_("مقدار موردنیاز"),
        help_text=_("مقدار بر اساس واحد تعریف‌شده در ماده اولیه است."),
    )
    # Optional per-product unit override could be added in future if necessary.

    class Meta:
        verbose_name = _("جزء (ماده اولیه) تشکیل‌دهنده")
        verbose_name_plural = _("اجزاء (ماده اولیه) تشکیل‌دهندهٔ محصول")
        unique_together = ("product", "material")
        indexes = [
            models.Index(fields=["product"]),
            models.Index(fields=["material"]),
        ]
        constraints = [
            CheckConstraint(check=Q(qty__gt=0), name="product_material_qty_gt_0"),
        ]

    def __str__(self) -> str:
        return f"{self.product} ↦ {self.material} × {self.qty}"


# Explicit export list for `from inventory.models import *`
__all__ = [
    "Material",
    "Part",
    "Product",
    "ProductModel",
    "ProductComponent",
    "ProductMaterial",
]
