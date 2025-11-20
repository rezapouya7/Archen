
def _normalize_jdate(value):
    """Ensure Jalali date comes back as a pure date object without time.
    If a datetime sneaks in, convert to date to avoid timezone shifts."""
    try:
        import datetime
        if hasattr(value, 'date'):
            return value.date()
        return value
    except Exception:
        return value


def _extract_product_ids(payload):
    """Return a list of product IDs (ints) from the requested_products payload."""
    if not payload:
        return []
    try:
        data = json.loads(payload) if isinstance(payload, str) else payload
    except Exception:
        return []
    if not isinstance(data, dict):
        return []
    output = []
    for key, qty in data.items():
        try:
            qty_int = int(qty)
            if qty_int <= 0:
                continue
            output.append(int(key))
        except Exception:
            continue
    return output

# PATH: /Archen/orders/forms.py
import json
from django import forms
from django.core.exceptions import ValidationError
from django_jalali import forms as jforms
from .models import Order
from .models import OrderItem  
# Import the relocated ProductionJob model from the jobs app.  This
# avoids relying on the fallback import defined in production_line.models.
from jobs.models import ProductionJob
from django.db import models

REQUIRED_MSG_FA = "پر کردن این فیلد الزامی است."
INVALID_MSG_FA = "مقدار وارد شده معتبر نیست."

# Tailwind classes matching the users form look-and-feel
TW_INPUT = (
    "w-full border border-gray-300 rounded px-3 py-2 text-sm "
    "focus:outline-none focus:ring-2 focus:ring-green-600 focus:border-green-600 "
    "bg-white placeholder-gray-400"
)
TW_TEXTAREA = (
    "w-full border border-gray-300 rounded px-3 py-2 text-sm bg-white "
    "focus:outline-none focus:ring-2 focus:ring-green-600 focus:border-green-600"
)
TW_SELECT = (
    "w-full border border-gray-300 rounded px-3 py-2 text-sm bg-white "
    "focus:outline-none focus:ring-2 focus:ring-green-600 focus:border-green-600"
)


COMMON_DATE_ATTRS = {
    "class": f"{TW_INPUT} persian-date-picker",
    "placeholder": "yyyy/mm/dd",
    "autocomplete": "off",
    "dir": "ltr",
    "data-jdp": "true",
}


class RequestedProductsField(forms.Field):
    """Accept JSON like {'<product_id>': <qty>, ...} coming from template JS."""
    def to_python(self, value):
        if not value:
            return {}
        try:
            data = json.loads(value) if isinstance(value, str) else value
        except Exception:
            raise ValidationError(INVALID_MSG_FA)
        if not isinstance(data, dict):
            raise ValidationError(INVALID_MSG_FA)
        out = {}
        for k, v in data.items():
            try:
                pid = int(k)
                qty = int(v)
                if qty > 0:
                    out[pid] = qty
            except Exception:
                continue
        return out


