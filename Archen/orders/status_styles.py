"""Shared styling helpers for order status badges/pills."""

from __future__ import annotations

STATUS_BADGE_CLASS_MAP = {
    'در انتظار': 'bg-gray-200 text-gray-700',
    'در حال ساخت': 'bg-amber-200 text-amber-800',
    'در انبار': 'bg-blue-200 text-blue-800',
    'ارسال شده': 'bg-green-200 text-green-800',
    'لغو شده': 'bg-red-200 text-red-800',
    'گارانتی': 'bg-teal-200 text-teal-800',
}

DEFAULT_STATUS_BADGE_CLASSES = 'bg-gray-200 text-gray-800'


def get_status_badge_classes(status_label: str | None) -> str:
    """Return Tailwind classes for the given Persian status label."""

    if not status_label:
        return DEFAULT_STATUS_BADGE_CLASSES
    return STATUS_BADGE_CLASS_MAP.get(status_label, DEFAULT_STATUS_BADGE_CLASSES)
