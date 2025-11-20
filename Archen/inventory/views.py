# PATH: /Archen/inventory/views.py

# Archen/Archen/inventory/views.py
# -*- coding: utf-8 -*-
"""
inventory/views.py
 - Inventory dashboard
 - Parts (list/create/edit/bulk delete)
 - Materials (list/create/edit/bulk delete)
 - Products (list/create/edit/bulk delete) now exposed under the `products/` prefix
 - Product models
"""

from typing import List, Dict

from django.contrib import messages
from django.db.models.deletion import ProtectedError
from django.db import IntegrityError
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.http import require_POST
from django.db.models import F, Q, Value, Count, FloatField
from django.db.models.functions import Coalesce

# Local models/forms
from .models import Part, Material
from .forms import PartForm, MaterialForm
from .forms import ProductStockEditForm  # if used elsewhere

# External domain models/forms
# Import product-related models and forms from the inventory namespace.
# Product and ProductModel are now defined directly in inventory.models, so
# there is no longer a dependency on the removed products app.  Likewise,
# ProductForm is defined in inventory.forms.
from inventory.models import Product, ProductModel, ProductComponent, ProductMaterial
from inventory.forms import ProductForm

import json
from decimal import Decimal, InvalidOperation
from production_line.models import ProductStock

# ----------------------------------
# Access control (manager-only)
# ----------------------------------

# ----------------------------------
# Safe delete helpers
# ----------------------------------
def _explain_protect_error(e: ProtectedError) -> str:
    msg = str(e)
    if "Product.product_model" in msg:
        return "برای این مدل، محصول ثبت شده است."
    if "Part.product_model" in msg:
        return "برای این مدل، قطعه ثبت شده است."
    if "ProductComponent.part" in msg or "used_in_bom" in msg:
        return "این قطعه در لیست قطعات محصولات (BOM) استفاده شده است."
    if "ProductMaterial.material" in msg:
        return "این ماده اولیه در لیست مواد محصولات (BOM) استفاده شده است."
    return "این مورد در بخش‌های دیگری استفاده شده و حذف آن باعث شکستن روابط می‌شود."

def is_manager(user):
    """Allow access only to authenticated users with role=='manager'."""
    return user.is_authenticated and getattr(user, 'role', '') == 'manager'


# ----------------------------------
# Inventory dashboard
# ----------------------------------
@login_required
@user_passes_test(is_manager)
def inventory_dashboard(request):
    return render(request, 'inventory/dashboard_inventory.html')


# ==================================================
# Parts
# ==================================================
@login_required
@user_passes_test(is_manager)
def parts_list_view(request):
    """
    Display a list of parts with optional filtering.

    This view supports filtering by the associated product model name (via
    ``?model=XYZ``) and simple substring search on the part name.  The
    old ``product_type`` free‑text filter is no longer supported now
    that the schema has been normalized around the ``ProductModel``
    relation.  A count of parts below their stock thresholds is also
    computed server‑side.
    """
    qs = Part.objects.all().order_by('name')

    # Filters

    # ``product_type`` parameter is no longer honoured; only the
    # ``model`` parameter is recognised.
    current_model = (request.GET.get('model') or '').strip()
    search_query = (request.GET.get('search') or '').strip()

    if current_model:
        # Filter by the related product_model name.  The ProductModel FK stores
        # the canonical model name, so filter via product_model__name.
        qs = qs.filter(product_model__name=current_model)
    if search_query:
        qs = qs.filter(name__icontains=search_query)

    # Model choices for toolbar filter
    try:
        model_choices = [(m.name, m.name) for m in ProductModel.objects.all().order_by('name')]
    except Exception:
        model_choices = []

    # Below-threshold count (treat null as 0)
    parts_ann = qs.annotate(
        thr=Coalesce('threshold', Value(0)),
        cut=Coalesce('stock_cut', Value(0)),
        # Use the renamed stock_cnc_tools field to compute the CNC/tools stock
        cnc=Coalesce('stock_cnc_tools', Value(0)),
    )
    # Treat at-or-below threshold as shortage to align with dashboard logic
    below_threshold_count = parts_ann.filter(Q(cut__lte=F('thr')) | Q(cnc__lte=F('thr'))).count()

    ctx = {
        'parts': qs,
        'model_choices': model_choices,
        'current_model': current_model,
        'search_query': search_query,
        'parts_count': qs.count(),
        'below_threshold_count': below_threshold_count,
    }
    return render(request, 'inventory/parts_list.html', ctx)


