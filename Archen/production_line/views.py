# PATH: /Archen/production_line/views.py
from django.db.models import Sum, Count, Q
import logging
import datetime
import logging
from django.http import JsonResponse, HttpResponseForbidden, Http404
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.http import require_GET
from django.contrib import messages
from django import forms
from django.urls import reverse
from django.utils import timezone
from zoneinfo import ZoneInfo
from django.db import transaction, IntegrityError

from inventory.models import Product, Part
from .models import ProductionLog, SectionChoices
from jobs.models import ProductionJob
from .forms import WorkEntryForm
from .utils import (
    get_user_role,
    role_to_section,
    is_parts_based,
    is_products_based,
    product_contains_mdf_page,
)

import jdatetime

# ------------------------------
# Helpers
# ------------------------------

def normalize_section_slug(slug: str) -> str:
    """
    Map legacy/non‑canonical slugs to canonical ones.
    Currently only 'cnc' -> 'cnc_tools' is needed.
    """
    if str(slug).lower() == "cnc":
        return "cnc_tools"
    return slug

def is_manager_or_accountant(user) -> bool:
    """Allow only managers or accountants."""
    role = get_user_role(user)
    return role in ("manager", "accountant")


def _count_open_jobs_for_section(section: str) -> int:
    """
    Return the number of open jobs that should be visible in the
    daily work entry form for the given product-based section.

    The logic mirrors the dropdown population in ``work_entry_view``
    and ``work_entry_manager_view``: only jobs that are not finished,
    do not yet have a log in the target section, and pass the
    allowed_sections / previous-section gating are counted.
    """
    if not is_products_based(section):
        return 0

    qs = (
        ProductionJob.objects
        .filter(finished_at__isnull=True)
        .exclude(productionlog__section=section)
    )
    order = ['assembly', 'workpage', 'undercoating', 'painting', 'sewing', 'upholstery', 'packaging']
    total = 0
    for job in qs.iterator():
        allowed = list(getattr(job, 'allowed_sections', []) or [])
        if allowed:
            allowed_norm = [s for s in order if s in set(x.lower() for x in allowed)]
            if section not in allowed_norm:
                continue
            idx = allowed_norm.index(section)
            if idx > 0:
                prev = allowed_norm[idx - 1]
                if not ProductionLog.objects.filter(job=job, section=prev).exists():
                    continue
        total += 1
    return total

# ------------------------------
# Job management (list/add/edit/delete)
# ------------------------------

@login_required
@user_passes_test(is_manager_or_accountant)

def index(request):
    """Production line top-level tiles."""
    role = get_user_role(request.user)
    is_manager = (role == "manager")
    tiles = [
        {
            'name': 'واحد نجاری',
            'slug': 'carpentry',
            'icon': 'unit_carpentry.png',
            'nested': True,
        },
        {
            'name': 'واحد صفحه‌کاری',
            'slug': 'workpage',
            'icon': 'unit_workpage.png',
            'nested': False,
        },
        {
            'name': 'واحد رنگ زیرکار',
            'slug': 'undercoating',
            'icon': 'unit_undercoating.png',
            'nested': False,
        },
        {
            'name': 'واحد رنگ',
            'slug': 'painting',
            'icon': 'unit_painting.png',
            'nested': False,
        },
        {
            'name': 'واحد رویه‌کوبی',
            'slug': 'upholstery_unit',
            'icon': 'unit_upholstery.png',
            'nested': True,
        },
        {
            'name': 'واحد بسته‌بندی',
            'slug': 'packaging',
            'icon': 'unit_packaging.png',
            'nested': False,
        },
    ]
    context = {'stages': tiles, 'is_manager': is_manager}
    return render(request, 'production_line/production_line.html', context)

@login_required
def work_router_view(request):
    """Route user after login based on role."""
    role = get_user_role(request.user)
    if role == "manager":
        return redirect('dashboard')
    return redirect('production_line:work_entry')

# ------------------------------
# Work entry (worker)
# ------------------------------

