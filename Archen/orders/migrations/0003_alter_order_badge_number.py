from django.db import migrations, models


def normalize_badge_numbers(apps, schema_editor):
    Order = apps.get_model('orders', 'Order')
    max_len = getattr(Order._meta.get_field('badge_number'), 'max_length', 50) or 50
    used = set()
    qs = Order.objects.all().order_by('pk').only('pk', 'badge_number')
    for order in qs:
        raw = (order.badge_number or '').strip()
        if not raw:
            if order.badge_number is not None:
                order.badge_number = None
                order.save(update_fields=['badge_number'])
            continue
        base = raw[:max_len]
        candidate = base
        suffix = 1
        lower_candidate = candidate.lower()
        while lower_candidate in used:
            suffix += 1
            extra = f"-{suffix}"
            limit = max_len - len(extra)
            if limit < 1:
                trimmed = ''
            else:
                trimmed = base[:limit]
            candidate = f"{trimmed}{extra}"
            lower_candidate = candidate.lower()
        used.add(lower_candidate)
        if candidate != order.badge_number:
            order.badge_number = candidate
            order.save(update_fields=['badge_number'])


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0002_order_current_stage'),
    ]

    operations = [
        migrations.RunPython(normalize_badge_numbers, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='order',
            name='badge_number',
            field=models.CharField(blank=True, max_length=50, null=True, unique=True),
        ),
    ]