@login_required
@user_passes_test(is_manager)
def parts_create_view(request):
    if request.method == 'POST':
        form = PartForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'قطعه جدید با موفقیت ثبت شد.')
            return redirect('inventory:parts_list')
    else:
        form = PartForm()
    return render(request, 'inventory/part_form.html', {'form': form, 'is_editing': False})


@login_required
@user_passes_test(is_manager)
def parts_edit_view(request, pk: int):
    obj = get_object_or_404(Part, pk=pk)
    if request.method == 'POST':
        form = PartForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, 'تغییرات قطعه ذخیره شد.')
            return redirect('inventory:parts_list')
    else:
        form = PartForm(instance=obj)
    return render(request, 'inventory/part_form.html', {'form': form, 'is_editing': True, 'object': obj})


@login_required
@user_passes_test(is_manager)
@require_POST
def parts_bulk_delete_view(request):
    raw_ids = request.POST.getlist('selected_parts') or request.POST.getlist('selected_items')
    ids: List[int] = []
    for rid in raw_ids:
        try:
            ids.append(int(rid))
        except (TypeError, ValueError):
            continue
    if not ids:
        messages.warning(request, 'هیچ قطعه‌ای انتخاب نشده است.')
        return redirect('inventory:parts_list')

    deleted_ok = 0
    blocked = 0
    for obj in Part.objects.filter(id__in=ids):
        try:
            obj.delete()
            deleted_ok += 1
        except ProtectedError as e:
            blocked += 1
            messages.error(request, f"حذف «{obj}» انجام نشد: {_explain_protect_error(e)}")
        except IntegrityError:
            blocked += 1
            messages.error(request, f"حذف «{obj}» انجام نشد به دلیل ملاحظات یکپارچگی داده‌ها.")
    if deleted_ok:
        messages.success(request, f"{deleted_ok} قطعه حذف شد.")
    elif blocked:
        messages.info(request, "هیچ قطعه‌ای حذف نشد.")
    else:
        messages.info(request, "هیچ قطعه‌ای انتخاب نشده بود.")
    return redirect('inventory:parts_list')


@login_required
@user_passes_test(is_manager)
@require_POST
def parts_inline_update(request):
    """Inline update of a single numeric stock field for a Part.

    Expected JSON body: {"id": <int>, "field": "stock_cut"|"stock_cnc_tools", "value": <int>}
    Returns JSON with normalized values and threshold to update UI state.
    """
    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        return HttpResponseBadRequest('Invalid JSON')

    part_id = payload.get('id')
    field = (payload.get('field') or '').strip()
    value = payload.get('value')

    allowed = {'stock_cut', 'stock_cnc_tools'}
    if field not in allowed:
        return HttpResponseBadRequest('Invalid field')

    try:
        part = get_object_or_404(Part, pk=int(part_id))
    except (TypeError, ValueError):
        return HttpResponseBadRequest('Invalid id')

    # Coerce to non-negative integer
    try:
        new_val = int(value)
    except (TypeError, ValueError):
        return HttpResponseBadRequest('Invalid value')
    if new_val < 0:
        new_val = 0

    # Apply update
    setattr(part, field, new_val)
    try:
        part.save(update_fields=[field, 'updated_at'])
    except Exception:
        return HttpResponseBadRequest('Unable to save')

    # Build response with both stock buckets and threshold for coloring
    return JsonResponse({
        'ok': True,
        'id': part.id,
        'field': field,
        'value': getattr(part, field) or 0,
        'cut': part.stock_cut or 0,
        'cnc': part.stock_cnc_tools or 0,
        'thr': part.threshold or 0,
    })


