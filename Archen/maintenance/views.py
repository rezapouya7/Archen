# PATH: /Archen/maintenance/views.py
# Archen/Archen/maintenance/views.py
"""
Views for the maintenance app.

This module centralizes potentially destructive actions such as purging
production logs, zeroing inventory counts and rebuilding stocks.  It also
provides simple backup and restore endpoints for administrators.  All
views in this module are restricted to authenticated managers via
runtime checks using the shared ``get_user_role`` helper from the
production_line app.
"""

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, HttpResponseForbidden
from django.views.decorators.http import require_POST
from django.db import transaction
from django.core import management
import tempfile
import os
import json
import subprocess

from production_line.utils import get_user_role
from production_line.models import ProductionLog, ProductStock
from inventory.models import Part, Material


@login_required
def maintenance_view(request):
    """Render the maintenance dashboard for managers only."""
    if get_user_role(request.user) != "manager":
        return HttpResponseForbidden("فقط مدیر می‌تواند این بخش را مشاهده کند.")
    return render(request, "maintenance/maintenance.html", {})


@require_POST
@login_required
@transaction.atomic
def maintenance_action(request):
    """Perform a selected maintenance action.  Only managers may invoke this."""
    if get_user_role(request.user) != "manager":
        return HttpResponseForbidden("فقط مدیر می‌تواند این بخش را انجام دهد.")

    action = request.POST.get("action")
    if action == "purge_logs":
        ProductionLog.objects.all().delete()
        messages.success(request, "تمام گزارش‌ها حذف شدند. موجودی‌ها دست‌نخورده باقی ماندند.")
    elif action == "purge_logs_and_zero":
        ProductionLog.objects.all().delete()
        Part.objects.update(stock_cut=0, stock_cnc_tools=0)
        ProductStock.objects.update(
            stock_undercoating=0, stock_painting=0, stock_sewing=0,
            stock_upholstery=0, stock_assembly=0, stock_packaging=0
        )
        # Also zero warehouse raw materials quantities so the inventory list shows zeros
        # English: Ensure Materials list (dashboard › warehouse › raw materials) reflects zero quantities.
        Material.objects.update(quantity=0)
        messages.success(request, "تمام گزارش‌ها حذف و همهٔ موجودی‌ها صفر شدند.")
    elif action == "rebuild_stocks":
        Part.objects.update(stock_cut=0, stock_cnc_tools=0)
        ProductStock.objects.update(
            stock_undercoating=0, stock_painting=0, stock_sewing=0,
            stock_upholstery=0, stock_assembly=0, stock_packaging=0
        )
        for log in ProductionLog.objects.order_by('logged_at').all():
            log.apply_inventory()
        messages.success(request, "موجودی‌ها بر اساس گزارش‌های فعلی مجدداً محاسبه شدند.")
    else:
        messages.error(request, "اقدام نامعتبر.")

    return redirect('maintenance:maintenance')


@login_required
def maintenance_backup(request):
    """
    Create and download a full PostgreSQL database backup using pg_dump.

    This replaces the previous JSON dump logic and uses the server-side
    pg_dump utility to generate a binary/custom format backup.
    """
    if get_user_role(request.user) != "manager":
        return HttpResponseForbidden("فقط مدیر می‌تواند این بخش را مشاهده کند.")

    try:
        from django.conf import settings

        # Database connection settings (can be overridden from settings)
        db_name = getattr(settings, "ARCHEN_PG_DB_NAME", "archenmo_db")
        db_user = getattr(settings, "ARCHEN_PG_DB_USER", "archenmo_archenmo")
        db_host = getattr(settings, "ARCHEN_PG_DB_HOST", "127.0.0.1")
        db_password = getattr(
            settings,
            "ARCHEN_PG_DB_PASSWORD",
            "uuX61R09aT![Vl",
        )

        env = os.environ.copy()
        env["PGPASSWORD"] = db_password

        # Run pg_dump and capture output in memory
        cmd = [
            "pg_dump",
            "-U",
            db_user,
            "-h",
            db_host,
            "-F",
            "c",
            "-b",
            "-v",
            db_name,
        ]
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )
        if result.returncode != 0:
            err = result.stderr.decode("utf-8", errors="ignore")
            return HttpResponse(
                f"خطا در تولید پشتیبان پایگاه‌داده:\n{err}",
                status=500,
                content_type="text/plain; charset=utf-8",
            )

        # Build a dated filename similar to: archenmo_db_backup_1403-07-10_12-30-45.dump
        try:
            import jdatetime

            now = jdatetime.datetime.now()
            date_str = now.strftime("%Y-%m-%d_%H-%M-%S")
        except Exception:
            from django.utils import timezone

            now = timezone.localtime()
            date_str = now.strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"archenmo_db_backup_{date_str}.dump"

        data = result.stdout
        response = HttpResponse(data, content_type="application/octet-stream")
        response["Content-Length"] = str(len(data))
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response
    except Exception as exc:
        return HttpResponse(
            f"خطا در تولید پشتیبان پایگاه‌داده: {exc}",
            status=500,
            content_type="text/plain; charset=utf-8",
        )