@login_required
def work_entry_view(request):
    """Unified daily work entry for the logged-in worker's section."""
    role = get_user_role(request.user)
    section = role_to_section(role)

    # Managers -> production line index; accountants -> accounting dashboard
    if role == "manager":
        return redirect('production_line:index')
    if role == "accountant":
        return redirect('accounting:dashboard')

    if request.method == 'POST':
        # Track whether an inventory-related failure occurred so we
        # can avoid showing the success message in that case.  We
        # intentionally do not attach the inventory message to the
        # form (top-of-page message is sufficient), but we still need
        # to suppress the success toast when inventory check fails.
        inventory_failed = False
        # --- Pre-populate product/model from job_number on POST (server-side safeguard) ---
        # This ensures that even if the client fails to set hidden fields,
        # the server derives authoritative values from the selected job.
        data = request.POST.copy()
        jn = (data.get('job_number') or '').strip()
        if is_products_based(section) and jn:
            try:
                job_prefill = (ProductionJob.objects
                               .filter(job_number=jn)
                               .select_related('product__product_model', 'part__product_model')
                               .first())
            except Exception:
                job_prefill = None
            if job_prefill and getattr(job_prefill, 'product_id', None):
                # Force product id into POST payload
                data['product'] = str(job_prefill.product_id)
                # Also set model by product's product_model name if available
                pm = getattr(getattr(job_prefill, 'product', None), 'product_model', None)
                if pm and getattr(pm, 'name', None):
                    data['model'] = pm.name
        # Use the possibly-updated data for form binding

        form = WorkEntryForm(data, user=request.user)
        if form.is_valid():
            selected_part = form.cleaned_data.get('part')
            selected_product = form.cleaned_data.get('product')
            job_number = form.cleaned_data.get('job_number')
            is_scrap = form.cleaned_data.get('is_scrap')
            is_external = form.cleaned_data.get('is_external')

            if is_parts_based(section) and not selected_part:
                form.add_error('part', "انتخاب قطعه الزامی است.")
            elif is_products_based(section) and not selected_product:
                form.add_error('product', "انتخاب محصول الزامی است.")
            # ``job_number`` is required for product sections.  The
            # WorkEntryForm sets ``required=True`` on the field when
            # appropriate and provides a custom Persian error message.
            # Therefore there is no need to manually add another
            # error here.  Leave the built‑in validation to handle
            # missing job numbers.

            if not form.errors:
                if is_parts_based(section):
                    try:
                        with transaction.atomic():
                            ProductionLog.objects.create(
                                user=request.user,
                                role=role or "",
                                section=section,
                                model=form.cleaned_data['model'],
                                part=selected_part,
                                produced_qty=form.cleaned_data.get('produced_qty') or 0,
                                scrap_qty=form.cleaned_data.get('scrap_qty') or 0,
                                note=form.cleaned_data.get('note'),
                            )
                    except Exception as e:
                        # Surface inventory/constraint errors as a non-field form error (inline),
                        # matching the Users form UX. Avoid redirects and browser popups.
                        form.add_error(None, "موجودی قطعه کافی نیست")
                else:
                    job_obj, created = ProductionJob.objects.get_or_create(
                        job_number=job_number,
                        defaults={'product': selected_product or None, 'part': selected_part or None},
                    )
                    if not created:
                        updated_fields = []
                        if not job_obj.product and selected_product:
                            job_obj.product = selected_product
                            updated_fields.append('product')
                        if not job_obj.part and selected_part:
                            job_obj.part = selected_part
                            updated_fields.append('part')
                        if updated_fields:
                            job_obj.save(update_fields=updated_fields)

                    allowed = getattr(job_obj, 'allowed_sections', []) or []
                    if allowed and section not in allowed:
                        form.add_error('job_number', "این شماره کار برای این بخش مجاز نیست.")

                    # Prevent duplicate registrations when a worker manually types a job number
                    # that has already advanced through this section.
                    if not form.errors and job_obj and ProductionLog.objects.filter(job=job_obj, section=section).exists():
                        form.add_error('job_number', "این شماره کار پیش‌تر در این بخش ثبت شده است.")

                    # If working in the assembly section with a product, ensure sufficient component stock exists.
                    if not form.errors and section == SectionChoices.ASSEMBLY and selected_product and not bool(is_external):
                        try:
                            from production_line.models import get_components_for_product
                            components = get_components_for_product(selected_product)
                        except Exception:
                            components = []
                        missing_parts = []
                        product_model = getattr(selected_product, 'product_model', None)
                        for comp in components:
                            pname = (comp.get('part_name') or '').strip()
                            qty = int(comp.get('qty') or 0)
                            if not pname or qty <= 0:
                                continue
                            part_id = (
                                comp.get('part_id')
                                or comp.get('part_pk')
                                or comp.get('part')
                            )
                            try:
                                part_id = int(part_id)
                            except (TypeError, ValueError):
                                part_id = None
                            qs = Part.objects.all()
                            if part_id:
                                part_obj = qs.filter(pk=part_id).first()
                            elif product_model:
                                part_obj = qs.filter(name=pname, product_model=product_model).first()
                            else:
                                part_obj = qs.filter(name=pname).first()
                            if part_obj:
                                available = part_obj.stock_cnc_tools or 0
                                if available < qty:
                                    missing_parts.append(pname)
                        if missing_parts:
                            unique_parts = sorted(set(missing_parts))
                            msg = "موجودی قطعات زیر کافی نیست: " + "، ".join(unique_parts)
                            form.add_error(None, msg)
                    # For assembly: also ensure sufficient raw materials stock exists (skip for external)
                    if not form.errors and section == SectionChoices.ASSEMBLY and selected_product and not bool(is_external):
                        try:
                            from inventory.models import ProductMaterial
                            mats = ProductMaterial.objects.filter(product=selected_product).select_related('material')
                        except Exception:
                            mats = []
                        missing_materials = []
                        for m in mats:
                            try:
                                req = float(m.qty)
                            except Exception:
                                continue
                            available = float(getattr(m.material, 'quantity', 0) or 0)
                            if available < req:
                                name = (getattr(m.material, 'name', '') or '').strip()
                                if name:
                                    missing_materials.append(name)
                        if missing_materials:
                            unique_mats = sorted(set(missing_materials))
                            msg = "موجودی مواد اولیه زیر کافی نیست: " + "، ".join(unique_mats)
                            form.add_error(None, msg)

                    if not form.errors:
                        if job_number:
                            # Only one job can be default at a time; clear others and mark this job as default.
                            ProductionJob.objects.filter(is_default=True).exclude(job_number=job_number).update(is_default=False)
                            if hasattr(job_obj, 'is_default'):
                                job_obj.is_default = True
                                job_obj.save(update_fields=['is_default'])

                        # Create the production log entry (atomically with inventory checks)
                        try:
                            with transaction.atomic():
                                # For deposit (امانی) jobs, force is_external off
                                if getattr(job_obj, 'job_label', '') == 'deposit' and bool(is_external):
                                    form.add_error(None, "برای کار امانی امکان انتخاب کلاف بیرون وجود ندارد.")
                                    raise Exception('deposit_external_not_allowed')
                                ProductionLog.objects.create(
                                    user=request.user, role=role or "", section=section,
                                    model=form.cleaned_data['model'], part=selected_part, product=selected_product,
                                    job=job_obj, is_scrap=bool(is_scrap), is_external=(False if getattr(job_obj, 'job_label', '') == 'deposit' else bool(is_external)),
                                    note=form.cleaned_data.get('note'),
                                )
                        except IntegrityError:
                            form.add_error('job_number', "این شماره کار پیش‌تر در این بخش ثبت شده است.")
                        except Exception:
                            # Surface inventory/constraint errors as inline non-field error.
                            form.add_error(None, "موجودی محصول کافی نیست")

                        # If marked as scrap (اسقاط), immediately close the job.
                        if bool(is_scrap):
                            job_obj.status = 'scrapped'
                            job_obj.job_label = 'scrapped'
                            job_obj.finished_at = timezone.now()
                            job_obj.save(update_fields=['status', 'job_label', 'finished_at'])

                if not form.errors and not inventory_failed:
                    messages.success(request, "ثبت با موفقیت انجام شد.")
                    return redirect('production_line:work_entry')
    else:
        form = WorkEntryForm(user=request.user)

    # Build dropdown list of open jobs (product sections only)
    label_colors = {
        'in_progress': '#6b7280',  # gray-500
        'completed':   '#68d391',  # green-400
        'scrapped':    '#dc2626',  # red-600
        'warranty':    '#fcd34d',  # yellow-300
        'repaired':    '#2563eb',  # blue-600
        'deposit':     '#8B4513',  # brown
    }
    label_text_colors = {
        'in_progress': '#ffffff',
        'completed':   '#000000',
        'scrapped':    '#ffffff',
        'warranty':    '#000000',
        'repaired':    '#ffffff',
        'deposit':     '#ffffff',
    }

    open_jobs_data = []
    selected_job_number = None
    if is_products_based(section):
        # Exclude jobs that already have a log in this section so that a unit cannot
        # register more than once per job.  Use the implicit reverse relation
        # productionlog_set on ProductionJob.job.
        qs = (ProductionJob.objects
                # English: Show only open jobs; rely on finished_at instead of status label.
                .filter(finished_at__isnull=True)
                .exclude(productionlog__section=section)
                .order_by('-created_at'))
        ORDER = ['assembly', 'workpage', 'undercoating', 'painting', 'sewing', 'upholstery', 'packaging']
        for job in qs:
            allowed = list(getattr(job, 'allowed_sections', []) or [])
            if allowed:
                # Normalize ordering of allowed sections to business flow
                allowed = [s for s in ORDER if s in set(x.lower() for x in allowed)]
                if section not in allowed:
                    continue
                idx = allowed.index(section)
                if idx > 0:
                    prev = allowed[idx - 1]
                    # Only show when previous section has a log for this job
                    if not ProductionLog.objects.filter(job=job, section=prev).exists():
                        continue
            jl = job.job_label or 'in_progress'
            open_jobs_data.append({
                'job_number': job.job_number,
                'job_label': jl,
                'label_display': {
                    'in_progress': 'در حال ساخت',
                    'completed': 'تولید شده',
                    'scrapped': 'اسقاط',
                    'warranty': 'گارانتی',
                    'repaired': 'تعمیرات',
                    'deposit': 'امانی',
                }.get(jl, 'نامشخص'),
                'color': label_colors.get(jl, '#6b7280'),
                'text_color': label_text_colors.get(jl, '#ffffff'),
            })
        # Sort jobs by numeric job_number ascending for a predictable dropdown order
        def _job_sort_key(item):
            jn = str(item.get('job_number') or '').strip()
            try:
                return (0, int(jn))
            except (TypeError, ValueError):
                return (1, jn)
        open_jobs_data.sort(key=_job_sort_key)
        selected_job_number = form.data.get('job_number') if form.is_bound else form.initial.get('job_number')
        # On initial load (GET), default to the smallest job number
        if not form.is_bound and not selected_job_number and open_jobs_data:
            selected_job_number = open_jobs_data[0].get('job_number')
        # On initial load (GET), default to the smallest job number
        if not form.is_bound and not selected_job_number and open_jobs_data:
            selected_job_number = open_jobs_data[0].get('job_number')
        # Hide the job_number text input if we have jobs to present in the dropdown
        if open_jobs_data:
            try:
                form.fields['job_number'].widget = forms.HiddenInput()
            except Exception:
                pass

    section_label = dict(SectionChoices.choices).get(section, "بخش تولید")
    context = {
        "form": form,
        "section": section,
        "page_title": f"ثبت کار روزانه - {section_label}",
        "title": f"ثبت کار روزانه - {section_label}",
        "show_logout": True,
        "open_jobs": [],  # legacy (datalist) not used anymore
        "back_url": reverse('dashboard'),
        "open_jobs_data": open_jobs_data,
        "label_colors": label_colors,
        "label_text_colors": label_text_colors,
        "selected_job_number": selected_job_number,
        "is_products_based": is_products_based(section),
    }
    return render(request, "production_line/work_entry.html", context)

