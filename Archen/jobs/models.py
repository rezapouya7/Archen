"""Models for the jobs app.

This module defines the ``ProductionJob`` model which was previously
part of the ``production_line`` app.  The model is copied here to
encapsulate job management under a dedicated namespace.  The database
table name is preserved via ``db_table`` so that existing data is
retained without requiring a migration.
"""

from __future__ import annotations

from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from inventory.models import Product, Part
from orders.models import Order, OrderItem
from production_line.models import SectionChoices


class ProductionJob(models.Model):
    """Represents a numbered unit moving through the production process.

    A ``ProductionJob`` may correspond to either a finished product or
    a loose part being manufactured.  Each job tracks its current
    section, status, label, deposit account, allowed sections and
    whether it is the current default job for quick work entry.  The
    model exposes helper methods to derive the process flow and
    identify the previous section based on the job's configuration.
    """

    STATUS_CHOICES = [
        ('in_progress', 'در حال ساخت'),
        ('completed',   'تولید شده'),
        ('scrapped',    'اسقاط'),
        ('warranty',    'گارانتی'),
        ('repaired',    'تعمیرات'),
        ('deposit',     'امانی'),
    ]

    # Additional label for jobs.  This field tracks the human‑visible tag
    # assigned when the job is created.  It persists separately from the
    # status so that a job may be marked as "امانی" (deposit) before work

    # (e.g. to "در حال ساخت", "تولید شده", "اسقاط", etc.).
    LABEL_CHOICES = [
        ('in_progress', 'در حال ساخت'),
        ('completed',   'تولید شده'),
        ('scrapped',    'اسقاط'),
        ('warranty',    'گارانتی'),
        ('repaired',    'تعمیرات'),
        ('deposit',     'امانی'),
    ]

    # Core fields
    job_number = models.CharField(max_length=50, unique=True)
    product = models.ForeignKey(Product, on_delete=models.PROTECT, null=True, blank=True)
    part = models.ForeignKey(Part, on_delete=models.PROTECT, null=True, blank=True)
    order = models.ForeignKey(Order, on_delete=models.SET_NULL, null=True, blank=True, related_name='jobs')
    order_item = models.ForeignKey(OrderItem, on_delete=models.SET_NULL, null=True, blank=True, related_name='jobs')
    current_section = models.CharField(max_length=20, choices=SectionChoices.choices, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='in_progress')
    job_label = models.CharField(max_length=20, choices=LABEL_CHOICES, default='in_progress')
    deposit_account = models.CharField(max_length=100, blank=True, null=True)
    is_external_entry = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    allowed_sections = models.JSONField(default=list, blank=True)
    is_default = models.BooleanField(default=False)

    def __str__(self) -> str:
        return f"Job {self.job_number} ({self.get_status_display()})"

    # ------------------------------------------------------------------
    # Process flow helpers
    # ------------------------------------------------------------------
    def get_process_flow(self) -> list[str]:
        """Return the ordered list of sections this job should traverse.

        When the job is associated with a loose part (no product) the
        flow is simply cutting → cnc_tools.  For product jobs the flow
        is either driven by the related ``ProductModel``'s process flow
        attribute or derived from the product's components.  If no
        information is available, an empty list is returned.
        """
        # Part-only jobs have a two‑step flow.
        if self.part and not self.product:
            return ['cutting', 'cnc_tools']

        # Product flow (dynamic if available)
        if self.product:
            try:
                pm = getattr(self.product, 'product_model', None)
                if pm and getattr(pm, 'process_flow', None):
                    return [str(x).lower() for x in (pm.process_flow or [])]
            except Exception:
                # If any error occurs reading process_flow, fall through to component‑based logic
                pass

            # Derive flow from components: check for pages/MDF to decide path
            include_workpage = False
            try:
                comps = (self.product.components or [])
                for c in comps:
                    n = (c.get('part_name') or '').lower()
                    if 'mdf' in n or 'صفحه' in n or 'page' in n:
                        include_workpage = True
                        break
            except Exception:
                include_workpage = False

            if include_workpage:
                # Flow for products requiring workpage
                return ['cutting', 'cnc_tools', 'assembly', 'workpage', 'undercoating', 'painting', 'packaging']
            else:
                # Flow for products without workpage step
                return ['cutting', 'cnc_tools', 'assembly', 'undercoating', 'painting', 'sewing', 'upholstery', 'packaging']

        # Unknown case: defensive default
        return []

    def get_previous_section(self) -> str | None:
        """Return the previous section in the job's process flow.

        If the current section is not set or is not part of the flow
        then ``None`` is returned.  Otherwise the section immediately
        preceding the current section in the flow is returned, or ``None``
        when the job is at the first step.
        """
        flow = self.get_process_flow()
        current = str(self.current_section or '').lower()
        if not current:
            return None
        try:
            idx = flow.index(current)
            return flow[idx - 1] if idx > 0 else None
        except ValueError:
            return None

    class Meta:
        verbose_name = 'Production Job'
        verbose_name_plural = 'Production Jobs'


