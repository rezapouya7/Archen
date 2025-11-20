# PATH: /Archen/accounting/views.py
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, JsonResponse
from django.contrib import messages
from django.conf import settings
from django.utils import timezone
from django.views.decorators.http import require_POST
from datetime import date, datetime, timedelta
import os
import json
import jdatetime
import uuid

# Import the FinanceRecordForm from the local forms module rather than
# from production_line.  The form was moved into the accounting app as
# part of decoupling accounting logic from the production line.
from .forms import FinanceRecordForm
from production_line.utils import get_user_role


def _parse_finance_timestamp(raw_value):
    """Return a Gregorian datetime for the stored Jalali timestamp."""
    if not raw_value:
        return None
    try:
        jdt = jdatetime.datetime.strptime(raw_value, '%Y-%m-%d %H:%M:%S')
        return jdt.togregorian()
    except Exception:
        try:
            # Fallback: try parsing as ISO string in Gregorian space
            return datetime.fromisoformat(raw_value)
        except Exception:
            return None


def _jalali_label(greg_date: date, fmt: str = '%Y/%m/%d') -> str:
    try:
        return jdatetime.date.fromgregorian(date=greg_date).strftime(fmt)
    except Exception:
        return greg_date.strftime('%Y-%m-%d')


def _shift_month(base: date, offset: int) -> date:
    """Return the first day of the month shifted by ``offset`` months."""
    total_months = (base.year * 12 + base.month - 1) + offset
    year = total_months // 12
    month = total_months % 12 + 1
    return date(year, month, 1)


def _shift_year(base: date, offset: int) -> date:
    return date(base.year + offset, 1, 1)


def _floor_to_period(target: date, period: str) -> date:
    if period == 'daily':
        return target
    if period == 'weekly':
        return target - timedelta(days=target.weekday())
    if period == 'monthly':
        return target.replace(day=1)
    if period == 'yearly':
        return target.replace(month=1, day=1)
    return target


