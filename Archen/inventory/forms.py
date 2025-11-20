# PATH: /Archen/inventory/forms.py
# -*- coding: utf-8 -*-
from django import forms
from django.core.exceptions import ValidationError
from .models import Part, Material
# Import Product and ProductModel from the local inventory models instead of the removed
# products app.  ProductModel is defined in inventory.models and exposes the
# same fields as the former products.models.ProductModel.  Importing it here
# ensures that forms continue to work without any dependency on the removed
# products application.
from .models import Product, ProductModel


# -----------------------------
# Base CSS classes reused across forms (similar to user forms)
# -----------------------------
BASE_INPUT_CLASSES = (
    "w-full border border-gray-300 rounded-md px-3 py-2 text-sm "
    "focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent "
    "bg-white placeholder-gray-400"
)
BASE_SELECT_CLASSES = (
    "w-full border border-gray-300 rounded-md px-3 py-2 text-sm bg-white "
    "focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
)
BASE_TEXTAREA_CLASSES = (
    "w-full border border-gray-300 rounded-md px-3 py-2 text-sm bg-white "
    "focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent min-h-[120px]"
)
BASE_NUMBER_CLASSES = BASE_INPUT_CLASSES + " text-left ltr"

REQUIRED_MSG_FA = "پر کردن این فیلد الزامی است."
INVALID_MSG_FA  = "مقدار وارد شده معتبر نیست."


class BaseFormStyleMixin:
    """Apply uniform styles + Persian error messages + HTML5 required on required fields."""

    def _set_widget_classes(self, widget: forms.Widget, classes: str):
        prev = widget.attrs.get("class", "")
        widget.attrs["class"] = (prev + " " + classes).strip()

    def _style_fields(self):
        for name, field in self.fields.items():
            # Persian error messages
            field.error_messages = {
                **field.error_messages,
                "required": REQUIRED_MSG_FA,
                "invalid": INVALID_MSG_FA,
                # Ensure choice fields show Persian message for invalid options
                "invalid_choice": "گزینه انتخاب‌شده معتبر نیست.",
            }

            w = field.widget
            if isinstance(w, forms.NumberInput):
                self._set_widget_classes(w, BASE_NUMBER_CLASSES)
                w.attrs.setdefault("dir", "ltr")
            elif isinstance(w, (forms.Select, forms.SelectMultiple)):
                self._set_widget_classes(w, BASE_SELECT_CLASSES)
                w.attrs.setdefault("dir", "rtl")
            elif isinstance(w, forms.Textarea):
                self._set_widget_classes(w, BASE_TEXTAREA_CLASSES)
                w.attrs.setdefault("dir", "rtl")
            else:
                self._set_widget_classes(w, BASE_INPUT_CLASSES)
                w.attrs.setdefault("dir", "rtl")

            # Add a11y hints only; avoid native browser required popups
            # Use aria-required for screen readers but do not set HTML5 required.
            if field.required:
                w.attrs["aria-required"] = "true"
            # Ensure no HTML 'required' attribute remains to keep Persian server-side errors unified
            w.attrs.pop("required", None)

            w.attrs.setdefault("aria-label", field.label or name)

            # If bound with errors, append error ring and aria-invalid for consistency with users app
            if getattr(self, 'is_bound', False) and name in getattr(self, 'errors', {}):
                prev_cls = w.attrs.get("class", "")
                w.attrs["class"] = (prev_cls + " ring-1 ring-red-500 focus:ring-red-300").strip()
                w.attrs["aria-invalid"] = "true"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()


