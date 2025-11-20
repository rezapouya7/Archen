# PATH: /Archen/production_line/models.py
# -*- coding: utf-8 -*-
from django.db import models, transaction
from django.conf import settings
from django.utils import timezone
from django_jalali.db import models as jmodels
import jdatetime
from inventory.models import Part
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def get_components_for_product(product) -> list[dict]:
    """Return a list of {'part_name': str, 'qty': int} for the product's BOM.

    Prefer normalized BOM rows (inventory.ProductComponent).  If a dynamic
    ``components`` attribute is present on the model instance (e.g. populated
    by a form or serializer), fall back to it.
    """
    if product is None:
        return []
    # Dynamic attribute provided by forms/serializer?
    dyn = getattr(product, 'components', None)
    if isinstance(dyn, (list, tuple)) and dyn:
        out = []
        for comp in dyn:
            try:
                pname = (comp.get('part_name') or '').strip()
                qty = int(comp.get('qty') or 0)
                part_id = comp.get('part_id') or comp.get('part_pk') or comp.get('part') or comp.get('id')
                try:
                    part_id = int(part_id)
                except (TypeError, ValueError):
                    part_id = None
            except Exception:
                continue
            if pname and qty > 0:
                out.append({'part_name': pname, 'qty': qty, 'part_id': part_id})
        if out:
            return out
    # Normalized BOM from the DB
    try:
        from inventory.models import ProductComponent
        rows = ProductComponent.objects.filter(product=product).select_related('part')
        return [
            {
                'part_name': r.part.name,
                'qty': int(r.qty),
                'part_id': r.part_id,
            }
            for r in rows
            if r.part_id and r.qty
        ]
    except Exception:
        return []


def get_materials_for_product(product) -> list[dict]:
    """Return a list of {'material_id': int, 'material_name': str, 'qty': Decimal} for product's materials BOM.

    This mirrors get_components_for_product but for materials (ProductMaterial).
    Using a local import avoids circular imports at module import time.
    """
    if product is None:
        return []
    try:
        from inventory.models import ProductMaterial
        rows = ProductMaterial.objects.filter(product=product).select_related('material')
        out = []
        for r in rows:
            try:
                q = Decimal(r.qty)
            except Exception:
                continue
            if r.material_id and q and q > 0:
                out.append({'material_id': r.material_id, 'material_name': getattr(r.material, 'name', ''), 'qty': q})
        return out
    except Exception:
        return []


def today_jdate():
    """
    Return today's Jalali date (date-only).

    Using ``jdatetime.date.today()`` directly can produce an off‑by‑one
    error when the server's system timezone differs from Tehran.  To ensure
    the correct Persian date is returned regardless of server locale, first
    obtain the current date in the application's configured timezone and
    then convert it to Jalali.  The conversion via ``fromgregorian`` yields
    an accurate Jalali date.  If timezone conversion or jdatetime is not
    available at runtime, fallback to the original implementation.
    """
    try:

        from django.utils import timezone as dj_timezone  # Local import to avoid circularities
        g_now = dj_timezone.localtime(dj_timezone.now())
        g_date = g_now.date()
        return jdatetime.date.fromgregorian(date=g_date)
    except Exception:

        try:
            return jdatetime.date.today()
        except Exception:
            # As a last resort, return None so that the default won't break migrations
            return None