# ------------------------------
# Work entry (manager chooses section)
# ------------------------------

@login_required
def work_entry_select_view(request):
    """Section chooser for managers (reuses the same template)."""
    if get_user_role(request.user) != "manager":
        return HttpResponseForbidden("فقط مدیر می‌تواند این بخش را مشاهده کند.")

    section_tiles = [
        {
            "name": "برش",
            "slug": "cutting",
            "icon": "carpentry_cutting.png",
        },
        {
            "name": "سی‌ان‌سی و ابزار",
            "slug": "cnc_tools",
            "icon": "carpentry_cnc_tools.png",
        },
        {
            "name": "مونتاژ",
            "slug": "assembly",
            "icon": "carpentry_assembly.png",
        },
        {
            "name": "صفحه‌کاری",
            "slug": "workpage",
            "icon": "workpage_sewing.png",
        },
        {
            "name": "خیاطی",
            "slug": "sewing",
            "icon": "upholstery_sewing.png",
        },
        {
            "name": "رویه‌کوبی",
            "slug": "upholstery",
            "icon": "upholstery_upholstery.png",
        },
        {
            "name": "رنگ زیرکار",
            "slug": "undercoating",
            "icon": "unit_undercoating.png",
        },
        {
            "name": "رنگ",
            "slug": "painting",
            "icon": "unit_painting.png",
        },
        {
            "name": "بسته‌بندی",
            "slug": "packaging",
            "icon": "unit_packaging.png",
        },
        {"name": "ایجاد کار", "slug": "create", "icon": ""},
    ]

    if request.method == 'POST':
        selected_slug = (request.POST.get('section') or '').strip()
        valid_slugs = {item['slug'] for item in section_tiles}
        if selected_slug == 'create':
            return redirect('production_line:create_job')
        if selected_slug in valid_slugs:
            return redirect('production_line:work_entry_manager', section=selected_slug)
        messages.error(request, "بخش انتخاب شده نامعتبر است.")

    return render(request, "production_line/work_entry.html", {
        "sections": section_tiles,
        "page_title": "ایجاد یا ویرایش کار",
        "title": "انتخاب بخش برای ثبت کار روزانه",
        "back_url": reverse('production_line:index'),
    })