@login_required
@user_passes_test(is_manager)
@require_POST
def parts_bulk_update(request):
    """Bulk update a numeric stock field for multiple Part rows.

    Expected JSON body: {
      "ids": [<int>, ...],
      "field": "stock_cut"|"stock_cnc_tools",
      "mode": "set"|"inc"|"dec",   # default: set
      "value": <int>
    }

    Returns: { ok: true, count: N, items: [{id, cut, cnc, thr}] }
    """
    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        return HttpResponseBadRequest('Invalid JSON')

    ids = payload.get('ids') or []
    field = (payload.get('field') or '').strip()
    mode = (payload.get('mode') or 'set').strip().lower()
    value = payload.get('value')

    allowed = {'stock_cut', 'stock_cnc_tools'}
    if field not in allowed:
        return HttpResponseBadRequest('Invalid field')

    try:
        delta = int(value)
    except (TypeError, ValueError):
        return HttpResponseBadRequest('Invalid value')
    if delta < 0 and mode in ('set', 'inc'):
        # For set/inc negative input makes little sense; coerce to 0 for set
        if mode == 'set':
            delta = 0

    # Normalize ids list
    norm_ids = []
    for rid in ids:
        try:
            norm_ids.append(int(rid))
        except (TypeError, ValueError):
            continue
    if not norm_ids:
        return HttpResponseBadRequest('No ids provided')

    updated = []
    qs = Part.objects.filter(id__in=norm_ids)
    for part in qs:
        current = getattr(part, field) or 0
        if mode == 'set':
            new_val = max(0, delta)
        elif mode == 'inc':
            new_val = max(0, current + max(0, delta))
        elif mode == 'dec':
            new_val = max(0, current - max(0, delta))
        else:
            return HttpResponseBadRequest('Invalid mode')

        setattr(part, field, int(new_val))
        part.save(update_fields=[field, 'updated_at'])
        updated.append({
            'id': part.id,
            'cut': part.stock_cut or 0,
            'cnc': part.stock_cnc_tools or 0,
            'thr': part.threshold or 0,
        })

    return JsonResponse({'ok': True, 'count': len(updated), 'items': updated})


# ==================================================
# 🧱 Materials
# ==================================================
@login_required
@user_passes_test(is_manager)
def materials_list(request):
    qs = Material.objects.all().order_by('name')

    # Filter by material (name exact) and search (icontains)
    current_material = (request.GET.get('material') or '').strip()
    search_query = (request.GET.get('search') or '').strip()

    if current_material:
        qs = qs.filter(name=current_material)
    if search_query:
        qs = qs.filter(name__icontains=search_query)

    try:
        material_choices = [(n, n) for n in Material.objects.order_by('name').values_list('name', flat=True).distinct()]
    except Exception:
        material_choices = []

    # Compute server-side shortage counter using <= threshold rule
    # English: Treat NULL as 0 for both quantity and threshold.
    qs_ann = qs.annotate(
        # Ensure consistent float output to avoid mixed Integer/Float errors
        qty=Coalesce(F('quantity'), Value(0.0), output_field=FloatField()),
        thr=Coalesce(F('threshold'), Value(0.0), output_field=FloatField()),
    )
    below_threshold_count = qs_ann.filter(qty__lte=F('thr')).count()

    return render(request, 'inventory/materials_list.html', {
        'materials': qs,
        'search_query': search_query,
        'material_choices': material_choices,
        'current_material': current_material,
        'below_threshold_count': below_threshold_count,
    })


@login_required
@user_passes_test(is_manager)
def materials_add(request):
    if request.method == 'POST':
        form = MaterialForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'ماده اولیه با موفقیت ثبت شد.')
            return redirect('inventory:materials_list')
    else:
        form = MaterialForm()
    return render(request, 'inventory/materials_form.html', {'form': form, 'is_editing': False})


@login_required
@user_passes_test(is_manager)
def materials_edit(request, pk: int):
    obj = get_object_or_404(Material, pk=pk)
    if request.method == 'POST':
        form = MaterialForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, 'تغییرات ماده اولیه ذخیره شد.')
            return redirect('inventory:materials_list')
    else:
        form = MaterialForm(instance=obj)
    return render(request, 'inventory/materials_form.html', {'form': form, 'is_editing': True, 'object': obj})