def _build_finance_series(records, period: str):
    """Aggregate finance records into time buckets for the requested period."""
    period = period if period in {'daily', 'weekly', 'monthly', 'yearly'} else 'daily'

    now = timezone.localtime()
    today = now.date()
    # Helpers (Jalali)
    def _j_from_greg(gd: date) -> jdatetime.date:
        return jdatetime.date.fromgregorian(date=gd)
    WEEKDAYS = ['شنبه','یکشنبه','دوشنبه','سه‌شنبه','چهارشنبه','پنجشنبه','جمعه']
    MONTHS = ['فروردین','اردیبهشت','خرداد','تیر','مرداد','شهریور','مهر','آبان','آذر','دی','بهمن','اسفند']

    if period in ('daily','weekly'):
        # Build current Jalali week (Saturday → Friday) using Jalali arithmetic
        g_today = today
        j_today = _j_from_greg(g_today)
        # Find start of current Jalali week (last Saturday)
        # Jalali weekday: 0=Saturday ... 6=Friday
        j_weekday = j_today.weekday()  # 0..6 with Saturday=0 in jdatetime
        j_week_start = j_today - jdatetime.timedelta(days=j_weekday)
        # Build 7 days in Jalali, then convert to Gregorian anchors
        j_days = [j_week_start + jdatetime.timedelta(days=d) for d in range(7)]
        bucket_keys = [jd.togregorian() for jd in j_days]
        labels = [jd.strftime('%Y/%m/%d') for jd in j_days]
        labels_display = [WEEKDAYS[i] for i in range(7)]
        # Highlight today's index using Jalali weekday index
        highlight_idx = j_weekday
    elif period == 'monthly':
        # Current Jalali year months Farvardin..Esfand
        j_today = _j_from_greg(today)
        year = j_today.year
        bucket_keys = [jdatetime.date(year, m, 1).togregorian() for m in range(1, 13)]
        labels = [f"{year}/{m:02d}" for m in range(1, 13)]
        labels_display = MONTHS[:]
        highlight_idx = j_today.month - 1
    else:  # yearly
        # Build last 5 years + current year using Jalali year numbers.
        j_today = _j_from_greg(today)
        j_current = j_today.year
        # Labels are Jalali years from current-5 .. current (6 items)
        labels = [str(y) for y in range(j_current - 5, j_current + 1)]
        labels_display = labels[:]
        highlight_idx = len(labels) - 1  # current year should be solid
        # For aggregation buckets, map each label year to the corresponding
        # Gregorian start-of-Jalali-year to floor records by Jalali year.
        bucket_keys = []
        for y in range(j_current - 5, j_current + 1):
            try:
                g_start = jdatetime.date(y, 1, 1).togregorian()
            except Exception:
                # Fallback to Gregorian Jan 1st if conversion fails
                g_start = date(y, 1, 1)
            bucket_keys.append(g_start)

    # Aggregate values per bucket
    if period == 'monthly':
        # Special handling: group by Jalali months of the current year
        j_year = jdatetime.date.fromgregorian(date=today).year
        month_totals = {m: {'receivable': 0, 'payable': 0} for m in range(1, 13)}
        for record in records:
            greg_dt = record.get('gregorian_dt')
            if not greg_dt:
                continue
            try:
                jdt = jdatetime.date.fromgregorian(date=greg_dt.date())
            except Exception:
                continue
            if jdt.year != j_year:
                continue
            try:
                amount = int(record.get('amount', 0))
            except Exception:
                amount = 0
            record_type = record.get('record_type')
            if record_type == 'receivable':
                month_totals[jdt.month]['receivable'] += amount
            elif record_type == 'payable':
                month_totals[jdt.month]['payable'] += amount
        receivable_series = [int(month_totals[m]['receivable']) for m in range(1, 13)]
        payable_series = [int(month_totals[m]['payable']) for m in range(1, 13)]
        net_series = [rec - pay for rec, pay in zip(receivable_series, payable_series)]
    else:
        aggregates = {key: {'receivable': 0, 'payable': 0} for key in bucket_keys}
        for record in records:
            greg_dt = record.get('gregorian_dt')
            if not greg_dt:
                continue
            if period == 'yearly':
                # Floor by Jalali year: find the greatest bucket_start <= record date
                bucket = None
                for start in bucket_keys:
                    if greg_dt.date() >= start:
                        bucket = start
                if bucket is None:
                    continue
            elif period == 'weekly':
                # Map by Jalali day index within the current week range
                jdt = jdatetime.date.fromgregorian(date=greg_dt.date())
                # If record falls within this Jalali week, pick its corresponding Gregorian anchor
                if jdt < j_days[0] or jdt > j_days[-1]:
                    continue
                day_idx = (jdt - j_days[0]).days
                bucket = bucket_keys[day_idx]
            else:
                bucket = _floor_to_period(greg_dt.date(), period)
                if bucket not in aggregates:
                    continue
            try:
                amount = int(record.get('amount', 0))
            except Exception:
                amount = 0
            record_type = record.get('record_type')
            if record_type == 'receivable':
                aggregates[bucket]['receivable'] += amount
            elif record_type == 'payable':
                aggregates[bucket]['payable'] += amount
        receivable_series = [int(aggregates[key]['receivable']) for key in bucket_keys]
        payable_series = [int(aggregates[key]['payable']) for key in bucket_keys]
        net_series = [rec - pay for rec, pay in zip(receivable_series, payable_series)]

    return {
        'labels': labels,
        'labels_display': labels_display,
        'highlight_index': highlight_idx,
        'receivable': receivable_series,
        'payable': payable_series,
        'net': net_series,
    }