@login_required
def work_entry_manager_view(request, section: str):
    """Manager version of daily work entry for any section."""
    if get_user_role(request.user) != "manager":
        return HttpResponseForbidden("فقط مدیر می‌تواند این بخش را مشاهده کند.")

    canonical_section = normalize_section_slug(section)

    default_job_number = None
    dj = ProductionJob.objects.filter(is_default=True).first()
    if dj:
        allowed = getattr(dj, 'allowed_sections', []) or []
        if not allowed or canonical_section in allowed:
            default_job_number = dj.job_number

    if request.method == 'POST':
        # Track inventory failures for manager flow as well so we don't show
        # a success message when inventory checks have failed.
        inventory_failed = False
        form = WorkEntryForm(request.POST, user=request.user, section_override=canonical_section)
        if form.is_valid():
            selected_part = form.cleaned_data.get('part')
            selected_product = form.cleaned_data.get('product')
            job_number = form.cleaned_data.get('job_number')
            is_scrap = form.cleaned_data.get('is_scrap')
            is_external = form.cleaned_data.get('is_external')

            if is_parts_based(canonical_section) and not selected_part:
                form.add_error('part', "انتخاب قطعه الزامی است.")
            elif is_products_based(canonical_section) and not selected_product:
                form.add_error('product', "انتخاب محصول الزامی است.")
            # ``job_number`` is required for product sections.  The
            # WorkEntryForm sets ``required=True`` on the field when
            # appropriate and provides a custom Persian error message.

            if not form.errors:
                if is_parts_based(canonical_section):
                    ProductionLog.objects.create(
                        user=request.user, role="manager", section=canonical_section,
                        model=form.cleaned_data['model'], part=selected_part,
                        produced_qty=form.cleaned_data.get('produced_qty') or 0,
                        scrap_qty=form.cleaned_data.get('scrap_qty') or 0,
                        note=form.cleaned_data.get('note'),
                    )
                else:
                    job_obj, created = ProductionJob.objects.get_or_create(
                        job_number=job_number,
                        defaults={'product': selected_product or None, 'part': selected_part or None},
                    )
                    if not created:
                        updated_fields = []
                        if not job_obj.product and selected_product:
                            job_obj.product = selected_product
                            updated_fields.append('product')
                        if not job_obj.part and selected_part:
                            job_obj.part = selected_part
                            updated_fields.append('part')
                        if updated_fields:
                            job_obj.save(update_fields=updated_fields)

                    # Enforce allowed sections and sequential gating (manager view)
                    # English: Only allow current section if it's authorized on the job
                    # and the previous authorized section (if any) already has a log.
                    allowed = list(getattr(job_obj, 'allowed_sections', []) or [])
                    if allowed and canonical_section not in allowed:
                        form.add_error('job_number', "این شماره کار برای این بخش مجاز نیست.")
                    if not form.errors and allowed:
                        ORDER = ['assembly','workpage','undercoating','painting','sewing','upholstery','packaging']
                        allowed_norm = [s for s in ORDER if s in set(x.lower() for x in allowed)]
                        try:
                            idx = allowed_norm.index(str(canonical_section))
                            prev = allowed_norm[idx-1] if idx > 0 else None
                        except ValueError:
                            prev = None
                        if prev and not ProductionLog.objects.filter(job=job_obj, section=prev).exists():
                            form.add_error('job_number', "تا ثبت بخش قبلی، این کار برای این بخش قابل مشاهده نیست.")

                    # For assembly section ensure sufficient parts stock exists for the product (skip for external)
                    if not form.errors and canonical_section == SectionChoices.ASSEMBLY and selected_product and not bool(is_external):
                        try:
                            from production_line.models import get_components_for_product
                            components = get_components_for_product(selected_product)
                        except Exception:
                            components = []
                        missing_parts = []
                        product_model = getattr(selected_product, 'product_model', None)
                        for comp in components:
                            pname = (comp.get('part_name') or '').strip()
                            qty = int(comp.get('qty') or 0)
                            if not pname or qty <= 0:
                                continue
                            part_id = (
                                comp.get('part_id')
                                or comp.get('part_pk')
                                or comp.get('part')
                            )
                            try:
                                part_id = int(part_id)
                            except (TypeError, ValueError):
                                part_id = None
                            qs = Part.objects.all()
                            if part_id:
                                part_obj = qs.filter(pk=part_id).first()
                            elif product_model:
                                part_obj = qs.filter(name=pname, product_model=product_model).first()
                            else:
                                part_obj = qs.filter(name=pname).first()
                            if part_obj:
                                available = part_obj.stock_cnc_tools or 0
                                if available < qty:
                                    missing_parts.append(pname)
                        if missing_parts:
                            unique_parts = sorted(set(missing_parts))
                            msg = "موجودی قطعات زیر کافی نیست: " + "، ".join(unique_parts)
                            messages.error(request, msg)
                            return redirect('production_line:work_entry_manager', section=section)
                    # For assembly section also ensure sufficient raw materials (skip for external)
                    if not form.errors and canonical_section == SectionChoices.ASSEMBLY and selected_product and not bool(is_external):
                        try:
                            from inventory.models import ProductMaterial
                            mats = ProductMaterial.objects.filter(product=selected_product).select_related('material')
                        except Exception:
                            mats = []
                        missing_materials = []
                        for m in mats:
                            try:
                                req = float(m.qty)
                            except Exception:
                                continue
                            available = float(getattr(m.material, 'quantity', 0) or 0)
                            if available < req:
                                name = (getattr(m.material, 'name', '') or '').strip()
                                if name:
                                    missing_materials.append(name)
                        if missing_materials:
                            unique_mats = sorted(set(missing_materials))
                            msg = "موجودی مواد اولیه زیر کافی نیست: " + "، ".join(unique_mats)
                            messages.error(request, msg)
                            return redirect('production_line:work_entry_manager', section=section)

                    if not form.errors:
                        # Update default job flags
                        ProductionJob.objects.filter(is_default=True).exclude(job_number=job_number).update(is_default=False)
                        if hasattr(job_obj, 'is_default'):
                            job_obj.is_default = True
                            job_obj.save(update_fields=['is_default'])

                        # Create the production log entry (handle inventory errors)
                        try:
                            # For deposit (امانی) jobs, force is_external off
                            if getattr(job_obj, 'job_label', '') == 'deposit' and bool(is_external):
                                messages.error(request, "برای کار امانی امکان انتخاب کلاف بیرون وجود ندارد.")
                                return redirect('production_line:work_entry_manager', section=section)
                            ProductionLog.objects.create(
                                user=request.user,
                                role="manager",
                                section=canonical_section,
                                model=form.cleaned_data['model'],
                                part=selected_part,
                                product=selected_product,
                                job=job_obj,
                                is_scrap=bool(is_scrap),
                                is_external=(False if getattr(job_obj, 'job_label', '') == 'deposit' else bool(is_external)),
                                note=form.cleaned_data.get('note'),
                            )
                        except Exception:
                            messages.error(request, "موجودی قطعه کافی نیست")
                            return redirect('production_line:work_entry_manager', section=section)

                        # If scrap is marked, close the job immediately
                        if bool(is_scrap):
                            job_obj.status = 'scrapped'
                            job_obj.job_label = 'scrapped'
                            job_obj.finished_at = timezone.now()
                            job_obj.save(update_fields=['status', 'job_label', 'finished_at'])

                if not form.errors and not inventory_failed:
                    messages.success(request, "ثبت با موفقیت انجام شد.")
                    return redirect('production_line:work_entry_manager', section=section)
    else:
        initial = {'job_number': default_job_number} if default_job_number else None
        form = WorkEntryForm(user=request.user, section_override=canonical_section, initial=initial)

    # Manager page title
    if section == 'sewing':
        section_label = 'خیاطی'
    elif section == 'upholstery':
        section_label = 'رویه‌کوبی'
    elif section == 'workpage':
        section_label = dict(SectionChoices.choices).get(SectionChoices.WORKPAGE, 'صفحه‌کاری')
    else:
        section_label = dict(SectionChoices.choices).get(section, section)

    label_colors = {
        'in_progress': '#6b7280',
        'completed':   '#68d391',
        'scrapped':    '#dc2626',
        'warranty':    '#fcd34d',
        'repaired':    '#2563eb',
        'deposit':     '#8B4513',
    }
    label_text_colors = {
        'in_progress': '#ffffff',
        'completed':   '#000000',
        'scrapped':    '#ffffff',
        'warranty':    '#000000',
        'repaired':    '#ffffff',
        'deposit':     '#ffffff',
    }

    open_jobs_data = []
    selected_job_number = None
    if is_products_based(canonical_section):
        # Exclude jobs that already have a production log for this section.  Each unit may
        # record at most one entry per job number; remove previously logged jobs from
        # the selection list.
        qs = (ProductionJob.objects
                # English: Use finished_at to determine open jobs; repaired label should still be workable
                .filter(finished_at__isnull=True)
                .exclude(productionlog__section=canonical_section)
                .order_by('-created_at'))
        ORDER = ['assembly', 'workpage', 'undercoating', 'painting', 'sewing', 'upholstery', 'packaging']
        for job in qs:
            allowed = list(getattr(job, 'allowed_sections', []) or [])
            if allowed:
                allowed = [s for s in ORDER if s in set(x.lower() for x in allowed)]
                if canonical_section not in allowed:
                    continue
                idx = allowed.index(canonical_section)
                if idx > 0:
                    prev = allowed[idx - 1]
                    if not ProductionLog.objects.filter(job=job, section=prev).exists():
                        continue
            jl = job.job_label or 'in_progress'
            open_jobs_data.append({
                'job_number': job.job_number,
                'job_label': jl,
                'label_display': job.get_job_label_display(),
                'color': label_colors.get(jl, '#6b7280'),
                'text_color': label_text_colors.get(jl, '#ffffff'),
            })
        # Sort jobs by numeric job_number ascending for a predictable dropdown order
        def _job_sort_key(item):
            jn = str(item.get('job_number') or '').strip()
            try:
                return (0, int(jn))
            except (TypeError, ValueError):
                return (1, jn)
        open_jobs_data.sort(key=_job_sort_key)
        selected_job_number = form.data.get('job_number') if form.is_bound else form.initial.get('job_number')
        # Hide the job_number text field when we have at least one option in the dropdown
        if open_jobs_data:
            try:
                form.fields['job_number'].widget = forms.HiddenInput()
            except Exception:
                pass

    context = {
        "form": form,
        "section": canonical_section,
        "page_title": f"ثبت کار روزانه - {section_label}",
        "title": f"ثبت کار روزانه - {section_label}",
        "show_logout": True,
        "open_jobs": [],
        "back_url": reverse('production_line:index'),
        "open_jobs_data": open_jobs_data,
        "label_colors": label_colors,
        "label_text_colors": label_text_colors,
        "selected_job_number": selected_job_number,
    }
    return render(request, "production_line/work_entry.html", context)


