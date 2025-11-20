# PATH: /Archen/orders/management/commands/backfill_order_qr.py
from django.db import models
from django.core.management.base import BaseCommand
from orders.models import Order


class Command(BaseCommand):
    help = "Assign QR codes to orders that do not yet have one."

    def handle(self, *args, **options):
        import uuid
        updated = 0
        for order in Order.objects.filter(models.Q(qr_code__isnull=True) | models.Q(qr_code='')):
            order.qr_code = uuid.uuid4().hex
            order.save(update_fields=["qr_code"])
            updated += 1
        if updated:
            self.stdout.write(self.style.SUCCESS(f"Assigned QR codes to {updated} orders."))
        else:
            self.stdout.write("No orders required QR code assignment.")