@login_required
def dashboard(request):
    """Render the accounting dashboard, allowing managers to view and add finance records."""
    # Allow manager and accountant
    if get_user_role(request.user) not in {"manager", "accountant"}:
        return HttpResponseForbidden("فقط مدیر می‌تواند این بخش را مشاهده کند.")

    # Location for storing finance records.
    # Migrate file from production_line to accounting if needed, preserving existing data.
    old_file = os.path.join(settings.BASE_DIR, 'production_line', 'finance_records.json')
    data_dir = os.path.join(settings.BASE_DIR, 'accounting')
    data_file = os.path.join(data_dir, 'finance_records.json')
    try:
        # Create target dir
        os.makedirs(data_dir, exist_ok=True)
        # If old path exists and new file missing, move it.
        if os.path.exists(old_file) and not os.path.exists(data_file):
            try:
                os.replace(old_file, data_file)
            except Exception:
                # Fallback to copy
                with open(old_file, 'r', encoding='utf-8') as src, open(data_file, 'w', encoding='utf-8') as dst:
                    dst.write(src.read())
    except Exception:
        pass

    # Load existing records from JSON
    finance_records = []
    try:
        if os.path.exists(data_file):
            with open(data_file, 'r', encoding='utf-8') as f:
                finance_records = json.load(f) or []
    except Exception:
        finance_records = []

    raw_records = [dict(rec) for rec in finance_records]

    ids_updated = False
    for rec in raw_records:
        if not rec.get('id'):
            rec['id'] = uuid.uuid4().hex
            ids_updated = True

    if ids_updated:
        try:
            os.makedirs(os.path.dirname(data_file), exist_ok=True)
            with open(data_file, 'w', encoding='utf-8') as f:
                json.dump(raw_records, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # Sort by created_at descending and annotate a human-readable label
    enriched_records = []
    for rec in raw_records:
        parsed_dt = _parse_finance_timestamp(rec.get('created_at'))
        enriched_records.append({**rec, 'gregorian_dt': parsed_dt})

    enriched_records = sorted(enriched_records, key=lambda r: r.get('created_at', ''), reverse=True)

    finance_records = []
    for rec in enriched_records:
        stripped = {k: v for k, v in rec.items() if k != 'gregorian_dt'}
        rt = stripped.get('record_type')
        if rt == 'receivable':
            stripped['record_type_label'] = 'بستانکاری'
        elif rt == 'payable':
            stripped['record_type_label'] = 'بدهکاری'
        else:
            stripped['record_type_label'] = rt or ''
        finance_records.append(stripped)

    # Instantiate the form for adding a new record
    form = FinanceRecordForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        record = form.cleaned_data.copy()
        amount_val = record.get('amount')
        if amount_val is not None:
            try:
                record['amount'] = int(str(amount_val).replace(',', '').strip())
            except Exception:
                record['amount'] = 0
        record['id'] = uuid.uuid4().hex
        # Add timestamp in Jalali for ordering
        record['created_at'] = jdatetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        raw_records.insert(0, record)
        enriched_records.insert(0, {**record, 'gregorian_dt': _parse_finance_timestamp(record['created_at'])})
        # Persist back to JSON
        try:
            os.makedirs(os.path.dirname(data_file), exist_ok=True)
            with open(data_file, 'w', encoding='utf-8') as f:
                json.dump(raw_records, f, ensure_ascii=False, indent=2)
            messages.success(request, "حساب مالی با موفقیت ثبت شد.")
        except Exception as e:
            messages.error(request, f"خطا در ذخیره حساب مالی: {e}")
        return redirect('accounting:dashboard')

    # Aggregate totals for chart
    try:
        total_receivable = sum(int(rec.get('amount', 0)) for rec in raw_records if rec.get('record_type') == 'receivable')
        total_payable = sum(int(rec.get('amount', 0)) for rec in raw_records if rec.get('record_type') == 'payable')
    except Exception:
        total_receivable = 0
        total_payable = 0

    selected_period_raw = request.GET.get('period', 'daily')
    selected_period = selected_period_raw if selected_period_raw in {'daily', 'weekly', 'monthly', 'yearly'} else 'daily'
    series = _build_finance_series(enriched_records, selected_period)

    initial_payload = {
        'chart': {
            'labels': series['labels'],
            'labels_display': series['labels_display'],
            'highlight_index': series['highlight_index'],
            'receivable': series['receivable'],
            'payable': series['payable'],
            'net': series['net'],
        },
        'totals': {
            'receivable': total_receivable,
            'payable': total_payable,
            'net': total_receivable - total_payable,
        },
        'period': selected_period,
    }

    context = {
        'finance_records': finance_records,
        'finance_form': form,
        'finance_chart_labels': ['بستانکاری', 'بدهکاری'],
        'finance_chart_data': [total_receivable, total_payable],
        'finance_totals': {
            'receivable': total_receivable,
            'payable': total_payable,
            'net': total_receivable - total_payable,
        },
        'timeline_labels': series['labels'],
        'timeline_labels_display': series['labels_display'],
        'timeline_highlight': series['highlight_index'],
        'timeline_receivable': series['receivable'],
        'timeline_payable': series['payable'],
        'timeline_net': series['net'],
        'selected_period': selected_period,
        'finance_initial_payload': initial_payload,
    }
    return render(request, 'accounting/dashboard.html', context)


@require_POST
@login_required
def update_finance_record(request):
    # Allow manager and accountant to edit per requirements
    if get_user_role(request.user) not in {"manager", "accountant"}:
        return HttpResponseForbidden("فقط مدیر می‌تواند این بخش را ویرایش کند.")

    try:
        payload = json.loads(request.body.decode('utf-8'))
    except Exception:
        return JsonResponse({'ok': False, 'error': 'درخواست نامعتبر است.'}, status=400)

    record_id = (payload.get('id') or '').strip()
    if not record_id:
        return JsonResponse({'ok': False, 'error': 'شناسه رکورد ارسال نشده است.'}, status=400)

    # Use accounting-local JSON file; migrate from old location if needed
    old_file = os.path.join(settings.BASE_DIR, 'production_line', 'finance_records.json')
    data_dir = os.path.join(settings.BASE_DIR, 'accounting')
    data_file = os.path.join(data_dir, 'finance_records.json')
    try:
        os.makedirs(data_dir, exist_ok=True)
        if os.path.exists(old_file) and not os.path.exists(data_file):
            try:
                os.replace(old_file, data_file)
            except Exception:
                with open(old_file, 'r', encoding='utf-8') as src, open(data_file, 'w', encoding='utf-8') as dst:
                    dst.write(src.read())
    except Exception:
        pass
    raw_records = []
    try:
        if os.path.exists(data_file):
            with open(data_file, 'r', encoding='utf-8') as f:
                raw_records = json.load(f) or []
    except Exception:
        raw_records = []

    target = None
    for rec in raw_records:
        if str(rec.get('id')) == record_id:
            target = rec
            break

    if target is None:
        return JsonResponse({'ok': False, 'error': 'رکورد یافت نشد.'}, status=404)

    entity_name = (payload.get('entity_name') or '').strip()
    description = (payload.get('description') or '').strip()
    amount_raw = payload.get('amount')
    record_type = (payload.get('record_type') or '').strip()

    if not entity_name:
        return JsonResponse({'ok': False, 'error': 'نام نمی‌تواند خالی باشد.'}, status=400)

    try:
        amount = int(str(amount_raw).replace(',', '').strip())
    except Exception:
        return JsonResponse({'ok': False, 'error': 'مبلغ نامعتبر است.'}, status=400)

    if record_type not in {'receivable', 'payable'}:
        return JsonResponse({'ok': False, 'error': 'نوع حساب نامعتبر است.'}, status=400)

    target.update({
        'entity_name': entity_name,
        'amount': amount,
        'record_type': record_type,
        'description': description,
    })

    try:
        os.makedirs(os.path.dirname(data_file), exist_ok=True)
        with open(data_file, 'w', encoding='utf-8') as f:
            json.dump(raw_records, f, ensure_ascii=False, indent=2)
    except Exception as exc:
        return JsonResponse({'ok': False, 'error': f'خطا در ذخیره: {exc}'}, status=500)

    enriched_records = []
    for rec in raw_records:
        parsed_dt = _parse_finance_timestamp(rec.get('created_at'))
        enriched_records.append({**rec, 'gregorian_dt': parsed_dt})

    try:
        total_receivable = sum(int(rec.get('amount', 0)) for rec in raw_records if rec.get('record_type') == 'receivable')
        total_payable = sum(int(rec.get('amount', 0)) for rec in raw_records if rec.get('record_type') == 'payable')
    except Exception:
        total_receivable = 0
        total_payable = 0

    selected_period_raw = payload.get('period') or 'daily'
    selected_period = selected_period_raw if selected_period_raw in {'daily', 'weekly', 'monthly', 'yearly'} else 'daily'
    series = _build_finance_series(enriched_records, selected_period)

    record_type_label = 'بستانکاری' if record_type == 'receivable' else 'بدهکاری'

    return JsonResponse(
        {
            'ok': True,
            'record': {
                'id': record_id,
                'entity_name': entity_name,
                'amount': amount,
                'record_type': record_type,
                'record_type_label': record_type_label,
                'description': description,
            },
            'totals': {
                'receivable': total_receivable,
                'payable': total_payable,
                'net': total_receivable - total_payable,
            },
            'chart': {
                'period': selected_period,
                'labels': series['labels'],
                'labels_display': series['labels_display'],
                'highlight_index': series['highlight_index'],
                'receivable': series['receivable'],
                'payable': series['payable'],
                'net': series['net'],
            },
        }
    )


@require_POST
@login_required
def bulk_delete_records(request):
    """Delete one or more finance records by IDs (POST with 'ids').

    Comments: Accepts multiple 'ids' form field values from the dashboard table.
    Only managers and accountants are permitted per business rule.
    """
    if get_user_role(request.user) not in {"manager", "accountant"}:
        return HttpResponseForbidden("فقط مدیر می‌تواند این بخش را حذف کند.")

    ids = request.POST.getlist('ids')
    if not ids:
        messages.warning(request, "هیچ ردیفی انتخاب نشده است.")
        return redirect('accounting:dashboard')

    # Load JSON from accounting path (migrating if necessary)
    old_file = os.path.join(settings.BASE_DIR, 'production_line', 'finance_records.json')
    data_dir = os.path.join(settings.BASE_DIR, 'accounting')
    data_file = os.path.join(data_dir, 'finance_records.json')
    try:
        os.makedirs(data_dir, exist_ok=True)
        if os.path.exists(old_file) and not os.path.exists(data_file):
            try:
                os.replace(old_file, data_file)
            except Exception:
                with open(old_file, 'r', encoding='utf-8') as src, open(data_file, 'w', encoding='utf-8') as dst:
                    dst.write(src.read())
    except Exception:
        pass

    raw_records = []
    try:
        if os.path.exists(data_file):
            with open(data_file, 'r', encoding='utf-8') as f:
                raw_records = json.load(f) or []
    except Exception:
        raw_records = []

    before = len(raw_records)
    id_set = set(str(x) for x in ids)
    filtered = [rec for rec in raw_records if str(rec.get('id')) not in id_set]

    try:
        with open(data_file, 'w', encoding='utf-8') as f:
            json.dump(filtered, f, ensure_ascii=False, indent=2)
        removed = before - len(filtered)
        if removed:
            messages.success(request, f"{removed} رکورد حذف شد.")
        else:
            messages.info(request, "رکوردی حذف نشد.")
    except Exception as exc:
        messages.error(request, f"خطا در حذف: {exc}")

    return redirect('accounting:dashboard')
