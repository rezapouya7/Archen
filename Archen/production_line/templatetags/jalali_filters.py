"""
Jalali date conversion filters.

These filters provide a simple way to display Gregorian ``date`` or
``datetime`` objects as Jalali (Persian) dates in templates.  Django's
built‑in ``date`` filter always formats dates according to the Gregorian
calendar, even when the site language is Persian.  To ensure that dates
appear in the correct calendar across the application, load this module
in your template and apply the ``to_jalali`` filter:

    {% load jalali_filters %}
    {{ some_datetime|to_jalali }}

Optionally, pass a format string as an argument to control the output.
The default format ``%Y/%m/%d`` yields a typical Persian date such as
``1402/06/25``.  See the ``jdatetime`` documentation for available
directives.
"""

from __future__ import annotations

import datetime
from django import template

try:
    import jdatetime  # type: ignore
except ImportError:
    # Fallback stub ensures that template rendering does not crash on

    jdatetime = None  # type: ignore

register = template.Library()


@register.filter(name="to_jalali")
def to_jalali(value: object, fmt: str = "%Y/%m/%d") -> str:
    """Convert a Gregorian ``date`` or ``datetime`` into a Jalali date string.

    :param value: A ``datetime.date`` or ``datetime.datetime`` instance.
                  If the value is ``None`` or not a date, it is returned
                  unchanged.
    :param fmt:   Optional strftime pattern for formatting the Jalali date.
                  Defaults to ``%Y/%m/%d``.
    :returns: A formatted Jalali date string, or the original value on
              failure.
    """
    if not value:
        return ""
    if jdatetime is None:

        return str(value)
    try:


        # off‑by‑one errors that can occur when converting directly


        # method for this purpose.
        if hasattr(jdatetime, 'date') and isinstance(value, getattr(jdatetime, 'date')):
            try:
                g_date = value.togregorian()
            except Exception:
                g_date = None
        elif hasattr(jdatetime, 'datetime') and isinstance(value, getattr(jdatetime, 'datetime')):
            try:
                g_date = value.togregorian().date()
            except Exception:
                g_date = None
        else:


            # off by one day in regions with non-Tehran timezones.
            if isinstance(value, datetime.datetime):
                try:
                    from django.utils import timezone as dj_timezone

                    # timezone defined in Django settings (Asia/Tehran).  If

                    g_date = dj_timezone.localtime(value).date()
                except Exception:
                    g_date = value.date()
            elif isinstance(value, datetime.date):
                g_date = value
            else:
                return str(value)

        if not g_date:
            return str(value)


        # ahead or behind the expected value.
        j_date = jdatetime.date.fromgregorian(date=g_date)
        return j_date.strftime(fmt)
    except Exception:
        # On any failure return the original value as a string to
        # avoid breaking template rendering.
        return str(value)