# =========================================================
#                       PartForm (Part)
# =========================================================
class PartForm(BaseFormStyleMixin, forms.ModelForm):
    class Meta:
        model = Part
        fields = ["name", "product_model", "threshold", "stock_cut", "stock_cnc_tools"]
        labels = {
            "name": "نام قطعه",
            "product_model": "مدل",
            "threshold": "آستانه هشدار",
            "stock_cut": "موجودی برش",
            "stock_cnc_tools": "موجودی سی‌ان‌سی و ابزار",
        }
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "مثلاً: بدنه کشو ۴۵"}),
            "product_model": forms.Select(),
            # allow negative values for stock fields by omitting the min attribute
            "stock_cut": forms.NumberInput(attrs={"placeholder": "0", "inputmode": "numeric"}),
            "stock_cnc_tools": forms.NumberInput(attrs={"placeholder": "0", "inputmode": "numeric"}),
        }

    def __init__(self, *args, **kwargs) -> None:
        """
        Initialise the ``PartForm`` with dynamic model choices and sensible defaults.

        On creation, the model dropdown should show a placeholder labelled
        "انتخاب مدل" and be disabled if there are no models.  On edit, the
        selected model is retained and no empty option is displayed.  The
        threshold and stock fields remain optional.
        """
        super().__init__(*args, **kwargs)
        # Make threshold and stock fields optional
        for fname in ("threshold", "stock_cut", "stock_cnc_tools"):
            if fname in self.fields:
                self.fields[fname].required = False

        # Configure the product_model selector
        model_field = self.fields.get('product_model')
        if model_field:
            try:
                models_qs = ProductModel.objects.all().order_by('name')
                # Use PK for the option value and model name for the label
                model_choices = [(m.pk, m.name) for m in models_qs]
            except Exception:
                models_qs = []
                model_choices = []

            editing = bool(getattr(self.instance, 'pk', None))
            if editing:
                # In edit mode show only existing models
                model_field.choices = model_choices
                model_field.widget.choices = model_choices
                model_field.empty_label = None
                try:
                    # Preselect by primary key to match choice values
                    current = getattr(self.instance.product_model, 'pk', None)
                    if current:
                        self.initial['product_model'] = current
                except Exception:
                    pass
            else:
                # In create mode prepend a descriptive placeholder
                placeholder = [('', 'انتخاب مدل')]
                model_field.choices = placeholder + model_choices
                model_field.widget.choices = placeholder + model_choices
                model_field.empty_label = 'انتخاب مدل'

            # Rely on default PK-based lookup
            model_field.to_field_name = None
            # Disable the selector if no choices exist
            if not model_choices:
                model_field.widget.attrs['disabled'] = 'disabled'

    # Remove explicit negative validation to allow stock values to go negative.
    # Negative values are intentionally permitted to represent backorders or deficits.

    def clean_stock_cut(self):
        return self.cleaned_data.get("stock_cut")

    def clean_stock_cnc_tools(self):
        return self.cleaned_data.get("stock_cnc_tools")