@require_GET
@login_required
def api_job_info(request):
    """
    Return model/product info for a given job number as JSON.
    Used to auto-populate read-only fields when the job changes.
    """
    job_number = (request.GET.get('job_number') or '').strip()
    data = {"found": False, "model_name": "", "product_id": None, "product_name": ""}
    if not job_number:
        return JsonResponse(data)

    try:
        from jobs.models import ProductionJob
        job = (ProductionJob.objects
               .filter(job_number=job_number)
               .select_related('product__product_model', 'part__product_model')
               .first())
    except Exception:
        job = None

    if job:
        model_name = ""
        product_id = None
        product_name = ""

        # Prefer product info if present
        product = getattr(job, 'product', None)
        if product:
            product_name = getattr(product, 'name', '') or ''
            product_id = getattr(product, 'id', None)
            pm = getattr(product, 'product_model', None)
            if pm:
                model_name = getattr(pm, 'name', '') or ''

        # Fallback: infer model from part if product not available
        if not model_name and getattr(job, 'part', None):
            pm = getattr(job.part, 'product_model', None)
            if pm:
                model_name = getattr(pm, 'name', '') or ''

        data.update({
            "found": True,
            "model_name": model_name or "",
            "product_id": product_id,
            "product_name": product_name or "",
        })
    return JsonResponse(data)


@require_GET
@login_required
def api_parts_by_model(request):
    model = request.GET.get('model')
    parts = Part.objects.filter(product_model__name=model).order_by('name') if model else Part.objects.none()
    data = [{"id": p.id, "name": p.name} for p in parts]
    return JsonResponse({"results": data})

@require_GET
@login_required
def api_products_by_model(request):
    model = request.GET.get('model')
    products = Product.objects.filter(product_model__name=model).order_by('name') if model else Product.objects.none()
    data = [{"id": pr.id, "name": pr.name} for pr in products]
    return JsonResponse({"results": data})


@require_GET
@login_required
def api_open_jobs_counts(request):
    """
    Return, as JSON, the number of open jobs that should appear in the
    daily work entry form for each product-based section.

    Response shape:
        {
            "results": [
                {"section": "assembly", "label": "مونتاژ", "count": 3},
                ...
            ]
        }
    """
    results = []
    label_map = dict(SectionChoices.choices)
    for section_value, _ in SectionChoices.choices:
        if not is_products_based(section_value):
            continue
        results.append({
            "section": section_value,
            "label": label_map.get(section_value, section_value),
            "count": _count_open_jobs_for_section(section_value),
        })
    return JsonResponse({"results": results})