@login_required
@user_passes_test(is_manager)
@require_POST
def materials_bulk_delete(request):
    raw_ids = request.POST.getlist('selected_materials') or request.POST.getlist('selected_items')
    ids: List[int] = []
    for rid in raw_ids:
        try:
            ids.append(int(rid))
        except (TypeError, ValueError):
            continue
    if not ids:
        messages.warning(request, 'هیچ موردی انتخاب نشده است.')
        return redirect('inventory:materials_list')

    deleted_ok = 0
    blocked = 0
    for obj in Material.objects.filter(id__in=ids):
        try:
            obj.delete()
            deleted_ok += 1
        except ProtectedError as e:
            blocked += 1
            messages.error(request, f"حذف «{obj}» انجام نشد: {_explain_protect_error(e)}")
        except IntegrityError:
            blocked += 1
            messages.error(request, f"حذف «{obj}» انجام نشد به دلیل ملاحظات یکپارچگی داده‌ها.")
    if deleted_ok:
        messages.success(request, f"{deleted_ok} ردیف حذف شد.")
    elif blocked:
        messages.info(request, "هیچ ردیفی حذف نشد.")
    else:
        messages.info(request, "هیچ ماده اولیه‌ای انتخاب نشده بود.")
    return redirect('inventory:materials_list')


# ==================================================
#  Products moved under inventory (products-stock/*)
# ==================================================
@login_required
@user_passes_test(is_manager)
def products_list(request):
    # Start with all products and prefetch their stock relationship.  Annotate each
    # product with per-section stock values and the stock threshold.  Missing
    # ProductStock records default to zero via ``Coalesce``.  These annotations
    # allow the template to access ``p.assembly``, ``p.paneling`` and related
    # attributes directly without additional database hits.
    qs = (Product.objects
          .all()
          .select_related('stock')
          .annotate(
              assembly=Coalesce('stock__stock_assembly', Value(0)),
              paneling=Coalesce('stock__stock_workpage', Value(0)),
              undercoat_color=Coalesce('stock__stock_undercoating', Value(0)),
              color=Coalesce('stock__stock_painting', Value(0)),
              sewing=Coalesce('stock__stock_sewing', Value(0)),
              upholstery=Coalesce('stock__stock_upholstery', Value(0)),
              packing=Coalesce('stock__stock_packaging', Value(0)),
              thr=Coalesce('stock__threshold', Value(0)),
          )
          .order_by('id'))
    search_query = (request.GET.get('search') or '').strip()
    model_filter = (request.GET.get('model') or '').strip()


    # ``product_type`` field has been removed from the schema, the only
    # supported filter is on the ``product_model__name`` relation.
    if model_filter:
        qs = qs.filter(product_model__name=model_filter)
    if search_query:
        qs = qs.filter(name__icontains=search_query)

    try:
        model_choices = [(m.name, m.name) for m in ProductModel.objects.all().order_by('id')]
    except Exception:
        model_choices = []

    # Compute server-side shortage count for products: any stage at or below threshold
    below_threshold_count = qs.filter(
        Q(assembly__lte=F('thr')) |
        Q(paneling__lte=F('thr')) |
        Q(undercoat_color__lte=F('thr')) |
        Q(color__lte=F('thr')) |
        Q(sewing__lte=F('thr')) |
        Q(upholstery__lte=F('thr')) |
        Q(packing__lte=F('thr'))
    ).count()

    return render(request, 'inventory/products_list.html', {
        'products': qs,
        'model_choices': model_choices,
        'current_model': model_filter,
        'search_query': search_query,
        'below_threshold_count': below_threshold_count,
    })


@login_required
@user_passes_test(is_manager)
@require_POST
def products_inline_update(request):
    """Inline update of a single ProductStock numeric field for a Product.

    Expected JSON body: {"id": <product_id>, "field": one of stock_* keys, "value": <int>}
    Allowed fields: stock_assembly, stock_workpage, stock_undercoating, stock_painting,
                    stock_sewing, stock_upholstery, stock_packaging
    Returns JSON with all section values and threshold for UI refresh.
    """
    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        return HttpResponseBadRequest('Invalid JSON')

    pid = payload.get('id')
    field = (payload.get('field') or '').strip()
    value = payload.get('value')

    allowed = {
        'stock_assembly', 'stock_workpage', 'stock_undercoating',
        'stock_painting', 'stock_sewing', 'stock_upholstery', 'stock_packaging'
    }
    if field not in allowed:
        return HttpResponseBadRequest('Invalid field')

    try:
        product = get_object_or_404(Product, pk=int(pid))
    except (TypeError, ValueError):
        return HttpResponseBadRequest('Invalid id')

    try:
        new_val = int(value)
    except (TypeError, ValueError):
        return HttpResponseBadRequest('Invalid value')
    if new_val < 0:
        new_val = 0

    stock, _ = ProductStock.objects.get_or_create(product=product)
    setattr(stock, field, new_val)
    try:
        stock.save(update_fields=[field])
    except Exception:
        return HttpResponseBadRequest('Unable to save')

    data = {
        'ok': True,
        'id': product.id,
        'field': field,
        'value': getattr(stock, field) or 0,
        'assembly': stock.stock_assembly or 0,
        'paneling': stock.stock_workpage or 0,
        'undercoat_color': stock.stock_undercoating or 0,
        'color': stock.stock_painting or 0,
        'sewing': stock.stock_sewing or 0,
        'upholstery': stock.stock_upholstery or 0,
        'packing': stock.stock_packaging or 0,
        'thr': stock.threshold or 0,
    }
    return JsonResponse(data)