# =========================================================
#                   MaterialForm (raw materials)
# =========================================================
class MaterialForm(BaseFormStyleMixin, forms.ModelForm):
    """
    - Only 'name' is required.
    - Unit as dropdown with an empty placeholder (does not constrain model CharField).
    """
    UNIT_CHOICES = [
        ("کیلوگرم", "کیلوگرم"),
        ("گرم", "گرم"),
        ("متر", "متر"),
        ("سانتی‌متر", "سانتی‌متر"),
        ("میلیمتر", "میلیمتر"),
        ("لیتر", "لیتر"),
        ("میلی‌لیتر", "میلی‌لیتر"),
        ("عدد", "عدد"),
        ("بسته", "بسته"),
        ("جعبه", "جعبه"),
    ]

    # Provide a blank default option for the unit selector.  A single space
    # renders as an empty visual choice instead of the descriptive label.
    unit = forms.ChoiceField(
        choices=[("", " ")] + UNIT_CHOICES,
        required=False,
        label="واحد",
        widget=forms.Select()
    )

    class Meta:
        model = Material
        fields = ["name", "quantity", "unit", "threshold", "supplier", "price"]
        labels = {
            "name": "نام ماده اولیه",
            "quantity": "مقدار",
            "unit": "واحد",
            "threshold": "حد آستانه موجودی",
            "supplier": "تأمین‌کننده",
            "price": "قیمت(تومان)",
        }
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "مثلاً: MDF 16mm"}),
            # Use a concrete decimal step so spinners/stepUp work reliably
            # and change by one decimal unit per click.
            "quantity": forms.NumberInput(attrs={"min": 0, "step": "0.1", "placeholder": "0", "inputmode": "decimal"}),
            "threshold": forms.NumberInput(attrs={"min": 0, "step": "0.1", "placeholder": "0", "inputmode": "decimal"}),
            "supplier": forms.TextInput(attrs={"placeholder": "نام یا شرکت تأمین‌کننده"}),
            "price": forms.NumberInput(attrs={"min": 0, "step": "0.01", "placeholder": "0", "inputmode": "decimal"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["name"].required = True
        for f in ("quantity", "threshold", "supplier", "price"):
            if f in self.fields:
                self.fields[f].required = False
        # Set a blank placeholder attribute for the unit select.  This value is used
        # by select2 and similar libraries; a space ensures the element renders
        # without visible text when empty.
        self.fields["unit"].widget.attrs.setdefault("data-placeholder", " ")

    def clean_quantity(self):
        v = self.cleaned_data.get("quantity")
        if v is not None and v < 0:
            raise ValidationError("مقدار نمی‌تواند منفی باشد.")
        return v

    def clean_threshold(self):
        v = self.cleaned_data.get("threshold")
        if v is not None and v < 0:
            raise ValidationError("حد آستانه موجودی نمی‌تواند منفی باشد.")
        return v

    def clean_price(self):
        v = self.cleaned_data.get("price")
        if v is not None and v < 0:
            raise ValidationError("قیمت نمی‌تواند منفی باشد.")
        return v


# =========================================================
#           NEW: ProductStockEditForm (threshold & description)
# =========================================================
class ProductStockEditForm(forms.ModelForm):
    """Minimal edit form for ProductStock (threshold & description only)."""
    class Meta:
        from production_line.models import ProductStock  # local import to avoid circular import at module import-time
        model = ProductStock
        fields = ["threshold", "description"]
        labels = {"threshold": "حد آستانه", "description": "توضیحات"}
        widgets = {
            "threshold": forms.NumberInput(attrs={"min": 0, "class": BASE_NUMBER_CLASSES, "placeholder": "مثلاً: 10"}),
            "description": forms.Textarea(attrs={"class": BASE_TEXTAREA_CLASSES, "rows": 3, "placeholder": "توضیحات"}),
        }

class ProductModelForm(BaseFormStyleMixin, forms.ModelForm):
    """Form for creating and editing ``ProductModel`` instances."""

    class Meta:
        model = ProductModel
        fields = ['name', 'description']
        labels = {
            'name': 'نام مدل',
            'description': 'توضیحات',
        }
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'مثلاً: رستا'}),
            'description': forms.Textarea(attrs={'rows': 3}),
        }

    def clean_name(self):
        name = (self.cleaned_data.get('name') or '').strip()
        if not name:
            raise forms.ValidationError('نام مدل نمی‌تواند خالی باشد.')
        return name


class PartConfigForm(BaseFormStyleMixin, forms.ModelForm):

    class Meta:
        model = Part
        fields = ['name', 'product_model', 'threshold', 'description']
        labels = {
            'name': 'نام قطعه',
            'product_model': 'مدل',
            'threshold': 'آستانه هشدار',
            'description': 'توضیحات',
        }
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'مثلاً: بدنه کشو'}),
            'product_model': forms.Select(),
            'threshold': forms.NumberInput(attrs={'min': 0, 'step': 1, 'placeholder': '0', 'inputmode': 'numeric'}),
            'description': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs) -> None:
        """
        Initialise the ``PartConfigForm`` with dynamic model choices and sensible defaults.

        Similar to ``PartForm``, the model selector displays a placeholder when
        creating a new part configuration and is disabled if there are no
        product models.  When editing, the current model is preselected.
        The threshold and description fields remain optional.
        """
        super().__init__(*args, **kwargs)
        # Mark threshold and description fields as non-required
        if 'threshold' in self.fields:
            self.fields['threshold'].required = False
        if 'description' in self.fields:
            self.fields['description'].required = False

        model_field = self.fields.get('product_model')
        if model_field:
            try:
                models_qs = ProductModel.objects.all().order_by('name')
                # Use PK for the option value and name for the label
                model_choices = [(m.pk, m.name) for m in models_qs]
            except Exception:
                models_qs = []
                model_choices = []

            editing = bool(getattr(self.instance, 'pk', None))
            if editing:
                model_field.choices = model_choices
                model_field.widget.choices = model_choices
                model_field.empty_label = None
                try:
                    current = getattr(self.instance.product_model, 'pk', None)
                    if current:
                        self.initial['product_model'] = current
                except Exception:
                    pass
            else:
                placeholder = [('', 'انتخاب مدل')]
                model_field.choices = placeholder + model_choices
                model_field.widget.choices = placeholder + model_choices
                model_field.empty_label = 'انتخاب مدل'

            # PK-based lookup
            model_field.to_field_name = None
            if not model_choices:
                model_field.widget.attrs['disabled'] = 'disabled'

    def clean_name(self):
        name = (self.cleaned_data.get('name') or '').strip()
        if not name:
            raise forms.ValidationError('نام قطعه نمی‌تواند خالی باشد.')
        return name

    def clean_threshold(self):
        """Ensure the threshold is a non‑negative integer or None."""
        value = self.cleaned_data.get('threshold')
        if value is None:
            return 0  # treat empty as zero
        try:
            ivalue = int(value)
        except (TypeError, ValueError):
            raise forms.ValidationError('آستانه هشدار باید یک عدد صحیح باشد.')
        if ivalue < 0:
            raise forms.ValidationError('آستانه هشدار نمی‌تواند منفی باشد.')
        return ivalue