class OrderForm(forms.ModelForm):

    order_date = jforms.jDateField(
        required=True,
        input_formats=["%Y/%m/%d", "%Y-%m-%d"],
        widget=jforms.widgets.jDateInput(attrs=COMMON_DATE_ATTRS),
        label="تاریخ سفارش",
        error_messages={"required": REQUIRED_MSG_FA, "invalid": INVALID_MSG_FA},
    )
    fabric_entry_date = jforms.jDateField(
        required=False,
        input_formats=["%Y/%m/%d", "%Y-%m-%d"],
        widget=jforms.widgets.jDateInput(attrs=COMMON_DATE_ATTRS),
        label="تاریخ ورود پارچه",
        error_messages={"invalid": INVALID_MSG_FA},
    )
    delivery_date = jforms.jDateField(
        required=False,
        input_formats=["%Y/%m/%d", "%Y-%m-%d"],
        widget=jforms.widgets.jDateInput(attrs=COMMON_DATE_ATTRS),
        label="تاریخ تحویل",
        error_messages={"invalid": INVALID_MSG_FA},
    )

    product_models = forms.MultipleChoiceField(
        required=False,
        choices=[],
        widget=forms.MultipleHiddenInput,
        label="مدل",
        error_messages={"required": REQUIRED_MSG_FA},
    )
    requested_products = RequestedProductsField(
        required=False,
        widget=forms.HiddenInput,
        label="محصولات درخواستی",
        error_messages={"required": REQUIRED_MSG_FA},
    )

    # Allow the user to select one or more production jobs to associate with
    # this order.  A job corresponds to a single physical unit that has
    # progressed (or will progress) through the production line.  Only jobs
    # that have not yet been linked to another order are available by
    # default.  The queryset is overridden in the form initializer.  We use
    # a MultipleChoiceField instead of a ModelMultipleChoiceField because
    # choices are rebuilt dynamically based on the current set of jobs.
    job_numbers = forms.MultipleChoiceField(
        required=False,
        choices=[],
        # Use a hidden widget to prevent the default Django rendering of this
        # field.  The UI for selecting jobs is defined manually in the
        # template (see orders_form.html).  Values posted via checkboxes
        # named ``job_numbers`` will populate this field’s cleaned_data.
        widget=forms.MultipleHiddenInput,
        label="شماره کارها",
        help_text="شماره کارهای مرتبط با محصولات انتخاب شده."
    )

    class Meta:
        model = Order
        # Use all model fields plus the two hidden sinks.  QR code is excluded from
        # user input and is displayed separately in the template.
        exclude = ['qr_code']
        labels = {
            # Rename subscription_code → customer subscription code
            "subscription_code": "کد اشتراک مشتری",
            # Rename exhibition_name → store name
            "exhibition_name": "نام فروشگاه",
            # Existing labels
            "customer_name": "نام مشتری",
            "city": "شهر",
            "fabric_description": "توضیح پارچه",
            "fabric_code": "کد پارچه",
            "color_code": "کد رنگ",
            "status": "وضعیت",
            "description": "توضیحات",
            "current_stage": "مرحله فعلی",
            # New field labels
            "badge_number": "شماره بیجک",
            "producer": "تولید کننده",
            "region": "منطقه",
            "customer_phone": "شماره تماس مشتری",
            "driver_phone": "شماره تماس راننده",
            "sender": "ارسال کننده",
            "driver_name": "نام راننده",
        }
        widgets = {
            # Hidden model selection stored here (populated from product_models in save())
            "model": forms.HiddenInput(),
            "subscription_code": forms.TextInput(attrs={"class": TW_INPUT}),
            "badge_number": forms.TextInput(attrs={"class": TW_INPUT}),
            "producer": forms.TextInput(attrs={"class": TW_INPUT}),
            "region": forms.TextInput(attrs={"class": TW_INPUT}),
            "customer_phone": forms.TextInput(attrs={"class": TW_INPUT}),
            "driver_phone": forms.TextInput(attrs={"class": TW_INPUT}),
            "sender": forms.TextInput(attrs={"class": TW_INPUT}),
            "driver_name": forms.TextInput(attrs={"class": TW_INPUT}),
            "exhibition_name": forms.TextInput(attrs={"class": TW_INPUT}),
            "customer_name": forms.TextInput(attrs={"class": TW_INPUT}),
            "city": forms.TextInput(attrs={"class": TW_INPUT}),
            "fabric_description": forms.Textarea(attrs={"class": TW_TEXTAREA, "rows": 2}),
            "fabric_code": forms.TextInput(attrs={"class": TW_INPUT}),
            "color_code": forms.TextInput(attrs={"class": TW_INPUT}),
            "status": forms.Select(attrs={"class": TW_SELECT}),
            "current_stage": forms.Select(attrs={"class": TW_SELECT}),
            "description": forms.Textarea(attrs={"class": TW_TEXTAREA, "rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Ensure the order status dropdown begins with a blank option.  Without
        # this, the first defined status becomes the default, which the user
        # wants to avoid.  Only add the blank if it's not already present.
        if 'status' in self.fields:
            choices = list(self.fields['status'].choices)
            # Typical ModelChoiceField/ChoiceField has a single empty label of '---------'
            # which counts as blank for HTML but still shows English dashes.  Replace
            # that label with a simple space for Persian UI, or insert our own.
            if choices:
                first_value, first_label = choices[0]
                if first_value != '':
                    # Prepend our blank option
                    self.fields['status'].choices = [('', 'انتخاب وضعیت')] + choices
                else:
                    # Replace the default placeholder label with a blank space
                    self.fields['status'].choices = [('', 'انتخاب وضعیت')] + choices[1:]

        # Populate product model choices dynamically
        try:
            from inventory.models import ProductModel
            self.fields['product_models'].choices = [(m.name, m.name) for m in ProductModel.objects.all().order_by('name')]
        except Exception:
            self.fields['product_models'].choices = []

        # Remove region from the form entirely (per new requirement)
        if "region" in self.fields:
            self.fields.pop("region")

        # Enforce required fields as per project needs
        if "subscription_code" in self.fields:
            self.fields["subscription_code"].required = False
        self.fields["customer_name"].required = True
        self.fields["city"].required = True
        self.fields["order_date"].required = True
        # Badge/receipt number must be required
        if "badge_number" in self.fields:
            self.fields["badge_number"].required = True

        # Optional: New fields are not required by default; keep as optional

        # Set clear messages + RTL/LTR
        for name, field in self.fields.items():
            field.error_messages = {
                **getattr(field, "error_messages", {}),
                "required": REQUIRED_MSG_FA,
                "invalid": INVALID_MSG_FA,
            }
            if isinstance(field.widget, forms.NumberInput):
                field.widget.attrs.setdefault("dir", "ltr")
            else:
                field.widget.attrs.setdefault("dir", "rtl")

        # Prefill product_models (edit mode) from comma-separated model
        if self.instance and getattr(self.instance, "model", None):
            tokens = [s.strip() for s in (self.instance.model or "").split(",") if s.strip()]
            valid = {k for k, _ in self.fields["product_models"].choices}
            self.initial["product_models"] = [t for t in tokens if t in valid]

        # Prefill requested_products (edit mode) from existing OrderItem(s)
        if self.instance and getattr(self.instance, "pk", None):
            try:
                items_qs = self.instance.items.select_related("product").all()
            except Exception:
                # fallback if related_name is not 'items'
                items_qs = OrderItem.objects.filter(order=self.instance)
            mapping = {it.product_id: int(it.quantity or 1) for it in items_qs}
            if mapping:
                self.initial["requested_products"] = json.dumps(mapping, ensure_ascii=False)

        # Reorder fields to group related items.  Fields not listed here will
        # retain their default order at the end.  Hidden sinks are not
        # reordered.  This method is idempotent when called multiple times.
        desired_order = [
            'badge_number', 'subscription_code', 'producer',
            'customer_name', 'customer_phone', 'city', 'driver_phone',
            'sender', 'driver_name', 'exhibition_name', 'status',
            'order_date', 'delivery_date', 'fabric_entry_date',
            'fabric_code', 'color_code', 'fabric_description', 'description'
            , 'job_numbers'
        ]

        # ------------------------------------------------------------------
        # Configure available production jobs for selection.
        #
        # A job can only be associated with a single order.  To enforce this
        # constraint, only jobs with ``order`` unset (or jobs that already
        # belong to this order in edit mode) are offered as choices.  Each
        # choice displays the job number along with its related product name
        # and the Persian label for the job's status.  When editing an

        # normally they would be excluded by the ``order__isnull`` filter.
        #
        # The value stored for each choice is the primary key of the
        # ProductionJob.  Downstream logic (in the view) uses these IDs to
        # assign jobs to the order and the corresponding OrderItem.
        try:
            # Determine selected product models from the bound data or initial state
            if self.is_bound:
                selected_models = [m.strip() for m in self.data.getlist('product_models') if m.strip()]
                selected_product_ids = _extract_product_ids(self.data.get('requested_products'))
            else:
                initial_models = self.initial.get('product_models') if isinstance(self.initial, dict) else None
                selected_models = [m.strip() for m in (initial_models or []) if isinstance(m, str) and m.strip()]
                initial_requested = None
                if isinstance(self.initial, dict):
                    initial_requested = self.initial.get('requested_products')
                if not initial_requested and self.instance and getattr(self.instance, 'pk', None):
                    try:
                        items_mapping = {it.product_id: int(it.quantity or 1) for it in self.instance.items.all()}
                        initial_requested = items_mapping
                    except Exception:
                        initial_requested = None
                selected_product_ids = _extract_product_ids(initial_requested)

            # Determine the set of jobs available for selection.  For new
            # orders, include only unassigned jobs; for edits, include
            # unassigned jobs plus jobs already attached to this order.
            base_qs = ProductionJob.objects.select_related('product', 'product__product_model').all()
            if self.instance and getattr(self.instance, 'pk', None):
                # Include jobs already linked to this order as well as
                # unassigned jobs.  We identify already linked jobs via
                # ``order=self.instance``.
                available_jobs = base_qs.filter(
                    models.Q(order__isnull=True) | models.Q(order=self.instance)
                )
            else:
                available_jobs = base_qs.filter(order__isnull=True)

            if selected_models:
                model_filter = models.Q(product__product_model__name__in=selected_models)
                if self.instance and getattr(self.instance, 'pk', None):
                    model_filter |= models.Q(order=self.instance)
                available_jobs = available_jobs.filter(model_filter)

            if selected_product_ids:
                available_jobs = available_jobs.filter(product_id__in=selected_product_ids)
            else:
                if self.instance and getattr(self.instance, 'pk', None):
                    available_jobs = available_jobs.filter(order=self.instance)
                else:
                    available_jobs = available_jobs.none()

            # Build choice tuples: (job.pk, label)
            choices = []
            for job in available_jobs:
                try:
                    prod_name = ''
                    if getattr(job, 'product', None):
                        prod_name = f" - {job.product.name}" if job.product.name else ''
                    # Resolve Persian display for the job label using the
                    # underlying choice definition on the model.
                    label_display = getattr(job, 'get_job_label_display', None)
                    persian_label = label_display() if callable(label_display) else job.job_label
                    # Compose a human readable label.  The color coding is
                    # applied in the template rather than embedding HTML here.
                    label = f"{job.job_number}{prod_name} ({persian_label})"
                    choices.append((str(job.pk), label))
                except Exception:
                    # In case of unexpected attributes, fallback to job_number
                    choices.append((str(job.pk), job.job_number or str(job.pk)))
            # Assign to field
            self.fields['job_numbers'].choices = choices
        except Exception:
            # If ProductionJob cannot be imported or queried, leave empty
            self.fields['job_numbers'].choices = []
        try:
            self.order_fields(desired_order)
        except Exception:
            # If order_fields is not available (Django <1.9), fallback to manual reordering
            from collections import OrderedDict
            new_fields = OrderedDict()
            for key in desired_order:
                if key in self.fields:
                    new_fields[key] = self.fields.pop(key)
            # Append any remaining fields
            for key, val in list(self.fields.items()):
                new_fields[key] = val
            self.fields = new_fields

    def clean_badge_number(self):
        value = self.cleaned_data.get("badge_number")
        if value is None:
            return None
        normalized = str(value).strip()
        if not normalized:
            return None
        qs = Order.objects.filter(badge_number__iexact=normalized)
        if self.instance and getattr(self.instance, "pk", None):
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError("شماره بیجک وارد شده تکراری است. لطفاً شماره دیگری وارد کنید.")
        return normalized

    def clean(self):

        for _field in ('order_date', 'delivery_date', 'fabric_entry_date'):
            if _field in self.data or _field in self.cleaned_data:
                try:
                    self.cleaned_data[_field] = _normalize_jdate(self.cleaned_data.get(_field))
                except Exception:
                    pass

        cleaned = super().clean()
        # Require both sinks (UI fills before submit)
        if not cleaned.get("product_models"):
            self.add_error("product_models", REQUIRED_MSG_FA)
        if not cleaned.get("requested_products"):
            self.add_error("requested_products", REQUIRED_MSG_FA)


        # have not already been assigned to another order.  This check
        # supplements the queryset restriction applied in __init__.  It
        # prevents tampering with the form POST data to select arbitrary jobs.
        jobs_selected = cleaned.get('job_numbers') or []
        selected_model_names = {str(m).strip() for m in (cleaned.get('product_models') or []) if str(m).strip()}
        if jobs_selected:
            # Build a set of allowed product IDs from requested_products
            try:
                req_map = cleaned.get('requested_products') or {}
                allowed_product_ids = {int(pid) for pid in req_map.keys()}
            except Exception:
                allowed_product_ids = set()
            for jid in jobs_selected:
                try:
                    job = ProductionJob.objects.select_related('product', 'product__product_model').get(pk=int(jid))
                except Exception:
                    self.add_error('job_numbers', f"شماره کار نامعتبر: {jid}")
                    continue
                # Ensure the job is either unassigned or belongs to this order
                # on edit.  If assigned to another order, raise error.
                if job.order and job.order != self.instance:
                    self.add_error('job_numbers', f"شماره کار {job.job_number} قبلاً به سفارش دیگری اختصاص یافته است.")
                # Ensure the job's product is one of the requested products
                if job.product_id and allowed_product_ids and job.product_id not in allowed_product_ids:
                    self.add_error('job_numbers', f"شماره کار {job.job_number} به محصولی که انتخاب نکرده‌اید تعلق دارد.")
                if selected_model_names:
                    try:
                        job_model_name = job.product.product_model.name if job.product and job.product.product_model else ''
                    except Exception:
                        job_model_name = ''
                    if not job_model_name or job_model_name not in selected_model_names:
                        self.add_error('job_numbers', f"شماره کار {job.job_number} با مدل‌های انتخاب‌شده همخوانی ندارد.")
        return cleaned

    def save(self, commit=True):
        """Persist selected models into Order.model (comma-separated).
        OrderItems are saved in the view's form_valid, not here."""
        instance = super().save(commit=False)
        models_sel = self.cleaned_data.get("product_models") or []
        instance.model = ", ".join(models_sel)
        if commit:
            instance.save()
        return instance