@login_required
@user_passes_test(is_manager)
@require_POST
def products_bulk_update(request):
    """Bulk update a ProductStock numeric field for multiple products.

    Expected JSON body: {
      "ids": [<product_id>, ...],
      "field": one of stock_* keys,
      "mode": "set"|"inc"|"dec",
      "value": <int>
    }
    Returns: { ok: true, count: N, items: [{id, assembly, paneling, undercoat_color, color, sewing, upholstery, packing, thr}] }
    """
    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        return HttpResponseBadRequest('Invalid JSON')

    ids = payload.get('ids') or []
    field = (payload.get('field') or '').strip()
    mode = (payload.get('mode') or 'set').strip().lower()
    value = payload.get('value')

    allowed = {
        'stock_assembly', 'stock_workpage', 'stock_undercoating',
        'stock_painting', 'stock_sewing', 'stock_upholstery', 'stock_packaging'
    }
    if field not in allowed:
        return HttpResponseBadRequest('Invalid field')

    try:
        delta = int(value)
    except (TypeError, ValueError):
        return HttpResponseBadRequest('Invalid value')
    if delta < 0 and mode in ('set', 'inc'):
        if mode == 'set':
            delta = 0

    norm_ids = []
    for rid in ids:
        try:
            norm_ids.append(int(rid))
        except (TypeError, ValueError):
            continue
    if not norm_ids:
        return HttpResponseBadRequest('No ids provided')

    updated = []
    products = Product.objects.filter(id__in=norm_ids)
    for p in products:
        stock, _ = ProductStock.objects.get_or_create(product=p)
        current = getattr(stock, field) or 0
        if mode == 'set':
            new_val = max(0, delta)
        elif mode == 'inc':
            new_val = max(0, current + max(0, delta))
        elif mode == 'dec':
            new_val = max(0, current - max(0, delta))
        else:
            return HttpResponseBadRequest('Invalid mode')
        setattr(stock, field, int(new_val))
        stock.save(update_fields=[field])
        updated.append({
            'id': p.id,
            'assembly': stock.stock_assembly or 0,
            'paneling': stock.stock_workpage or 0,
            'undercoat_color': stock.stock_undercoating or 0,
            'color': stock.stock_painting or 0,
            'sewing': stock.stock_sewing or 0,
            'upholstery': stock.stock_upholstery or 0,
            'packing': stock.stock_packaging or 0,
            'thr': stock.threshold or 0,
        })

    return JsonResponse({'ok': True, 'count': len(updated), 'items': updated})