# New API: return whether a product's materials include MDF/page
@require_GET
@login_required
def api_product_requires_workpage(request):
    """
    Return whether a product's materials BOM contains an MDF/page material.
    Response: { "ok": True, "requires_workpage": true/false }
    """
    product_id = request.GET.get('product_id')
    if not product_id:
        return JsonResponse({"ok": False, "error": "missing product_id"}, status=400)
    try:
        pr = Product.objects.prefetch_related('material_bom_items__material').get(pk=product_id)
    except Product.DoesNotExist:
        return JsonResponse({"ok": False, "error": "not_found"}, status=404)

    requires = product_contains_mdf_page(pr)
    return JsonResponse({"ok": True, "requires_workpage": bool(requires)})

# ------------------------------
# Section dashboard (manager)
# ------------------------------

@login_required
def section_dashboard_view(request, section: str):
    if get_user_role(request.user) != "manager":
        return HttpResponseForbidden("فقط مدیر می‌تواند این بخش را مشاهده کند.")

    if section == 'accounting':
        raise Http404("Accounting dashboard has been moved to its own app.")

    canonical_section = normalize_section_slug(section)

    period = request.GET.get('period', 'daily')
    # English: Use robust Jalali today to avoid TZ/off-range issues on hosts
    try:
        from .models import today_jdate  # Local import to avoid circular import at module load
        today = today_jdate() or jdatetime.date.today()
    except Exception:
        today = jdatetime.date.today()
    # English: Also compute Gregorian today to use for safe arithmetic
    try:
        g_today = today.togregorian()
    except Exception:
        g_today = datetime.date.today()
    start_date = None
    if period == 'daily':
        start_date = today
    elif period == 'weekly':
        try:
            start_date = jdatetime.date.fromgregorian(date=g_today - datetime.timedelta(days=6))
        except Exception:
            start_date = today
    elif period == 'monthly':
        try:
            start_date = jdatetime.date.fromgregorian(date=g_today - datetime.timedelta(days=29))
        except Exception:
            start_date = today
    elif period == 'yearly':
        try:
            start_date = jdatetime.date.fromgregorian(date=g_today - datetime.timedelta(days=364))
        except Exception:
            start_date = today

    log_qs = ProductionLog.objects.filter(section=canonical_section)
    if start_date is not None:
        log_qs = log_qs.filter(jdate__gte=start_date)

    # Chart should reflect effective quantities:
    # - For parts sections: sum of produced_qty and scrap_qty.
    # - For product sections: +1 for non-scrap logs (produced) and +1 for scrap logs (اسقاط).
    # Implemented by summing numeric quantities and adding counts where quantities are zero.
    points_query = (
        log_qs.values('jdate')
             .annotate(
                 sum_produced=Sum('produced_qty'),
                 sum_scrap=Sum('scrap_qty'),
                 count_prod=Count('id', filter=(Q(produced_qty__lte=0) & Q(scrap_qty__lte=0) & Q(is_scrap=False))),
                 count_scrap=Count('id', filter=(Q(scrap_qty__lte=0) & Q(is_scrap=True))),
             )
             .order_by('jdate')
    )
    try:
        raw_points = list(points_query)
    except Exception:
        # English: Some databases may contain invalid dates (e.g., '0000-00-00')
        # that cause jdatetime to raise. Avoid crashing and continue with empty data.
        logging.getLogger(__name__).exception("Failed to load jdate points; using empty dataset")
        raw_points = []
    # Normalize keys to string and build a lookup for padding
    points_map = {}
    for p in raw_points:
        try:
            key = str(p.get('jdate'))
        except Exception:
            key = str(p.get('jdate')) if p.get('jdate') else ''
        produced_val = int(p.get('sum_produced') or 0) + int(p.get('count_prod') or 0)
        scrap_val = int(p.get('sum_scrap') or 0) + int(p.get('count_scrap') or 0)
        points_map[key] = {
            'jdate': key,
            'produced': produced_val,
            'scrap': scrap_val,
        }

    # Build chart points with pretty labels depending on period (force Persian labels)
    WEEKDAYS_FA = ['شنبه','یکشنبه','دوشنبه','سه‌شنبه','چهارشنبه','پنجشنبه','جمعه']
    MONTHS_FA = ['فروردین','اردیبهشت','خرداد','تیر','مرداد','شهریور','مهر','آبان','آذر','دی','بهمن','اسفند']

    def _label_for_date(jd: jdatetime.date) -> str:
        """Return Persian weekday label independent of host locale.

        English comment: Some hosts make jdatetime.strftime("%A") return
        Latin transliterations. We map weekday index → Persian names directly
        to guarantee Farsi output.
        """
        try:
            idx = int(jd.weekday())  # jdatetime: Saturday=0 .. Friday=6
            if 0 <= idx < 7:
                return WEEKDAYS_FA[idx]
        except Exception:
            pass
        try:
            return jd.strftime('%A')
        except Exception:
            return str(jd)

    def _month_key(jd: jdatetime.date) -> str:
        return f"{jd.year:04d}-{jd.month:02d}"

    points = []
    highlight_index = None
    if period in ('daily', 'weekly'):
        # Build current week (Saturday..Friday) using Gregorian arithmetic to avoid jdatetime __sub__ issues
        try:
            # Python weekday: Mon=0..Sun=6; Saturday=5
            back = (g_today.weekday() - 5) % 7
            g_start_w = g_today - datetime.timedelta(days=back)
            for i in range(7):
                g_d = g_start_w + datetime.timedelta(days=i)
                try:
                    jd = jdatetime.date.fromgregorian(date=g_d)
                    key = str(jd)
                    label = _label_for_date(jd)
                except Exception:
                    key = str(g_d)
                    label = g_d.strftime('%a')
                base = points_map.get(key, {'jdate': key, 'produced': 0, 'scrap': 0})
                base['label'] = label
                points.append(base)
            try:
                highlight_index = (g_today - g_start_w).days
            except Exception:
                highlight_index = len(points) - 1
        except Exception:
            # Fallback: seven empty points
            for _ in range(7):
                points.append({'jdate': '', 'produced': 0, 'scrap': 0, 'label': '-'})
            highlight_index = len(points) - 1
    elif period == 'monthly':
        # Current Jalali year months Farvardin..Esfand
        months = [jdatetime.date(today.year, m, 1) for m in range(1, 13)]
        month_totals = { _month_key(m): {'produced': 0, 'scrap': 0} for m in months }
        for key, val in points_map.items():
            try:
                y, m, d2 = [int(x) for x in key.split('-')]
                jd = jdatetime.date(y, m, d2)
            except Exception:
                continue
            mk = _month_key(jd)
            if mk in month_totals:
                month_totals[mk]['produced'] += int(val.get('produced', 0))
                month_totals[mk]['scrap'] += int(val.get('scrap', 0))
        points = []
        for idx, m in enumerate(months):
            mk = _month_key(m)
            totals = month_totals.get(mk, {'produced': 0, 'scrap': 0})
            # Force month label in Persian regardless of locale
            label = MONTHS_FA[idx] if 0 <= idx < 12 else m.strftime('%B')
            points.append({'jdate': mk, 'produced': totals['produced'], 'scrap': totals['scrap'], 'label': label})
        try:
            highlight_index = today.month - 1
        except Exception:
            highlight_index = len(points) - 1
    else:  # yearly
        # Last 5 years aggregated
        years = []
        y0 = jdatetime.date(today.year - 4, 1, 1)
        for y in range(today.year - 4, today.year + 1):
            years.append(y)
        totals = { str(y): {'produced': 0, 'scrap': 0} for y in years }
        for key, val in points_map.items():
            try:
                y, m, d2 = [int(x) for x in key.split('-')]
                jd = jdatetime.date(y, m, d2)
            except Exception:
                continue
            yk = str(jd.year)
            if yk in totals:
                totals[yk]['produced'] += int(val.get('produced', 0))
                totals[yk]['scrap'] += int(val.get('scrap', 0))
        points = []
        for idx, y in enumerate(years):
            t = totals.get(str(y), {'produced': 0, 'scrap': 0})
            points.append({'jdate': str(y), 'produced': t['produced'], 'scrap': t['scrap'], 'label': str(y)})
        highlight_index = len(points) - 1

    def get_model_label(model_code):
        return str(model_code or "-")

    logs_qs = (
        ProductionLog.objects.filter(section=canonical_section)
                             .select_related('product', 'part', 'user')
                             .order_by('-logged_at', '-id')[:50]
    )

    recent_rows = []
    tehran_tz = None
    try:
        tehran_tz = ZoneInfo("Asia/Tehran")
    except Exception:
        tehran_tz = None

    for log in logs_qs:
        jdate_str = str(getattr(log, 'jdate', "") or "")
        time_str = "-"
        if getattr(log, 'logged_at', None):
            try:
                dt = log.logged_at
                if timezone.is_aware(dt):
                    dt_local = timezone.localtime(dt, tehran_tz) if tehran_tz else timezone.localtime(dt)
                else:
                    # Treat naive as UTC then convert
                    dt = timezone.make_aware(dt, timezone.utc)
                    dt_local = timezone.localtime(dt, tehran_tz) if tehran_tz else timezone.localtime(dt)
                time_str = dt_local.strftime("%H:%M")
            except Exception:
                time_str = "-"

        model_label = get_model_label(getattr(log, 'model', None))

        item_name = None
        if getattr(log, 'part_id', None):
            item_name = getattr(log.part, 'name', None)
        if not item_name and getattr(log, 'product_id', None):
            item_name = getattr(log.product, 'name', None)
        if not item_name:
            item_name = getattr(log, 'item_name', None)
        if not item_name:
            item_name = "-"

        user_obj = getattr(log, 'user', None)
        user_name = getattr(user_obj, 'full_name', None) or getattr(user_obj, 'username', "-")

        qty_produced = int(getattr(log, 'produced_qty', 0) or 0)
        qty_scrap = int(getattr(log, 'scrap_qty', 0) or 0)
        if qty_produced or qty_scrap:
            produced_count = qty_produced
            scrap_count = qty_scrap
        else:
            produced_count = 0 if getattr(log, 'is_scrap', False) else 1
            scrap_count = 1 if getattr(log, 'is_scrap', False) else 0

        recent_rows.append({
            "date": jdate_str,
            "time": time_str,
            "model": model_label,
            "name": item_name,
            "produced": produced_count,
            "scrap": scrap_count,
            "user": user_name,
            "note": getattr(log, 'note', "") or "",
        })

    name_column_label = "محصول"
    # Display part names instead of product names for sections that are parts‑based
    if canonical_section in {SectionChoices.CUTTING, SectionChoices.CNC_TOOLS}:
        name_column_label = "قطعه"

    # ------------------------------------------------------------
    # Determine the appropriate label for the “scrap/waste” column.
    #
    # In carpentry sub‑sections (cutting, cnc_tools, assembly) the column
    # represents production waste (ضایعات).  For all other units and the
    # upholstery sub‑sections, the business uses the term “اسقاط” to denote
    # scrapped items.  We therefore compute the label based on the
    # canonical section slug.
    scrap_column_label = "ضایعات"
    if canonical_section not in {
        SectionChoices.CUTTING,
        SectionChoices.CNC_TOOLS,
        SectionChoices.ASSEMBLY,
    }:
        scrap_column_label = "اسقاط"

    if section == "sewing":
        section_label = "خیاطی"
    elif section == "upholstery":
        section_label = "رویه‌کوبی"
    else:
        section_label = dict(SectionChoices.choices).get(section, section)

    parent_unit = None
    if section in {"cutting", "cnc_tools", "assembly"}:
        parent_unit = "carpentry"
    elif section in {"sewing", "upholstery"}:
        parent_unit = "upholstery_unit"

    if parent_unit:
        if parent_unit == 'carpentry':
            back_url = reverse('production_line:carpentry')
        elif parent_unit == 'upholstery_unit':
            back_url = reverse('production_line:upholstery')
        else:
            back_url = reverse('production_line:unit', args=[parent_unit])
    else:
        back_url = reverse('production_line:index')

    context = {
        "section": section,
        "section_label": section_label,
        "points": points,
        "today_logs": recent_rows,
        "name_column_label": name_column_label,
        "scrap_column_label": scrap_column_label,
        "selected_period": period,
        "back_url": back_url,
        "parent_unit_name": 'واحد نجاری' if parent_unit == 'carpentry' else ('واحد رویه‌کوبی' if parent_unit == 'upholstery_unit' else None),
        "period_choices": [('daily', 'روزانه'), ('weekly', 'هفتگی'), ('monthly', 'ماهانه'), ('yearly', 'سالانه')],
        "highlight_index": highlight_index,
    }

    return render(request, "production_line/section_dashboard.html", context)

