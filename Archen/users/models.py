# PATH: /Archen/users/models.py
from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):
    ROLE_CHOICES = [
        ('manager', 'مدیر'),
        ('seller', 'فروشنده'),
        ('accountant', 'حسابدار'),
        ('cutter_master', 'برشکار'),
        ('cnc_master', 'اپراتور سی‌ان‌سی'),
        ('assembly_master', 'مونتاژ‌کار'),
        ('undercoating_master', 'زیرکار‌'),
        ('painting_master', 'نقاش'),
        ('workpage_master', 'صفحه‌کار'),
        ('sewing_master', 'خیاط'),
        ('upholstery_master', 'رویه‌کوب'),
        ('packaging_master', 'بسته‌بند'),
    ]

    full_name = models.CharField(max_length=150)
    role = models.CharField(max_length=30, choices=ROLE_CHOICES)

    def __str__(self):
        return self.full_name or self.username

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"