@login_required
@user_passes_test(is_manager)
def products_add(request):
    """
    Create a new product along with its bill of materials.

    In addition to the basic product fields (name, model, description), this
    view accepts two hidden JSON payloads – ``components_data`` and
    ``materials_data`` – that describe the parts and materials required to
    assemble the product.  Each payload is parsed and persisted via the
    ProductComponent and ProductMaterial models after the base Product
    instance has been saved.
    """
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            # Persist the Product instance first
            product = form.save()

            # After saving the product, persist the stock threshold on the
            # associated ProductStock.  The threshold value is collected via
            # the extra ``threshold`` field on the ProductForm and is not
            # mapped to any Product model field.  Default to 0 when the
            # field is missing or invalid.  Import locally to avoid
            # circular dependencies at module import time.
            try:
                threshold_val = form.cleaned_data.get('threshold')
                if threshold_val is None:
                    threshold_val = 0
                from production_line.models import ProductStock
                stock, _ = ProductStock.objects.get_or_create(product=product)
                stock.threshold = threshold_val or 0
                stock.save(update_fields=['threshold'])
            except Exception:
                # Swallow exceptions to avoid blocking product creation if
                # stock updates fail; threshold will remain its default.
                pass
            # Parse client‑provided BOM JSON.  Missing or invalid JSON
            # yields an empty list gracefully.
            comps_raw = request.POST.get('components_data') or '[]'
            mats_raw = request.POST.get('materials_data') or '[]'
            try:
                comps_list = json.loads(comps_raw) if comps_raw else []
            except Exception:
                comps_list = []
            try:
                mats_list = json.loads(mats_raw) if mats_raw else []
            except Exception:
                mats_list = []

            # Create ProductComponent rows for each component.  There will be
            # no existing BOM rows on a newly created product, so we simply
            # iterate and insert.  Invalid part IDs or quantities are skipped.
            for comp in comps_list:
                part_id = comp.get('part_id')
                qty = comp.get('qty')
                try:
                    pid = int(part_id)
                    q = int(qty)
                    if q < 1:
                        continue
                except (TypeError, ValueError):
                    continue
                try:
                    part_obj = Part.objects.get(pk=pid)
                except Part.DoesNotExist:
                    continue
                ProductComponent.objects.create(product=product, part=part_obj, qty=q)

            # Create ProductMaterial rows for each material.  Quantities are
            # parsed as Decimals to preserve fractional units.
            for mat in mats_list:
                material_id = mat.get('material_id')
                qty = mat.get('qty')
                try:
                    mid = int(material_id)
                    # Accept numeric strings or numbers; fall back to 0 on error
                    q = Decimal(str(qty))
                    if q <= 0:
                        continue
                except (TypeError, ValueError, InvalidOperation):
                    continue
                try:
                    material_obj = Material.objects.get(pk=mid)
                except Material.DoesNotExist:
                    continue
                ProductMaterial.objects.create(product=product, material=material_obj, qty=q)

            messages.success(request, 'محصول با موفقیت ایجاد شد.')
            return redirect('inventory:products_list')
    else:
        form = ProductForm()

    # Build parts_by_model mapping to drive the client‑side component picker.
    try:
        parts_by_model: Dict[str, List[Dict[str, str]]] = {}
        for m in ProductModel.objects.all().order_by('name'):
            parts_by_model[m.name] = [
                {"id": p.id, "name": p.name}
                for p in m.parts.all().order_by('name')
            ]
    except Exception:
        parts_by_model = {}

    # Build a flat list of all materials for the material picker.
    try:
        materials_list = [
            {"id": m.id, "name": m.name, "unit": m.unit or ""}
            for m in Material.objects.all().order_by('name')
        ]
    except Exception:
        materials_list = []

    # Prepare JSON strings for embedding in the template.  Use ensure_ascii=False
    # to preserve Persian labels correctly.
    parts_json = json.dumps(parts_by_model, ensure_ascii=False)
    materials_json = json.dumps(materials_list, ensure_ascii=False)
    initial_components_json = json.dumps([], ensure_ascii=False)
    initial_materials_json = json.dumps([], ensure_ascii=False)

    return render(request, 'inventory/products_form.html', {
        'form': form,
        'is_editing': False,
        'parts_json': parts_json,
        'materials_json': materials_json,
        'initial_components_json': initial_components_json,
        'initial_materials_json': initial_materials_json,
    })


