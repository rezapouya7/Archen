from django import template

from orders.status_styles import get_status_badge_classes

register = template.Library()


@register.filter(name='order_status_classes')
def order_status_classes(status_label):
    """Return background/text classes for an order status label."""

    return get_status_badge_classes(status_label)
