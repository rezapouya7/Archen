# PATH: /Archen/orders/models.py
from django.db import models
import django_jalali.db.models as jmodels


class Order(models.Model):
    STATUS_CHOICES = [
        ('در انتظار', 'در انتظار'),
        ('در حال ساخت', 'در حال ساخت'),
        ('در انبار', 'در انبار'),
        ('ارسال شده', 'ارسال شده'),
        ('لغو شده', 'لغو شده'),
        ('گارانتی', 'گارانتی'),
    ]
    STAGE_CHOICES = [
        ('در انتظار تولید', 'در انتظار تولید'),
        ('زیرکاری A', 'زیرکاری A'),
        ('زیرکاری B', 'زیرکاری B'),
        ('زیرکاری C', 'زیرکاری C'),
        ('رنگ‌‌کاری', 'رنگ‌‌کاری'),
        ('رویه‌کوبی', 'رویه‌کوبی'),
        ('بسته‌بندی', 'بسته‌بندی'),
    ]

    model = models.CharField(max_length=100, blank=True, null=True)
    # Subscription code for the customer.  Renamed in the UI to "کد اشتراک مشتری".
    subscription_code = models.CharField(max_length=50, blank=True, null=True)

    # Store/exhibition name.  In the UI this field is labelled "نام فروشگاه".
    exhibition_name = models.CharField(max_length=100, blank=True, null=True)

    # New: badge/receipt number for the order (شماره بیجک).
    badge_number = models.CharField(max_length=50, blank=True, null=True, unique=True)

    # New: name of the producer/manufacturer (تولید کننده).
    producer = models.CharField(max_length=100, blank=True, null=True)

    # New: geographical region (منطقه) associated with the order/delivery.
    region = models.CharField(max_length=100, blank=True, null=True)

    # New: customer phone number (شماره تماس مشتری).
    customer_phone = models.CharField(max_length=20, blank=True, null=True)

    # New: driver phone number (شماره تماس راننده).
    driver_phone = models.CharField(max_length=20, blank=True, null=True)

    # New: the person or entity sending the order (ارسال کننده).
    sender = models.CharField(max_length=100, blank=True, null=True)

    # New: name of the driver responsible for delivery (نام راننده).
    driver_name = models.CharField(max_length=100, blank=True, null=True)
    customer_name = models.CharField(max_length=100, blank=True, null=True)
    city = models.CharField(max_length=50, blank=True, null=True)


    order_date = jmodels.jDateField(blank=True, null=True)
    fabric_description = models.TextField(blank=True, null=True)
    fabric_code = models.CharField(max_length=50, blank=True, null=True)
    fabric_entry_date = jmodels.jDateField(blank=True, null=True)
    color_code = models.CharField(max_length=50, blank=True, null=True)
    delivery_date = jmodels.jDateField(blank=True, null=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    current_stage = models.CharField(
        max_length=32,
        choices=STAGE_CHOICES,
        default=STAGE_CHOICES[0][0],
        verbose_name="مرحله فعلی",
        help_text="آخرین مرحله انجام‌شده در خط تولید."
    )
    description = models.TextField(blank=True, null=True)

    # Each order is assigned a unique QR code on creation.  This string can be
    # encoded into a QR graphic externally.  It is populated automatically
    # when the order is first saved.
    qr_code = models.CharField(
        max_length=64,
        unique=True,
        blank=True,
        null=True,
        verbose_name="کد کیوآر",
        help_text="شناسه یکتا برای تولید کد QR سفارش."
    )

    def save(self, *args, **kwargs):
        """Assign a QR code once on initial save.  Uses uuid4 for randomness."""
        import uuid
        if not getattr(self, "qr_code", None):
            # Generate a 32-character hex string
            self.qr_code = uuid.uuid4().hex
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.customer_name} - {self.order_date}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name="items", on_delete=models.CASCADE)
    product = models.ForeignKey('inventory.Product', on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(default=1)
    job_number = models.CharField(
        max_length=64,
        unique=True,
        blank=True,
        null=True,
        verbose_name="شماره کار",
        help_text="شماره یکتا برای پیگیری محصول در خط تولید."
    )

    class Meta:
        unique_together = ('order', 'product')
        verbose_name = "OrderItem"
        verbose_name_plural = "OrderItems"

    def __str__(self):
        return f"{self.order_id} - {self.product} x{self.quantity}"