@login_required
@user_passes_test(is_manager)
def products_edit(request, pk: int):
    obj = get_object_or_404(Product, pk=pk)

    """
    Edit an existing product along with its bill of materials.  This view
    mirrors the behaviour of ``products_add`` but additionally updates or
    deletes existing BOM entries to reflect the submitted JSON.  The
    selected product model may change; if it does, parts belonging to the
    previous model that are no longer valid will be removed during
    submission.
    """
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES, instance=obj)
        if form.is_valid():
            product = form.save()

            # Update the ProductStock threshold after saving the product
            try:
                threshold_val = form.cleaned_data.get('threshold')
                if threshold_val is None:
                    threshold_val = 0
                from production_line.models import ProductStock
                stock, _ = ProductStock.objects.get_or_create(product=product)
                stock.threshold = threshold_val or 0
                stock.save(update_fields=['threshold'])
            except Exception:
                # Non‑fatal: ignore errors updating stock to avoid losing
                # other changes
                pass
            comps_raw = request.POST.get('components_data') or '[]'
            mats_raw = request.POST.get('materials_data') or '[]'
            try:
                comps_list = json.loads(comps_raw) if comps_raw else []
            except Exception:
                comps_list = []
            try:
                mats_list = json.loads(mats_raw) if mats_raw else []
            except Exception:
                mats_list = []

            # Build a map of part_id -> qty for easy lookup and deduplication
            comp_map = {}
            for comp in comps_list:
                try:
                    pid = int(comp.get('part_id'))
                    q = int(comp.get('qty'))
                    if q < 1:
                        continue
                    comp_map[pid] = q
                except (TypeError, ValueError):
                    continue
            # Delete BOM components not present in the submitted list
            ProductComponent.objects.filter(product=product).exclude(part_id__in=comp_map.keys()).delete()
            # Upsert each component
            for pid, q in comp_map.items():
                try:
                    part_obj = Part.objects.get(pk=pid)
                except Part.DoesNotExist:
                    continue
                ProductComponent.objects.update_or_create(
                    product=product,
                    part=part_obj,
                    defaults={'qty': q},
                )

            # Build a map of material_id -> qty for materials
            mat_map = {}
            for mat in mats_list:
                try:
                    mid = int(mat.get('material_id'))
                    q = Decimal(str(mat.get('qty')))
                    if q <= 0:
                        continue
                    mat_map[mid] = q
                except (TypeError, ValueError, InvalidOperation):
                    continue
            # Delete material BOM rows not present
            ProductMaterial.objects.filter(product=product).exclude(material_id__in=mat_map.keys()).delete()
            # Upsert each material
            for mid, q in mat_map.items():
                try:
                    material_obj = Material.objects.get(pk=mid)
                except Material.DoesNotExist:
                    continue
                ProductMaterial.objects.update_or_create(
                    product=product,
                    material=material_obj,
                    defaults={'qty': q},
                )

            messages.success(request, 'تغییرات محصول ذخیره شد.')
            return redirect('inventory:products_list')
    else:
        form = ProductForm(instance=obj)

    # Build parts_by_model mapping
    try:
        parts_by_model: Dict[str, List[Dict[str, str]]] = {}
        for m in ProductModel.objects.all().order_by('name'):
            parts_by_model[m.name] = [
                {"id": p.id, "name": p.name}
                for p in m.parts.all().order_by('name')
            ]
    except Exception:
        parts_by_model = {}

    # Build materials list
    try:
        materials_list = [
            {"id": m.id, "name": m.name, "unit": m.unit or ""}
            for m in Material.objects.all().order_by('name')
        ]
    except Exception:
        materials_list = []

    # Build initial component/material arrays for populating the form.  Each
    # entry includes the PK and quantity only; names are derived client‑side.
    initial_components = [
        {"part_id": pc.part_id, "qty": pc.qty}
        for pc in obj.bom_items.all().order_by('part__name')
    ]
    initial_materials = [
        {"material_id": pm.material_id, "qty": str(pm.qty)}
        for pm in obj.material_bom_items.all().order_by('material__name')
    ]

    parts_json = json.dumps(parts_by_model, ensure_ascii=False)
    materials_json = json.dumps(materials_list, ensure_ascii=False)
    initial_components_json = json.dumps(initial_components, ensure_ascii=False)
    initial_materials_json = json.dumps(initial_materials, ensure_ascii=False)

    return render(request, 'inventory/products_form.html', {
        'form': form,
        'is_editing': True,
        'object': obj,
        'parts_json': parts_json,
        'materials_json': materials_json,
        'initial_components_json': initial_components_json,
        'initial_materials_json': initial_materials_json,
    })


@login_required
@user_passes_test(is_manager)
def products_delete(request, pk: int):
    obj = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        obj.delete()
        messages.success(request, 'محصول حذف شد.')
        return redirect('inventory:products_list')
    return redirect('inventory:products_list')