# ----------------------------------------------------------------------------
# Signals to apply label side-effects on job creation
# ----------------------------------------------------------------------------
@receiver(post_save, sender='jobs.ProductionJob')
def apply_label_side_effects(sender, instance, created, **kwargs):
    """Apply stock movements on creation for deposit/scrapped/completed labels.

    - deposit (امانی): closed; add 1 to the single allowed section.
    - scrapped (اسقاط): closed; remove 1 from previous allowed section.
    - completed (تولید شده): closed; add 1 to packaging and -1 from previous.
    """
    try:
        job = instance
        if not created:
            return
        label = str(getattr(job, 'job_label', '') or '')
        allowed = list(getattr(job, 'allowed_sections', []) or [])
        # Only act if a product job and allowed sections is a non-empty list
        if not job.product_id:
            return
        from production_line.models import ProductStock, SectionChoices
        stock, _ = ProductStock.objects.get_or_create(product=job.product)

        def _field_for(section_slug: str) -> str | None:
            mapping = {
                'assembly': 'stock_assembly',
                'workpage': 'stock_workpage',
                'undercoating': 'stock_undercoating',
                'painting': 'stock_painting',
                'sewing': 'stock_sewing',
                'upholstery': 'stock_upholstery',
                'packaging': 'stock_packaging',
            }
            return mapping.get((section_slug or '').lower())

        if label == 'deposit':
            # Closed deposit: add to the single allowed section
            if len(allowed) == 1:
                fname = _field_for(allowed[0])
                if fname:
                    setattr(stock, fname, (getattr(stock, fname, 0) or 0) + 1)
                    stock.save(update_fields=[fname])
                    job.status = 'in_progress'  # label dictates closure but status remains traceable
                    job.finished_at = timezone.now()
                    job.save(update_fields=['status', 'finished_at'])
            return

        if label == 'scrapped':
            # Remove from previous allowed section (if any)
            if len(allowed) >= 1:
                prev = allowed[-1] if len(allowed) == 1 else allowed[-2]
                fname = _field_for(prev)
                if fname:
                    setattr(stock, fname, (getattr(stock, fname, 0) or 0) - 1)
                    stock.save(update_fields=[fname])
                    job.status = 'scrapped'
                    job.finished_at = timezone.now()
                    job.save(update_fields=['status', 'finished_at'])
            return

        if label == 'completed':
            # Add to packaging and subtract from previous allowed (if present)
            fname_pack = _field_for('packaging')
            if fname_pack:
                setattr(stock, fname_pack, (getattr(stock, fname_pack, 0) or 0) + 1)
            prev = allowed[-1] if allowed else job.current_section
            prev_fname = _field_for(prev) if prev else None
            if prev_fname and prev_fname != fname_pack:
                setattr(stock, prev_fname, (getattr(stock, prev_fname, 0) or 0) - 1)
            stock.save(update_fields=[fn for fn in [fname_pack, prev_fname] if fn])
            job.status = 'completed'
            job.finished_at = timezone.now()
            job.save(update_fields=['status', 'finished_at'])
            return
    except Exception:
        # Fail-safe: never break job creation
        pass