# ---------------------------------------------------------------------------
# Basic production_line line model (preserved)
# ---------------------------------------------------------------------------
class ProductionLine(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------
class SectionChoices(models.TextChoices):
    """
    Ordered sections across the production_line line.
    """
    CUTTING       = 'cutting', 'برش'
    CNC_TOOLS     = 'cnc_tools', 'سی‌ان‌سی و ابزار'
    UNDERCOATING  = 'undercoating', 'رنگ زیرکار'
    PAINTING      = 'painting', 'رنگ'
    WORKPAGE      = 'workpage', 'صفحه‌کاری'
    SEWING        = 'sewing', 'خیاطی'
    UPHOLSTERY    = 'upholstery', 'رویه‌کوبی'
    ASSEMBLY      = 'assembly', 'مونتاژ'
    PACKAGING     = 'packaging', 'بسته‌بندی'


ROLE_TO_SECTION = {
    'cutter_master':       SectionChoices.CUTTING,
    'cnc_master':          SectionChoices.CNC_TOOLS,
    'undercoating_master': SectionChoices.UNDERCOATING,
    'painting_master':     SectionChoices.PAINTING,
    'workpage_master':     SectionChoices.WORKPAGE,
    'sewing_master':       SectionChoices.SEWING,
    'upholstery_master':   SectionChoices.UPHOLSTERY,
    'assembly_master':     SectionChoices.ASSEMBLY,
    'packaging_master':    SectionChoices.PACKAGING,
    # 'manager': handled elsewhere
}


# ---------------------------------------------------------------------------
# Product stock across product-based sections (7 columns)
# ---------------------------------------------------------------------------
class ProductStock(models.Model):
    """Per-product stock for the product sections."""
    product = models.OneToOneField('inventory.Product', on_delete=models.CASCADE, related_name='stock')
    stock_workpage = models.IntegerField(default=0, verbose_name="موجودی صفحه‌کاری")
    stock_undercoating = models.IntegerField(default=0, verbose_name="موجودی رنگ زیرکار")
    stock_painting = models.IntegerField(default=0, verbose_name="موجودی رنگ")
    stock_sewing = models.IntegerField(default=0, verbose_name="موجودی خیاطی")
    stock_upholstery = models.IntegerField(default=0, verbose_name="موجودی رویه‌کوبی")
    stock_assembly = models.IntegerField(default=0, verbose_name="موجودی مونتاژ")
    stock_packaging = models.IntegerField(default=0, verbose_name="موجودی بسته‌بندی")
    threshold = models.IntegerField(default=0, blank=True, null=True, verbose_name="حد آستانه")
    description = models.TextField(blank=True, null=True, verbose_name="توضیحات")

    def __str__(self):
        return f"Stock | {self.product}"

# ---------------------------------------------------------------------------
# ProductionLog (the actionable record)
# ---------------------------------------------------------------------------
class ProductionLog(models.Model):
    # Audit/user info (preserved)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='production_logs')
    role = models.CharField(max_length=30)  # snapshot for audit
    model = models.CharField(max_length=50)  # product model name (string snapshot)
    part = models.ForeignKey('inventory.Part', on_delete=models.PROTECT, null=True, blank=True)
    product = models.ForeignKey('inventory.Product', on_delete=models.PROTECT, null=True, blank=True)
    # Point to the relocated ProductionJob model in the ``jobs`` app.
    job = models.ForeignKey('jobs.ProductionJob', on_delete=models.PROTECT, null=True, blank=True)
    produced_qty = models.PositiveIntegerField(default=0)
    scrap_qty = models.PositiveIntegerField(default=0)
    section = models.CharField(max_length=20, choices=SectionChoices.choices)
    is_scrap = models.BooleanField(default=False)
    is_external = models.BooleanField(default=False)
    logged_at = models.DateTimeField(auto_now_add=True)
    jdate = jmodels.jDateField(default=today_jdate)
    note = models.CharField(max_length=200, blank=True, null=True)

    def _product_field_map(self) -> dict:
        """Centralized field map for product stock columns."""
        return {
            SectionChoices.WORKPAGE:     'stock_workpage',
            SectionChoices.UNDERCOATING: 'stock_undercoating',
            SectionChoices.PAINTING:     'stock_painting',
            SectionChoices.SEWING:       'stock_sewing',
            SectionChoices.UPHOLSTERY:   'stock_upholstery',
            SectionChoices.ASSEMBLY:     'stock_assembly',
            SectionChoices.PACKAGING:    'stock_packaging',
        }

    def _resolve_component_part(self, component: dict) -> Part | None:
        """Locate the concrete ``Part`` row for a BOM component."""
        pname = (component.get('part_name') or '').strip()
        if not pname:
            return None

        part_id = component.get('part_id') or component.get('part_pk') or component.get('part')
        try:
            part_id = int(part_id)
        except (TypeError, ValueError):
            part_id = None

        qs = Part.objects.select_for_update()
        if part_id:
            return qs.filter(pk=part_id).first()

        product_model = getattr(self.product, 'product_model', None)
        if product_model:
            return qs.filter(name=pname, product_model=product_model).first()

        return qs.filter(name=pname).first()

    def increment_current(self):
        """
        Increment inventory for the *current* section (default +1 when quantity
        is omitted). No-op if entity/section unsupported.
        """
        produced = int(getattr(self, 'produced_qty', 0) or 0)
        scrap = int(getattr(self, 'scrap_qty', 0) or 0)

        # Part sections
        if self.section in (SectionChoices.CUTTING, SectionChoices.CNC_TOOLS):
            if not self.part:
                return
            if self.section == SectionChoices.CUTTING:
                # Validate that resulting stock does not become negative
                current_cut = int(self.part.stock_cut or 0)
                increment = produced or 1
                projected = current_cut + increment - scrap
                if projected < 0:
                    # Prevent negative inventory and surface a user-facing message
                    raise ValidationError(_('موجودی قطعه کافی نیست'))
                self.part.stock_cut = projected
                self.part.save(update_fields=['stock_cut'])
            else:
                # Increment CNC/Tools stock for parts
                increment = produced or 1
                self.part.stock_cnc_tools = (self.part.stock_cnc_tools or 0) + increment
                self.part.save(update_fields=['stock_cnc_tools'])
            return

        # Product sections
        if not self.product:
            return
        stock, _ = ProductStock.objects.get_or_create(product=self.product)
        fname = self._product_field_map().get(self.section)
        if fname:
            setattr(stock, fname, (getattr(stock, fname, 0) or 0) + 1)
            stock.save(update_fields=[fname])

    def decrement_previous(self):
        """
        Decrement inventory for the *previous* section by -1.
        Uses the job flow to determine the previous section.
        """
        # The "previous" section for the current registration is the
        # job's current_section (i.e. the section that was last ticked).
        # Previously this used get_previous_section(), which returned the
        # section before the job's current_section and therefore decremented
        # the wrong stage. Use the job's current_section value directly.
        prev_section = str(self.job.current_section or '').lower() if self.job else None
        if not prev_section:
            return

        # Assembly is a special case: assembly consumes component parts
        # from Part.stock_cnc_tools according to the product BOM. The
        # assembly handler already performs that consumption and validates
        # availability, so do not additionally decrement the "previous"
        # section when the current log is for assembly.
        if str(self.section) == str(SectionChoices.ASSEMBLY):
            return


        if prev_section in (SectionChoices.CUTTING, SectionChoices.CNC_TOOLS):
            if not self.part:
                return
            if prev_section == SectionChoices.CUTTING:
                current_cut = int(self.part.stock_cut or 0)
                if current_cut < 1:
                    raise ValidationError(_('موجودی قطعه کافی نیست'))
                self.part.stock_cut = current_cut - 1
                self.part.save(update_fields=['stock_cut'])
            else:
                # Decrement CNC/Tools stock for parts
                current_cnc = int(self.part.stock_cnc_tools or 0)
                if current_cnc < 1:
                    raise ValidationError(_('موجودی قطعه کافی نیست'))
                self.part.stock_cnc_tools = current_cnc - 1
                self.part.save(update_fields=['stock_cnc_tools'])
            return


        if not self.product:
            return
        stock, _ = ProductStock.objects.get_or_create(product=self.product)
        fname = self._product_field_map().get(prev_section)
        if fname:
            current_val = int(getattr(stock, fname, 0) or 0)
            if current_val < 1:
                # Product stock insufficient for movement
                raise ValidationError(_('موجودی محصول کافی نیست'))
            setattr(stock, fname, current_val - 1)
            stock.save(update_fields=[fname])

    # -------------------------
    # Core logic
    # -------------------------
    def apply_inventory(self):
        if self.part and not self.product:
            # Determine quantities, defaulting to zero if not provided
            produced = getattr(self, 'produced_qty', 0) or 0
            scrap = getattr(self, 'scrap_qty', 0) or 0
            # Cutting section: add produced to stock_cut
            # CNC section: add produced to stock_cnc and subtract produced from stock_cut
            if self.section == SectionChoices.CUTTING:
                # Validate that resulting stock does not become negative
                current_cut = int(self.part.stock_cut or 0)
                projected = current_cut + int(produced or 0) - int(scrap or 0)
                if projected < 0:
                    # Prevent negative inventory and surface a user-facing message
                    raise ValidationError(_('موجودی قطعه کافی نیست'))
                if produced:
                    self.part.stock_cut = (self.part.stock_cut or 0) + produced
                if scrap:
                    self.part.stock_cut = (self.part.stock_cut or 0) - scrap
                self.part.save(update_fields=['stock_cut'])
            elif self.section == SectionChoices.CNC_TOOLS:
                # Validate available 'stock_cut' before consuming in CNC/Tools
                available_cut = int(self.part.stock_cut or 0)
                will_consume = int(produced or 0) + int(scrap or 0)
                if will_consume > available_cut:
                    # Prevent negative inventory and surface a user-facing message
                    raise ValidationError(_('موجودی قطعه کافی نیست'))
                # Produced pieces move from cutting to CNC/Tools
                if produced:
                    self.part.stock_cnc_tools = (self.part.stock_cnc_tools or 0) + produced
                    self.part.stock_cut = (self.part.stock_cut or 0) - produced
                if scrap:
                    # Scrap quantity always deducted from cutting stock
                    self.part.stock_cut = (self.part.stock_cut or 0) - scrap
                self.part.save(update_fields=['stock_cut', 'stock_cnc_tools'])
            # Part logs do not use jobs; return early
            return

        # -----------------------------------
        # Product-based logs (requires a job)
        # -----------------------------------
        job = self.job
        if not job:
            # If somehow no job is associated with a product log, ignore
            return

        first_entry = not bool(job.current_section)

        # ---------- External (outside frame) ----------
        if self.is_external:
            # Only increment current section; no decrements; no part consumption
            # English: External entries should still honor completion rules when
            # they land on the last allowed section (or packaging as fallback).
            self.increment_current()
            job.current_section = self.section
            job.is_external_entry = True

            # Determine whether this external entry completes the job
            should_close = False
            try:
                allowed = list(getattr(job, 'allowed_sections', []) or [])
                if allowed:
                    ORDER = [
                        SectionChoices.ASSEMBLY,
                        SectionChoices.WORKPAGE,
                        SectionChoices.UNDERCOATING,
                        SectionChoices.PAINTING,
                        SectionChoices.SEWING,
                        SectionChoices.UPHOLSTERY,
                        SectionChoices.PACKAGING,
                    ]
                    allowed_norm = [s for s in ORDER if s in set(str(x).lower() for x in allowed)]
                    last_allowed = allowed_norm[-1] if allowed_norm else None
                    if last_allowed and str(self.section) == last_allowed:
                        should_close = True
            except Exception:
                # Defensive: never break external flow
                should_close = False

            # Fallback: packaging implies completion as before
            if self.section == SectionChoices.PACKAGING:
                should_close = True

            if should_close:
                # English: Close the job; keep job_label unchanged unless it was 'in_progress'.
                if job.status == 'warranty':
                    # Keep label (e.g., 'warranty'), only update status/finished_at
                    job.status = 'repaired'
                else:
                    job.status = 'completed'
                # Only promote label when it is in_progress → completed
                if (job.job_label or '') == 'in_progress' and job.status == 'completed':
                    job.job_label = 'completed'
                job.finished_at = timezone.now()

            job.save(update_fields=['current_section', 'is_external_entry', 'status', 'job_label', 'finished_at'])
            return

        # Identify deposit (امانی) job behavior
        is_deposit = False
        try:
            is_deposit = str(getattr(job, 'job_label', '') or '') == 'deposit'
        except Exception:
            is_deposit = False

        # ---------- Deposit (امانی) movement ----------
        # Rules:
        # - On success: +1 to current section product stock.
        # - And -1 from previous allowed (i.e., previous ticked/current_section) unless this is first entry.
        # - Do NOT consume parts or raw materials at any section.
        # - If marked as scrap: only -1 from previous (unless first), close job; no +1 to current and no consumption.
        if is_deposit:
            # Local helper to decrement previous product section ignoring assembly special-case
            def _dec_prev_product_bucket():
                prev_section = str(job.current_section or '').lower() if job else None
                if not prev_section:
                    return
                if not self.product:
                    return
                stock, _ = ProductStock.objects.get_or_create(product=self.product)
                fname = self._product_field_map().get(prev_section)
                if fname:
                    current_val = int(getattr(stock, fname, 0) or 0)
                    if current_val < 1:
                        raise ValidationError(_('موجودی محصول کافی نیست'))
                    setattr(stock, fname, current_val - 1)
                    stock.save(update_fields=[fname])

            if self.is_scrap:
                # Scrap for deposit: only decrement previous (if any) and close
                if not first_entry:
                    _dec_prev_product_bucket()
                # Close job as scrapped
                job.status = 'scrapped'
                job.finished_at = timezone.now()
                job.current_section = self.section
                job.is_external_entry = False
                try:
                    job.job_label = 'scrapped'
                except Exception:
                    pass
                job.save(update_fields=['status', 'finished_at', 'current_section', 'is_external_entry', 'job_label'])
                return

            # Normal deposit movement: decrement previous (if not first) then increment current; no consumption
            if not first_entry:
                _dec_prev_product_bucket()

            # Increment current section
            self.increment_current()

            # Completion logic: close when reaching last allowed (or packaging fallback)
            should_close = False
            try:
                allowed = list(getattr(job, 'allowed_sections', []) or [])
                if allowed:
                    ORDER = [
                        SectionChoices.ASSEMBLY,
                        SectionChoices.WORKPAGE,
                        SectionChoices.UNDERCOATING,
                        SectionChoices.PAINTING,
                        SectionChoices.SEWING,
                        SectionChoices.UPHOLSTERY,
                        SectionChoices.PACKAGING,
                    ]
                    allowed_norm = [s for s in ORDER if s in set(str(x).lower() for x in allowed)]
                    last_allowed = allowed_norm[-1] if allowed_norm else None
                    if last_allowed and str(self.section) == last_allowed:
                        should_close = True
            except Exception:
                pass
            if self.section == SectionChoices.PACKAGING:
                should_close = True
            if should_close:
                if job.status == 'warranty':
                    job.status = 'repaired'
                else:
                    job.status = 'completed'
                if (job.job_label or '') == 'in_progress' and job.status == 'completed':
                    job.job_label = 'completed'
                job.finished_at = timezone.now()

            job.current_section = self.section
            job.is_external_entry = False
            try:
                if job.status == 'completed' and (job.job_label or '') == 'in_progress':
                    job.job_label = 'completed'
            except Exception:
                pass
            job.save(update_fields=['current_section', 'status', 'finished_at', 'is_external_entry', 'job_label'])
            return

        # ---------- Scrap (waste) ----------
        if self.is_scrap:
            # Product scrap handling depends on the section

            if self.section == SectionChoices.ASSEMBLY:
                # Consume parts from CNC for each component
                components = get_components_for_product(self.product)
                materials = get_materials_for_product(self.product)
                with transaction.atomic():
                    # Consume components (parts)
                    for comp in components:
                        pname = (comp.get('part_name') or '').strip()
                        qty = int(comp.get('qty') or 0)
                        if not pname or qty <= 0:
                            continue
                        part = self._resolve_component_part(comp)
                        if not part:
                            continue
                        current_cnc = int(part.stock_cnc_tools or 0)
                        if current_cnc < qty:
                            # English: Prevent negative inventory of parts
                            raise ValidationError(_('موجودی قطعه کافی نیست'))
                        # Consume parts from CNC/Tools stock when scrapping
                        part.stock_cnc_tools = current_cnc - qty
                        part.save(update_fields=['stock_cnc_tools'])
                    # Consume raw materials
                    if materials:
                        from inventory.models import Material  # Local import to avoid circulars
                        # Lock rows to avoid race on concurrent submissions
                        mat_ids = [m['material_id'] for m in materials]
                        mats = {m.id: m for m in Material.objects.select_for_update().filter(id__in=mat_ids)}
                        for itm in materials:
                            mat = mats.get(itm['material_id'])
                            if not mat:
                                continue
                            req = float(itm['qty'])
                            current = float(mat.quantity or 0)
                            if current < req:
                                # English: Not enough raw material stock
                                raise ValidationError(_('موجودی مواد اولیه کافی نیست'))
                            mat.quantity = current - req
                            mat.save(update_fields=['quantity'])
            else:

                self.decrement_previous()

            # Mark job as scrapped and do not increment current
            job.status = 'scrapped'
            job.finished_at = timezone.now()
            job.current_section = self.section
            job.is_external_entry = False

            try:
                job.job_label = 'scrapped'
            except Exception:
                pass
            job.save(update_fields=['status', 'finished_at', 'current_section', 'is_external_entry', 'job_label'])
            return

        # ---------- Normal movement ----------

        if not first_entry:
            self.decrement_previous()

        # Entering ASSEMBLY for product → consume components and materials (unless external already handled)
        if self.product and self.section == SectionChoices.ASSEMBLY:
            # Skip consumption entirely if marked as external; handled earlier
            if not self.is_external:
                components = get_components_for_product(self.product)
                materials = get_materials_for_product(self.product)
                with transaction.atomic():
                    # Consume components (parts)
                    for comp in components:
                        pname = (comp.get('part_name') or '').strip()
                        qty = int(comp.get('qty') or 0)
                        if not pname or qty <= 0:
                            continue
                        part = self._resolve_component_part(comp)
                        if not part:
                            continue
                        current_cnc = int(part.stock_cnc_tools or 0)
                        if current_cnc < qty:
                            # English: Prevent negative inventory of parts
                            raise ValidationError(_('موجودی قطعه کافی نیست'))
                        part.stock_cnc_tools = current_cnc - qty
                        part.save(update_fields=['stock_cnc_tools'])
                    # Consume raw materials
                    if materials:
                        from inventory.models import Material  # Local import to avoid circulars
                        mat_ids = [m['material_id'] for m in materials]
                        mats = {m.id: m for m in Material.objects.select_for_update().filter(id__in=mat_ids)}
                        for itm in materials:
                            mat = mats.get(itm['material_id'])
                            if not mat:
                                continue
                            req = float(itm['qty'])
                            current = float(mat.quantity or 0)
                            if current < req:
                                raise ValidationError(_('موجودی مواد اولیه کافی نیست'))
                            mat.quantity = current - req
                            mat.save(update_fields=['quantity'])

        # Increment current section
        # In assembly section, do not increment product stock if marked as scrap
        if self.product and self.section == SectionChoices.ASSEMBLY and self.is_scrap:
            pass  # English: for scrap in assembly we only consumed inputs; no output added
        else:
            self.increment_current()

        # Completion rules
        # For products: reaching the last allowed section completes the job.
        # Historically packaging implied completion; we keep that, but also
        # handle custom allowed_sections where the last section may differ.
        if self.product:
            should_close = False
            try:
                allowed = list(getattr(job, 'allowed_sections', []) or [])
                if allowed:
                    # Canonical flow order
                    ORDER = [
                        SectionChoices.ASSEMBLY,
                        SectionChoices.WORKPAGE,
                        SectionChoices.UNDERCOATING,
                        SectionChoices.PAINTING,
                        SectionChoices.SEWING,
                        SectionChoices.UPHOLSTERY,
                        SectionChoices.PACKAGING,
                    ]
                    # Normalize to slugs
                    allowed_norm = [s for s in [
                        'assembly','workpage','undercoating','painting','sewing','upholstery','packaging'
                    ] if s in set(str(x).lower() for x in allowed)]
                    last_allowed = allowed_norm[-1] if allowed_norm else None
                    if last_allowed and str(self.section) == last_allowed:
                        should_close = True
            except Exception:
                pass
            # Fallback: packaging closes as before
            if self.section == SectionChoices.PACKAGING:
                should_close = True

            if should_close:
                # English: Close the job; preserve label unless it was 'in_progress'.
                if job.status == 'warranty':
                    job.status = 'repaired'
                else:
                    job.status = 'completed'
                if (job.job_label or '') == 'in_progress' and job.status == 'completed':
                    job.job_label = 'completed'
                job.finished_at = timezone.now()
        if self.section == SectionChoices.CNC_TOOLS and self.part and not self.product:
            job.status = 'completed'
            job.finished_at = timezone.now()


        job.current_section = self.section
        job.is_external_entry = False

        # 1) Do not change deposit label automatically; keep original labels intact.
        # 2) Sync label minimally: only in_progress → completed on successful completion.
        try:
            if job.status == 'completed' and (job.job_label or '') == 'in_progress':
                job.job_label = 'completed'
        except Exception:
            pass
        job.save(update_fields=['current_section', 'status', 'finished_at', 'is_external_entry', 'job_label'])

        # The generic completion logic above handles warranty via status mapping.

    # ------------------------------------------------------------------
    # Rollback helpers
    # ------------------------------------------------------------------
    def _normalize_section(self, value) -> str | None:
        slug = (str(value or '')).strip().lower()
        return slug or None

    def _adjust_product_stock(self, section_slug: str | None, delta: int):
        if not self.product or not section_slug or not delta:
            return
        stock, _ = ProductStock.objects.get_or_create(product=self.product)
        field = self._product_field_map().get(section_slug)
        if not field:
            return
        current = int(getattr(stock, field, 0) or 0)
        setattr(stock, field, current + delta)
        stock.save(update_fields=[field])

    def _restore_consumed_inputs(self):
        components = get_components_for_product(self.product)
        materials = get_materials_for_product(self.product)
        if not components and not materials:
            return
        with transaction.atomic():
            for comp in components:
                qty = int(comp.get('qty') or 0)
                if qty <= 0:
                    continue
                part = self._resolve_component_part(comp)
                if not part:
                    continue
                part.stock_cnc_tools = (part.stock_cnc_tools or 0) + qty
                part.save(update_fields=['stock_cnc_tools'])
            if materials:
                from inventory.models import Material
                mat_ids = [m.get('material_id') for m in materials if m.get('material_id')]
                mats = {m.id: m for m in Material.objects.select_for_update().filter(id__in=mat_ids)}
                for itm in materials:
                    mat = mats.get(itm.get('material_id'))
                    if not mat:
                        continue
                    try:
                        qty = Decimal(itm.get('qty') or 0)
                    except Exception:
                        continue
                    try:
                        current = Decimal(mat.quantity or 0)
                    except Exception:
                        current = Decimal('0')
                    mat.quantity = current + qty
                    mat.save(update_fields=['quantity'])

    def _reverse_decrement_previous(self, prev_section: str | None):
        prev_section = self._normalize_section(prev_section)
        if not prev_section:
            return
        # Assembly logs never decremented previous stock in apply_inventory
        if self._normalize_section(self.section) == self._normalize_section(SectionChoices.ASSEMBLY):
            return
        if prev_section in (SectionChoices.CUTTING, SectionChoices.CNC_TOOLS):
            if not self.part:
                return
            if prev_section == SectionChoices.CUTTING:
                self.part.stock_cut = (self.part.stock_cut or 0) + 1
                self.part.save(update_fields=['stock_cut'])
            else:
                self.part.stock_cnc_tools = (self.part.stock_cnc_tools or 0) + 1
                self.part.save(update_fields=['stock_cnc_tools'])
            return
        self._adjust_product_stock(prev_section, +1)

    def _reverse_part_log(self):
        if not self.part or self.product:
            return
        produced = int(getattr(self, 'produced_qty', 0) or 0)
        scrap = int(getattr(self, 'scrap_qty', 0) or 0)
        if self.section == SectionChoices.CUTTING:
            if produced:
                self.part.stock_cut = (self.part.stock_cut or 0) - produced
            if scrap:
                self.part.stock_cut = (self.part.stock_cut or 0) + scrap
            self.part.save(update_fields=['stock_cut'])
            return
        if self.section == SectionChoices.CNC_TOOLS:
            if produced:
                self.part.stock_cnc_tools = (self.part.stock_cnc_tools or 0) - produced
                self.part.stock_cut = (self.part.stock_cut or 0) + produced
            if scrap:
                self.part.stock_cut = (self.part.stock_cut or 0) + scrap
            self.part.save(update_fields=['stock_cut', 'stock_cnc_tools'])

    def rollback_inventory(self, prev_section: str | None = None):
        """Undo the inventory movements triggered by this log."""
        # Part-only jobs have isolated stock rules
        if self.part and not self.product:
            self._reverse_part_log()
            return

        job = self.job
        if not job:
            return

        prev_section = self._normalize_section(prev_section)
        first_entry = prev_section is None

        # External entries only incremented the current section
        if self.is_external:
            self._adjust_product_stock(self._normalize_section(self.section), -1)
            return

        job_label = str(getattr(job, 'job_label', '') or '')
        is_deposit = job_label == 'deposit'

        if is_deposit:
            if self.is_scrap:
                if not first_entry:
                    self._adjust_product_stock(prev_section, +1)
                return
            if not first_entry:
                self._adjust_product_stock(prev_section, +1)
            self._adjust_product_stock(self._normalize_section(self.section), -1)
            return

        if self.is_scrap:
            if self.section == SectionChoices.ASSEMBLY:
                self._restore_consumed_inputs()
            else:
                if not first_entry:
                    self._reverse_decrement_previous(prev_section)
            return

        # Normal flow
        if not first_entry:
            self._reverse_decrement_previous(prev_section)

        if self.section == SectionChoices.ASSEMBLY and not self.is_external:
            self._restore_consumed_inputs()

        self._adjust_product_stock(self._normalize_section(self.section), -1)

    # -------------------------
    # Model plumbing
    # -------------------------
    def save(self, *args, **kwargs):
        """
        Persist and then apply inventory side-effects on first creation.
        """
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new:
            # Any exception should bubble up to surface invalid transitions during development.
            self.apply_inventory()

    def __str__(self):
        who = getattr(self.user, 'full_name', None) or getattr(self.user, 'username', '—')
        flags = []
        if self.is_external:
            flags.append('EXT')
        if self.is_scrap:
            flags.append('SCR')
        flag_str = ','.join(flags) if flags else 'OK'
        job_number = self.job.job_number if getattr(self, 'job', None) else '—'
        return f"{self.jdate} | {self.get_section_display()} | {job_number} | {who} | {flag_str}"

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['job', 'section'],
                condition=models.Q(job__isnull=False),
                name='production_log_unique_job_section',
            ),
        ]