# ------------------------------
# Unit view (nested cards)
# ------------------------------

@login_required
def unit_view(request, unit: str):
    role = get_user_role(request.user)
    is_manager = (role == "manager")
    unit_map = {
        'carpentry': [
            {'name': 'برش', 'slug': 'cutting', 'icon': 'carpentry_cutting.png'},
            {'name': 'سی‌ان‌سی و ابزار', 'slug': 'cnc_tools', 'icon': 'carpentry_cnc_tools.png'},
            {'name': 'مونتاژ', 'slug': 'assembly', 'icon': 'carpentry_assembly.png'},
        ],
        'upholstery_unit': [
            {'name': 'خیاطی', 'slug': 'sewing', 'icon': 'upholstery_sewing.png'},
            {'name': 'رویه‌کوبی', 'slug': 'upholstery', 'icon': 'upholstery_upholstery.png'},
        ],
    }
    subcards = unit_map.get(unit)
    if not subcards:
        return redirect('production_line:section_dashboard', section=unit)
    unit_titles = {'carpentry': 'واحد نجاری', 'upholstery_unit': 'واحد رویه‌کوبی'}
    unit_name = unit_titles.get(unit, unit)
    return render(request, 'production_line/unit.html', {'subcards': subcards, 'is_manager': is_manager, 'unit_slug': unit, 'unit_name': unit_name})