@login_required
@transaction.atomic
def maintenance_restore(request):
    """
    Restore the full PostgreSQL database from an uploaded pg_dump file.

    The uploaded file must be a dump created by pg_dump. The restore is
    performed via pg_restore directly on the PostgreSQL server.
    """
    if get_user_role(request.user) != "manager":
        return HttpResponseForbidden("فقط مدیر می‌تواند این بخش را انجام دهد.")

    if request.method != 'POST':
        return redirect('maintenance:maintenance')

    uploaded_file = request.FILES.get('backup_file')
    if not uploaded_file:
        messages.warning(
            request,
            "هیچ فایلی برای بارگذاری انتخاب نشده است.",
        )
        return redirect('maintenance:maintenance')

    try:
        # Persist uploaded dump to a temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.dump') as tmp:
            for chunk in uploaded_file.chunks():
                tmp.write(chunk)
            tmp_path = tmp.name

        try:
            from django.conf import settings

            db_name = getattr(settings, "ARCHEN_PG_DB_NAME", "archenmo_db")
            db_user = getattr(settings, "ARCHEN_PG_DB_USER", "archenmo_archenmo")
            db_host = getattr(settings, "ARCHEN_PG_DB_HOST", "127.0.0.1")
            db_password = getattr(
                settings,
                "ARCHEN_PG_DB_PASSWORD",
                "uuX61R09aT![Vl",
            )

            env = os.environ.copy()
            env["PGPASSWORD"] = db_password

            # Simple text status file next to the uploaded dump for operators.
            status_path = f"{tmp_path}.status.txt"
            try:
                with open(status_path, "a", encoding="utf-8") as sf:
                    sf.write("شروع بازگردانی پشتیبان پایگاه‌داده...\n")
            except Exception:
                status_path = None

            # Run pg_restore against the target database.
            # Use --clean so existing objects from the backup are dropped
            # before being recreated, to avoid "relation already exists"
            # and duplicate key errors when restoring onto a live database.
            cmd = [
                "pg_restore",
                "-U",
                db_user,
                "-h",
                db_host,
                "-d",
                db_name,
                "--clean",
                "--if-exists",
                "--no-owner",
                "--no-privileges",
                "-v",
                tmp_path,
            ]
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
            )
            # IMPORTANT:
            # Do NOT touch the Django session (messages framework) after pg_restore,
            # because the restore may have dropped/recreated the session tables.
            # Any attempt to save the current session would then raise
            # SessionInterrupted. We intentionally avoid setting messages here.
            err_text = result.stderr.decode("utf-8", errors="ignore")
            # Append final status to the sidecar text file (if we could open it)
            if status_path is not None:
                try:
                    with open(status_path, "a", encoding="utf-8") as sf:
                        if result.returncode == 0:
                            sf.write("بازگردانی با موفقیت انجام شد.\n")
                        else:
                            sf.write("خطا در بازگردانی پشتیبان پایگاه‌داده:\n")
                            if err_text:
                                sf.write(err_text)
                                if not err_text.endswith("\n"):
                                    sf.write("\n")
                except Exception:
                    pass

            if result.returncode != 0:
                # Surface the error via server logs; user will see a generic failure.
                try:
                    import logging
                    logging.getLogger(__name__).error(
                        "PostgreSQL restore failed: %s", err_text
                    )
                except Exception:
                    pass
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
    except Exception as exc:
        messages.error(request, f"خطا در ذخیره فایل پشتیبان: {exc}")
    return redirect('maintenance:maintenance')


# ---------------------------------------------------------------------------
# Per‑app backup/restore helpers and endpoints
# ---------------------------------------------------------------------------
def _dated_filename(prefix: str) -> str:
    """Return a Persian-dated filename like 'prefix_1403-07-10_12-30-45.json'."""
    try:
        import jdatetime
        now = jdatetime.datetime.now()
        date_str = now.strftime('%Y-%m-%d_%H-%M-%S')
    except Exception:
        from django.utils import timezone
        now = timezone.localtime()
        date_str = now.strftime('%Y-%m-%d_%H-%M-%S')
    # Keep the prefix (may contain Persian text). The filename will be
    # returned as-is; we later set Content-Disposition using RFC5987
    # encoding so non-ASCII characters are preserved for downloads.
    safe_prefix = prefix
    return f"{safe_prefix}_{date_str}.json"