__all__ = ["PartForm", "MaterialForm", "ProductStockEditForm", "ProductModelForm"]

# =========================================================
#                    ProductForm (product)
# =========================================================
# The ``ProductForm`` was originally defined in the removed ``products`` app.  To
# continue supporting product CRUD operations within the inventory namespace,
# we reproduce the form here.  It uses Tailwind‑compatible widgets and
# integrates with ProductModel to populate the ``product_model`` choices.  The

# ``materials_json``) for client‑side Bill of Materials editing; those fields
# have been removed.  BOM management is now handled via the ``ProductComponent``
# and ``ProductMaterial`` models and should be performed through the admin or
# dedicated interfaces.
class ProductForm(BaseFormStyleMixin, forms.ModelForm):
    """
    Standardised product form aligned with the users app form UX.  This form
    mirrors the original ``products.forms.ProductForm`` definition but
    omits the hidden JSON fields used for Bill of Materials editing.  The
    ``product_model`` choices are loaded dynamically from ``ProductModel``.
    """

    class Meta:
        model = Product
        fields = ['name', 'product_model', 'description']
        labels = {
            'name': 'نام محصول',
            'product_model': 'مدل',
            'description': 'توضیحات',
        }
        widgets = {
            # Text input styled consistently with other forms
            'name': forms.TextInput(attrs={
                'class': 'w-full border border-gray-300 p-2 rounded text-sm',
                'placeholder': 'مثلاً: مبل ال کلاسیک',
                'autocomplete': 'off',
            }),
            # Select with consistent styling
            'product_model': forms.Select(attrs={
                'class': 'w-full border border-gray-300 p-2 rounded text-sm bg-white',
            }),
            # Textarea for optional description
            'description': forms.Textarea(attrs={
                'class': 'w-full border border-gray-300 p-2 rounded text-sm',
                'rows': 4,
            }),
        }

    # ------------------------------------------------------------------
    # Additional fields not mapped to the Product model
    #
    # ``threshold`` allows the user to specify a per‑product stock warning
    # threshold when creating or editing a product.  This value is stored
    # on the related ProductStock instance (via the view) rather than on
    # the Product itself.  The field is optional and defaults to 0.
    threshold = forms.IntegerField(
        required=False,
        min_value=0,
        label='آستانه هشدار',
        widget=forms.NumberInput(attrs={
            'class': 'w-full border border-gray-300 p-2 rounded text-sm',
            'placeholder': 'مثلاً: 10',
        }),
    )

    def __init__(self, *args, **kwargs) -> None:
        """
        Initialise the ``ProductForm`` with dynamic model choices and proper defaults.

        When creating a new product, a placeholder labelled ``انتخاب مدل`` is
        presented and the selector is disabled if there are no models.  When
        editing an existing product, the current model is preselected and
        no blank option is shown.  This logic mirrors the behaviour in
        ``PartForm`` so that products and parts handle models consistently.
        """
        super().__init__(*args, **kwargs)
        # Determine whether we are editing an existing product (instance has pk)
        editing = bool(getattr(self.instance, 'pk', None))

        # Configure the product_model selector to use model names as option values.
        model_field = self.fields.get('product_model')
        if model_field:
            try:
                # Build a list of (value, label) tuples using the ProductModel.name for both.
                models_qs = ProductModel.objects.all().order_by('id')
                model_choices = [(m.pk, m.name) for m in models_qs]
            except Exception:
                models_qs = []
                model_choices = []

            if editing:
                # In edit mode, show all available models without a placeholder and preselect
                # the current model by its name.  This ensures the value in the select
                # corresponds to the model name used by client‑side code to index
                # parts_by_model.
                model_field.choices = model_choices
                model_field.widget.choices = model_choices
                model_field.empty_label = None
                try:
                    current = getattr(self.instance.product_model, 'pk', None)
                    if current:
                        self.initial['product_model'] = current
                except Exception:
                    pass
            else:
                # In create mode, add a descriptive placeholder option.
                placeholder = [('', 'انتخاب مدل')]
                model_field.choices = placeholder + model_choices
                model_field.widget.choices = placeholder + model_choices
                model_field.empty_label = 'انتخاب مدل'

            # Use the model name as the field value instead of the primary key.  Django will
            # resolve the name back to a ProductModel instance via the to_field_name.
            model_field.to_field_name = None
            # Disable the selector if there are no models available
            if not model_choices:
                model_field.widget.attrs['disabled'] = 'disabled'
            else:
                model_field.widget.attrs.pop('disabled', None)

        # Set the initial threshold value.  When editing, read from the related ProductStock;
        # otherwise default to zero.  Any failures fall back to zero.
        if 'threshold' in self.fields:
            try:
                from production_line.models import ProductStock  # local import to avoid circular dependency
                if editing:
                    stock = getattr(self.instance, 'stock', None)
                    if isinstance(stock, ProductStock):
                        self.fields['threshold'].initial = stock.threshold or 0
                    else:
                        self.fields['threshold'].initial = 0
                else:
                    self.fields['threshold'].initial = 0
            except Exception:
                self.fields['threshold'].initial = 0

    # --- Bill of Materials helper fields ---
    #
    # To support client‑side editing of a product's bill of materials directly
    # from the product create/edit form, we expose two hidden fields that
    # capture the user‑selected parts (components) and raw materials in JSON
    # format.  Each field stores a JSON array of objects; for components
    # objects contain ``part_id`` and ``qty`` (an integer), and for materials
    # they contain ``material_id`` and ``qty`` (a number that may be
    # fractional).  These fields are not mapped to any model fields and
    # therefore must be handled explicitly in the view when saving a product.
    components_data = forms.CharField(
        required=False,
        widget=forms.HiddenInput,
        label=""  # hidden fields do not need labels
    )
    materials_data = forms.CharField(
        required=False,
        widget=forms.HiddenInput,
        label=""
    )


    def clean_name(self):
        """
        Normalize the product name by stripping leading/trailing whitespace.
        The field is optional and therefore may be blank; in that case an
        empty string is returned.
        """
        name = (self.cleaned_data.get('name') or '').strip()
        return name

    def clean(self):
        """
        Perform cross‑field validation to ensure that the product name is only
        unique within the context of its associated product model.

        Historically the ``Product.name`` field was marked as unique, which
        prevented adding a product with the same name to a different model.
        That constraint has been relaxed on the model; however, we still need
        to prevent duplicate names *within* the same model.  This method
        checks whether another product with the same name and model already
        exists and raises a Persian validation error if so.  When editing an
        existing product, the current instance is excluded from the check.
        """
        cleaned_data = super().clean()
        name = cleaned_data.get('name')
        product_model = cleaned_data.get('product_model')
        # Only validate when both fields are present
        if name and product_model:
            try:
                qs = Product.objects.filter(name=name, product_model=product_model)
                # Exclude the current instance to allow saving unchanged objects
                if getattr(self.instance, 'pk', None):
                    qs = qs.exclude(pk=self.instance.pk)
                if qs.exists():
                    # Attach the error to the name field so that it shows up next to it
                    self.add_error('name', forms.ValidationError(
                        'محصول دیگری با این نام و مدل قبلاً ثبت شده است.', code='unique'))
            except Exception:
                # If the database is unreachable or other errors occur, skip the check.
                pass
        return cleaned_data

    def save(self, commit: bool = True):
        """
        Persist the Product instance without any embedded BOM data.

        Previous implementations stored a product’s bill of materials in
        hidden JSON fields on the form (``components_json`` and
        ``materials_json``).  With the new schema, the BOM is
        represented via the ``ProductComponent`` and ``ProductMaterial``
        models and should be managed separately (e.g. via the admin).
        This save method therefore simply delegates to the parent class.
        """
        return super().save(commit=commit)

# Expose ProductForm through __all__ so it can be imported via inventory.forms.ProductForm
__all__.append("ProductForm")