@login_required
def api_job_details(request):
    job_number = request.GET.get("job_number")
    if not job_number:
        return JsonResponse({"ok": False, "error": "missing job_number"}, status=400)

    try:
        job = (
            ProductionJob.objects
            .select_related("product__product_model", "part__product_model")
            .get(job_number=job_number)
        )
    except ProductionJob.DoesNotExist:
        return JsonResponse({"ok": False, "error": "not_found"}, status=404)

    model_obj = None
    if getattr(job, "product", None) and getattr(job.product, "product_model", None):
        model_obj = job.product.product_model
    elif getattr(job, "part", None) and getattr(job.part, "product_model", None):
        model_obj = job.part.product_model

    payload = {
        "ok": True,
        "model_id": getattr(model_obj, "id", None),
        "model_name": getattr(model_obj, "name", "") or "",
        "product": (
            {"id": job.product_id, "name": job.product.name}
            if job.product_id else None
        ),
    }
    return JsonResponse(payload)
# ------------------------------
# APIs: job search and details
# ------------------------------

@require_GET
def api_job_search(request):
    """Search open jobs by job_number prefix with optional section constraint.

    Returns up to 50 results with colour metadata consistent with work entry.
    This keeps the job number dropdown in daily work entry synchronized with
    the current set of registered jobs and section constraints.
    """
    term = (request.GET.get('term') or '').strip()
    section = normalize_section_slug((request.GET.get('section') or '').strip())
    if not term:
        return JsonResponse({'results': []})

    label_colors = {
        'in_progress': '#6b7280',  # gray-500
        'completed':   '#68d391',  # green-400
        'scrapped':    '#dc2626',  # red-600
        'warranty':    '#fcd34d',  # yellow-300
        'repaired':    '#2563eb',  # blue-600
        'deposit':     '#8B4513',  # brown
    }
    label_text_colors = {
        'in_progress': '#ffffff',
        'completed':   '#000000',
        'scrapped':    '#ffffff',
        'warranty':    '#000000',
        'repaired':    '#ffffff',
        'deposit':     '#ffffff',
    }

    qs = ProductionJob.objects.all()
    # For daily entry we only allow unfinished jobs
    qs = qs.filter(finished_at__isnull=True)
    # Filter by prefix on job_number
    qs = qs.filter(job_number__startswith=term)

    # Helper: numeric-friendly sort key on job_number
    def _jobnum_sort_key(value: str) -> tuple[int, str | int]:
        jn = (value or "").strip()
        try:
            return (0, int(jn))
        except (TypeError, ValueError):
            return (1, jn)

    # Apply section-dependent visibility rules similar to work_entry_view
    if section:
        # Exclude jobs already logged for this section
        qs = qs.exclude(productionlog__section=section)
        # Respect allowed_sections ordering/precedence
        ORDER = ['assembly', 'workpage', 'undercoating', 'painting', 'sewing', 'upholstery', 'packaging']
        candidates = []
        for job in qs.order_by('-created_at')[:200]:  # cap before additional checks
            allowed = list(getattr(job, 'allowed_sections', []) or [])
            if allowed:
                allowed_norm = [s for s in ORDER if s in set(x.lower() for x in allowed)]
                if section not in allowed_norm:
                    continue
                try:
                    idx = allowed_norm.index(section)
                except ValueError:
                    continue
                prev = allowed_norm[idx-1] if idx > 0 else None
                if prev and not ProductionLog.objects.filter(job=job, section=prev).exists():
                    # Previous section not done yet
                    continue
            jl = job.job_label or 'in_progress'
            candidates.append({
                'value': job.job_number,
                'text': job.job_number,
                'label': jl,
                'color': label_colors.get(jl, '#6b7280'),
                'textColor': label_text_colors.get(jl, '#ffffff'),
            })
        # Sort numerically (asc) by job_number and cap to 50 results
        candidates.sort(key=lambda item: _jobnum_sort_key(item.get('value')))
        return JsonResponse({'results': candidates[:50]})

    # If no section is provided, just return up to 50 newest unfinished jobs matching the prefix
    results = []
    for job in qs.order_by('-created_at')[:200]:
        jl = job.job_label or 'in_progress'
        results.append({
            'value': job.job_number,
            'text': job.job_number,
            'label': jl,
            'color': label_colors.get(jl, '#6b7280'),
            'textColor': label_text_colors.get(jl, '#ffffff'),
        })
    results.sort(key=lambda item: _jobnum_sort_key(item.get('value')))
    return JsonResponse({'results': results[:50]})