def _dump_models_as_response(models: list[str], filename_prefix: str) -> HttpResponse:
    """Dump the given models via dumpdata and return as downloadable response."""
    out = None
    try:
        from io import StringIO
        out = StringIO()
        # Use natural keys for readability and portability within app boundaries
        management.call_command(
            'dumpdata',
            *models,
            stdout=out,
            indent=2,
            use_natural_foreign_keys=True,
            use_natural_primary_keys=True,
        )
    except Exception as e:
        return HttpResponse(f"خطا در تولید پشتیبان: {e}", status=500)
    filename = _dated_filename(filename_prefix)
    data = out.getvalue()
    # Serve JSON with UTF-8 charset and provide RFC5987 filename* header
    response = HttpResponse(data, content_type='application/json; charset=utf-8')
    try:
        from urllib.parse import quote
        filename_encoded = quote(filename)
        # filename* is supported by modern browsers and preserves UTF-8 names
        response['Content-Disposition'] = f"attachment; filename*=utf-8''{filename_encoded}"
    except Exception:
        # Fallback - simple filename (may be mangled for non-ascii)
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


def _restore_from_upload(request, success_message: str) -> tuple[bool, str | None]:
    """Common restore flow using Django loaddata. Returns (ok, error_message)."""
    uploaded_file = request.FILES.get('file') or request.FILES.get('backup_file')
    if not uploaded_file:
        return False, "هیچ فایلی برای بارگذاری انتخاب نشده است."
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.json') as tmp:
            for chunk in uploaded_file.chunks():
                tmp.write(chunk)
            tmp_path = tmp.name
        try:
            management.call_command('loaddata', tmp_path, verbosity=0)
            messages.success(request, success_message)
            return True, None
        except Exception as e:
            return False, f"خطا در بارگذاری پشتیبان: {e}"
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
    except Exception as exc:
        return False, f"خطا در ذخیره فایل پشتیبان: {exc}"


# Inventory: ProductModel, Product, Part, Material, ProductComponent, ProductMaterial
@login_required
def backup_inventory(request):
    if get_user_role(request.user) != "manager":
        return HttpResponseForbidden("فقط مدیر می‌تواند این بخش را مشاهده کند.")
    models = [
        'inventory.ProductModel',
        'inventory.Product',
        'inventory.Part',
        'inventory.Material',
        'inventory.ProductComponent',
        'inventory.ProductMaterial',
    ]
    # Persian filename: 'پشتیبان-انبار_YYYY-MM-DD_HH-MM-SS.json'
    return _dump_models_as_response(models, 'پشتیبان-انبار')


@login_required
@transaction.atomic
def restore_inventory(request):
    if get_user_role(request.user) != "manager":
        return HttpResponseForbidden("فقط مدیر می‌تواند این بخش را انجام دهد.")
    if request.method != 'POST':
        return redirect('maintenance:maintenance')
    ok, err = _restore_from_upload(request, "پشتیبان انبار با موفقیت بارگذاری شد.")
    if not ok and err:
        messages.error(request, err)
    return redirect('maintenance:maintenance')