@login_required
@user_passes_test(is_manager)
def products_bulk_delete(request):
    raw_ids = request.POST.getlist('selected_products') or request.POST.getlist('selected_items')
    ids: List[int] = []
    for rid in raw_ids:
        try:
            ids.append(int(rid))
        except (TypeError, ValueError):
            continue
    if not ids:
        messages.warning(request, 'هیچ موردی انتخاب نشده است.')
        return redirect('inventory:products_list')

    deleted_ok = 0
    blocked = 0
    for obj in Product.objects.filter(id__in=ids):
        try:
            obj.delete()
            deleted_ok += 1
        except ProtectedError as e:
            blocked += 1
            messages.error(request, f"حذف «{obj}» انجام نشد: {_explain_protect_error(e)}")
        except IntegrityError:
            blocked += 1
            messages.error(request, f"حذف «{obj}» انجام نشد به دلیل ملاحظات یکپارچگی داده‌ها.")
    if deleted_ok:
        messages.success(request, f"{deleted_ok} محصول حذف شد.")
    elif blocked:
        messages.info(request, "هیچ محصولی حذف نشد.")
    else:
        messages.info(request, "هیچ محصولی انتخاب نشده بود.")
    return redirect('inventory:products_list')


# ==================================================
# 🧩 Product Models (moved under inventory)
# ==================================================
from .forms import ProductModelForm  # keep local form for styling parity

@login_required
@user_passes_test(is_manager)
def models_list_view(request):
    qs = ProductModel.objects.all().order_by('name')
    current_model = (request.GET.get('model') or '').strip()
    search_query = (request.GET.get('search') or '').strip()

    if current_model:
        qs = qs.filter(name=current_model)
    if search_query:
        qs = qs.filter(name__icontains=search_query) | qs.filter(description__icontains=search_query)

    try:
        model_choices = [(m.name, m.name) for m in ProductModel.objects.all().order_by('name')]
    except Exception:
        model_choices = []

    return render(request, 'inventory/model_list.html', {
        'models': qs,
        'model_choices': model_choices,
        'current_model': current_model,
        'search_query': search_query,
    })


@login_required
@user_passes_test(is_manager)
def model_create_view(request):
    if request.method == 'POST':
        form = ProductModelForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'مدل جدید با موفقیت ایجاد شد.')
            return redirect('inventory:models_list')
    else:
        form = ProductModelForm()
    return render(request, 'inventory/model_form.html', {'form': form, 'is_editing': False})


@login_required
@user_passes_test(is_manager)
def model_edit_view(request, pk: int):
    obj = get_object_or_404(ProductModel, pk=pk)
    if request.method == 'POST':
        form = ProductModelForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, 'تغییرات مدل ذخیره شد.')
            return redirect('inventory:models_list')
    else:
        form = ProductModelForm(instance=obj)
    return render(request, 'inventory/model_form.html', {'form': form, 'is_editing': True, 'object': obj})


@login_required
@user_passes_test(is_manager)
def model_delete_view(request, pk: int):
    obj = get_object_or_404(ProductModel, pk=pk)
    if request.method == 'POST':
        obj.delete()
        messages.success(request, 'مدل حذف شد.')
        return redirect('inventory:models_list')
    return redirect('inventory:models_list')


@login_required
@user_passes_test(is_manager)
def model_bulk_delete_view(request):
    raw_ids = request.POST.getlist('selected_models') or request.POST.getlist('selected_items')
    ids: List[int] = []
    for rid in raw_ids:
        try:
            ids.append(int(rid))
        except (TypeError, ValueError):
            continue
    if not ids:
        messages.warning(request, "شناسه‌های نامعتبر ارسال شده است.")
        return redirect('inventory:models_list')

    deleted_ok = 0
    blocked = 0
    for obj in ProductModel.objects.filter(id__in=ids):
        try:
            obj.delete()
            deleted_ok += 1
        except ProtectedError as e:
            blocked += 1
            messages.error(request, f"حذف «{obj}» انجام نشد: {_explain_protect_error(e)}")
        except IntegrityError:
            blocked += 1
            messages.error(request, f"حذف «{obj}» انجام نشد به دلیل ملاحظات یکپارچگی داده‌ها.")
    if deleted_ok:
        messages.success(request, f"{deleted_ok} مدل حذف شد.")
    elif blocked:
        messages.info(request, "هیچ مدلی حذف نشد.")
    else:
        messages.info(request, "هیچ مدلی انتخاب نشده بود.")
    return redirect('inventory:models_list')