# Accounting: JSON file at production_line/finance_records.json
@login_required
def backup_accounting(request):
    if get_user_role(request.user) != "manager":
        return HttpResponseForbidden("فقط مدیر می‌تواند این بخش را مشاهده کند.")
    from django.conf import settings
    data_file = os.path.join(settings.BASE_DIR, 'production_line', 'finance_records.json')
    payload = '[]'
    try:
        if os.path.exists(data_file):
            with open(data_file, 'r', encoding='utf-8') as f:
                # Validate JSON to avoid sending corrupt data
                payload_json = json.load(f)
                payload = json.dumps(payload_json, ensure_ascii=False, indent=2)
    except Exception:
        payload = '[]'
    filename = _dated_filename('پشتیبان-حسابداری')
    response = HttpResponse(payload, content_type='application/json; charset=utf-8')
    try:
        from urllib.parse import quote
        response['Content-Disposition'] = f"attachment; filename*=utf-8''{quote(filename)}"
    except Exception:
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required
@transaction.atomic
def restore_accounting(request):
    if get_user_role(request.user) != "manager":
        return HttpResponseForbidden("فقط مدیر می‌تواند این بخش را انجام دهد.")
    if request.method != 'POST':
        return redirect('maintenance:maintenance')
    uploaded_file = request.FILES.get('file') or request.FILES.get('backup_file')
    if not uploaded_file:
        messages.warning(request, "هیچ فایلی برای بارگذاری انتخاب نشده است.")
        return redirect('maintenance:maintenance')
    try:
        data = uploaded_file.read()
        # Validate JSON
        try:
            parsed = json.loads(data.decode('utf-8'))
        except Exception as e:
            messages.error(request, f"فایل JSON نامعتبر است: {e}")
            return redirect('maintenance:maintenance')
        from django.conf import settings
        data_file = os.path.join(settings.BASE_DIR, 'production_line', 'finance_records.json')
        os.makedirs(os.path.dirname(data_file), exist_ok=True)
        with open(data_file, 'w', encoding='utf-8') as f:
            json.dump(parsed, f, ensure_ascii=False, indent=2)
        messages.success(request, "پشتیبان حسابداری با موفقیت بارگذاری شد.")
    except Exception as exc:
        messages.error(request, f"خطا در ذخیره فایل: {exc}")
    return redirect('maintenance:maintenance')


# Production line
@login_required
def backup_production(request):
    if get_user_role(request.user) != "manager":
        return HttpResponseForbidden("فقط مدیر می‌تواند این بخش را مشاهده کند.")
    models = [
        'production_line.ProductionLine',
        'production_line.ProductStock',
        'production_line.ProductionLog',
    ]
    return _dump_models_as_response(models, 'پشتیبان-خط-تولید')


@login_required
@transaction.atomic
def restore_production(request):
    if get_user_role(request.user) != "manager":
        return HttpResponseForbidden("فقط مدیر می‌تواند این بخش را انجام دهد.")
    if request.method != 'POST':
        return redirect('maintenance:maintenance')
    ok, err = _restore_from_upload(request, "پشتیبان خط تولید با موفقیت بارگذاری شد.")
    if not ok and err:
        messages.error(request, err)
    return redirect('maintenance:maintenance')


# Jobs
@login_required
def backup_jobs(request):
    if get_user_role(request.user) != "manager":
        return HttpResponseForbidden("فقط مدیر می‌تواند این بخش را مشاهده کند.")
    models = ['jobs.ProductionJob']
    return _dump_models_as_response(models, 'پشتیبان-کارها')


@login_required
@transaction.atomic
def restore_jobs(request):
    if get_user_role(request.user) != "manager":
        return HttpResponseForbidden("فقط مدیر می‌تواند این بخش را انجام دهد.")
    if request.method != 'POST':
        return redirect('maintenance:maintenance')
    ok, err = _restore_from_upload(request, "پشتیبان کارها با موفقیت بارگذاری شد.")
    if not ok and err:
        messages.error(request, err)
    return redirect('maintenance:maintenance')


# Orders
@login_required
def backup_orders(request):
    if get_user_role(request.user) != "manager":
        return HttpResponseForbidden("فقط مدیر می‌تواند این بخش را مشاهده کند.")
    models = ['orders.Order', 'orders.OrderItem']
    return _dump_models_as_response(models, 'پشتیبان-سفارش‌ها')


@login_required
@transaction.atomic
def restore_orders(request):
    if get_user_role(request.user) != "manager":
        return HttpResponseForbidden("فقط مدیر می‌تواند این بخش را انجام دهد.")
    if request.method != 'POST':
        return redirect('maintenance:maintenance')
    ok, err = _restore_from_upload(request, "پشتیبان سفارش‌ها با موفقیت بارگذاری شد.")
    if not ok and err:
        messages.error(request, err)
    return redirect('maintenance:maintenance')


# Users
@login_required
def backup_users(request):
    if get_user_role(request.user) != "manager":
        return HttpResponseForbidden("فقط مدیر می‌تواند این بخش را مشاهده کند.")
    models = ['users.CustomUser']
    return _dump_models_as_response(models, 'پشتیبان-کاربران')


@login_required
@transaction.atomic
def restore_users(request):
    if get_user_role(request.user) != "manager":
        return HttpResponseForbidden("فقط مدیر می‌تواند این بخش را انجام دهد.")
    if request.method != 'POST':
        return redirect('maintenance:maintenance')
    ok, err = _restore_from_upload(request, "پشتیبان کاربران با موفقیت بارگذاری شد.")
    if not ok and err:
        messages.error(request, err)
    return redirect('maintenance:maintenance')
