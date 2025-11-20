# jobs/forms.py
from django import forms
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from inventory.models import Part, Product
from production_line.models import ProductionLog, SectionChoices
from production_line.utils import (
    get_user_role, role_to_section, is_parts_based, is_products_based,
    product_contains_mdf_page,
)

INPUT_CLS = "block w-full rounded-md border border-gray-300 p-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
SELECT_CLS = "block w-full rounded-md border border-gray-300 p-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"

class WorkEntryForm(forms.ModelForm):
    # === عینِ فرم فعلی شما ===
    model = forms.ChoiceField(
        choices=[('', 'انتخاب مدل')],
        label=_("مدل"),
        widget=forms.Select(attrs={"class": SELECT_CLS, "id": "id_model", "required": "required"}),
    )
    part = forms.ModelChoiceField(
        queryset=Part.objects.none(), required=False, label=_("قطعه"),
        empty_label=" ", widget=forms.Select(attrs={"class": SELECT_CLS, "id": "id_part"}),
    )
    product = forms.ModelChoiceField(
        queryset=Product.objects.none(), required=False, label=_("محصول"),
        empty_label="انتخاب محصول", widget=forms.Select(attrs={"class": SELECT_CLS, "id": "id_product"}),
    )
    produced_qty = forms.IntegerField(
        required=False, min_value=0, initial=0, label=_("تعداد تولید"),
        widget=forms.NumberInput(attrs={"class": INPUT_CLS, "id": "id_produced_qty", "placeholder": "0"}),
    )
    scrap_qty = forms.IntegerField(
        required=False, min_value=0, initial=0, label=_("تعداد ضایعات"),
        widget=forms.NumberInput(attrs={"class": INPUT_CLS, "id": "id_scrap_qty", "placeholder": "0"}),
    )
    job_number = forms.CharField(
        max_length=50, required=False, label=_("شماره کار"),
        error_messages={'required': 'شماره کار الزامی است.'},
        widget=forms.TextInput(attrs={"class": INPUT_CLS, "id": "id_job_number", "list": "job_numbers_datalist"}),
    )
    is_scrap = forms.BooleanField(required=False, label=_("اسقاط"),
        widget=forms.CheckboxInput(attrs={"class": "mr-2", "id": "id_is_scrap"}))
    is_external = forms.BooleanField(required=False, label=_("کلاف بیرون"),
        widget=forms.CheckboxInput(attrs={"class": "mr-2", "id": "id_is_external"}))
    note = forms.CharField(required=False, max_length=200, label=_("توضیحات"),
        widget=forms.Textarea(attrs={"class": INPUT_CLS, "rows": 2}))

    class Meta:
        model = ProductionLog
        fields = ["model","part","product","produced_qty","scrap_qty","job_number","is_scrap","is_external","note"]

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user")
        section_override = kwargs.pop("section_override", None)
        super().__init__(*args, **kwargs)
        role = get_user_role(user)
        section = section_override or role_to_section(role)
        self.user = user
        self.section = section

        # Load ProductModel choices
        try:
            from inventory.models import ProductModel
            models_qs = ProductModel.objects.all().order_by('name')
            self.fields['model'].choices = [('', 'انتخاب مدل')] + [(m.name, m.name) for m in models_qs]
            if not models_qs.exists():
                self.fields['model'].widget.attrs['disabled'] = 'disabled'
        except Exception:
            self.fields['model'].choices = [('', 'انتخاب مدل')]
            self.fields['model'].widget.attrs['disabled'] = 'disabled'

        selected_model = (self.data.get('model') if self.is_bound else self.initial.get('model')) or None

        def expand_part_queryset(qs):
            posted_id = (self.data.get('part') if self.is_bound else self.initial.get('part'))
            if posted_id:
                try:
                    return Part.objects.filter(Q(pk=posted_id) | Q(pk__in=qs.values('pk'))).order_by('name')
                except Exception:
                    return qs
            return qs

        def expand_product_queryset(qs):
            posted_id = (self.data.get('product') if self.is_bound else self.initial.get('product'))
            if posted_id:
                try:
                    return Product.objects.filter(Q(pk=posted_id) | Q(pk__in=qs.values('pk'))).order_by('name')
                except Exception:
                    return qs
            return qs

        if is_parts_based(section):
            qs = Part.objects.none()
            if selected_model:
                qs = Part.objects.filter(product_model__name=selected_model).order_by('name')
            self.fields["part"].queryset = expand_part_queryset(qs)
            try:
                if qs.count() == 0:
                    self.fields["part"].widget.attrs['disabled'] = 'disabled'
                else:
                    self.fields["part"].widget.attrs.pop('disabled', None)
            except Exception:
                pass
            self.fields["product"].widget = forms.HiddenInput()
            self.fields["job_number"].widget = forms.HiddenInput()
            self.fields["is_scrap"].widget = forms.HiddenInput()
            self.fields["is_external"].widget = forms.HiddenInput()
        elif is_products_based(section):
            qs = Product.objects.none()
            if selected_model:
                qs = Product.objects.filter(product_model__name=selected_model).order_by('name')
            self.fields["product"].queryset = expand_product_queryset(qs)
            try:
                if qs.count() == 0:
                    self.fields["product"].widget.attrs['disabled'] = 'disabled'
                else:
                    self.fields["product"].widget.attrs.pop('disabled', None)
            except Exception:
                pass
            self.fields["part"].widget = forms.HiddenInput()
            self.fields["produced_qty"].widget = forms.HiddenInput()
            self.fields["scrap_qty"].widget = forms.HiddenInput()
            self.fields["job_number"].required = True

    def clean(self):
        cleaned = super().clean()
        job_number = cleaned.get("job_number")
        if job_number:
            cleaned["job_number"] = job_number.strip()
        section = getattr(self, 'section', None)
        if is_parts_based(section):
            produced = cleaned.get("produced_qty") or 0
            scrap = cleaned.get("scrap_qty") or 0
            if produced < 0 or scrap < 0:
                raise forms.ValidationError(_("مقادیر تولید یا ضایعات نمی‌تواند منفی باشد."))
            if produced == 0 and scrap == 0:
                raise forms.ValidationError(_("حداقل یکی از تعداد تولید یا ضایعات باید وارد شود."))
            cleaned["job_number"] = None
            cleaned["is_scrap"] = False
            cleaned["is_external"] = False
        if cleaned.get("is_scrap") and cleaned.get("is_external"):
            raise forms.ValidationError(_("نمی‌توانید همزمان ضایعات و کلاف بیرون را انتخاب کنید."))
        return cleaned


class CreateJobForm(forms.Form):
    job_number = forms.CharField(
        label=_("شماره کار"),
        widget=forms.TextInput(attrs={"class": INPUT_CLS, "id": "create_job_number"}),
    )
    model = forms.ChoiceField(
        choices=[('', 'انتخاب مدل')], label=_("مدل"),
        widget=forms.Select(attrs={"class": SELECT_CLS, "id": "create_job_model", "required": "required"}),
    )
    product = forms.ModelChoiceField(
        queryset=Product.objects.none(), required=True, label=_("محصول"),
        widget=forms.Select(attrs={"class": SELECT_CLS, "id": "create_job_product"}),
    )
    PRODUCT_SECTION_CHOICES = [
        (SectionChoices.ASSEMBLY, SectionChoices.ASSEMBLY.label),
        (SectionChoices.WORKPAGE, SectionChoices.WORKPAGE.label),
        (SectionChoices.UNDERCOATING, SectionChoices.UNDERCOATING.label),
        (SectionChoices.PAINTING, SectionChoices.PAINTING.label),
        (SectionChoices.SEWING, SectionChoices.SEWING.label),
        (SectionChoices.UPHOLSTERY, SectionChoices.UPHOLSTERY.label),
        (SectionChoices.PACKAGING, SectionChoices.PACKAGING.label),
    ]
    allowed_sections = forms.MultipleChoiceField(
        choices=PRODUCT_SECTION_CHOICES, label=_("بخش‌های مجاز"),
        widget=forms.CheckboxSelectMultiple, required=True,
    )

    # برچسب‌ها را از مدل jobs بگیریم
    from jobs.models import ProductionJob as _PJ
    job_label = forms.ChoiceField(
        choices=_PJ.LABEL_CHOICES, label=_("برچسب کار"),
        widget=forms.RadioSelect, initial='in_progress'
    )
    deposit_account = forms.CharField(
        required=False, label=_("طرف حساب"),
        widget=forms.TextInput(attrs={"class": INPUT_CLS, "placeholder": "نام طرف حساب", "id": "id_deposit_account"})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        try:
            from inventory.models import ProductModel
            models_qs = ProductModel.objects.all().order_by('name')
            self.fields['model'].choices = [('', 'انتخاب مدل')] + [(m.name, m.name) for m in models_qs]
            if not models_qs.exists():
                self.fields['model'].widget.attrs['disabled'] = 'disabled'
        except Exception:
            self.fields['model'].choices = [('', 'انتخاب مدل')]
            self.fields['model'].widget.attrs['disabled'] = 'disabled'

        selected_model = (self.data.get('model') if self.is_bound else self.initial.get('model')) or None

        def expand_product_queryset(qs):
            posted_id = (self.data.get('product') if self.is_bound else self.initial.get('product'))
            if posted_id:
                try:
                    return Product.objects.filter(Q(pk=posted_id) | Q(pk__in=qs.values('pk'))).order_by('name')
                except Exception:
                    return qs
            return qs

        qs = Product.objects.none()
        if selected_model:
            qs = Product.objects.filter(product_model__name=selected_model).order_by('name')
        self.fields['product'].queryset = expand_product_queryset(qs)
        try:
            if qs.count() == 0:
                self.fields['product'].widget.attrs['disabled'] = 'disabled'
            else:
                self.fields['product'].widget.attrs.pop('disabled', None)
        except Exception:
            pass
        try:
            self.fields['product'].empty_label = 'انتخاب محصول'
        except Exception:
            pass

        job_label_val = None
        try:
            job_label_val = (self.data.get('job_label') if self.is_bound else self.initial.get('job_label'))
        except Exception:
            job_label_val = None
        if job_label_val != 'deposit':
            self.fields['deposit_account'].widget.attrs['disabled'] = 'disabled'
        else:
            self.fields['deposit_account'].widget.attrs.pop('disabled', None)

        # English comment: Intelligent defaults for allowed_sections based on product BOM.
        try:
            from production_line.models import SectionChoices as _SC
            def _infer_defaults(prod: Product | None) -> list[str]:
                if not prod:
                    return []
                has_mdf = product_contains_mdf_page(prod)
                all_sections = [
                    _SC.ASSEMBLY, _SC.WORKPAGE, _SC.UNDERCOATING, _SC.PAINTING,
                    _SC.SEWING, _SC.UPHOLSTERY, _SC.PACKAGING,
                ]
                if has_mdf:
                    return [s for s in map(str, all_sections) if s not in (_SC.SEWING, _SC.UPHOLSTERY)]
                return [s for s in map(str, all_sections) if s != _SC.WORKPAGE]

            # Determine defaults only on initial render, and only when
            # caller has not explicitly provided initial allowed_sections.
            if not self.is_bound and 'allowed_sections' not in (self.initial or {}):
                prod_id = self.initial.get('product')
                defaults: list[str] = []
                try:
                    if prod_id:
                        prod_obj = Product.objects.get(pk=prod_id)
                        defaults = _infer_defaults(prod_obj)
                except Exception:
                    defaults = []
                # If job label is not 'in_progress', start with no ticks (user may change).
                if (job_label_val or '') != 'in_progress':
                    defaults = []
                self.initial['allowed_sections'] = defaults
        except Exception:
            pass

    def clean_allowed_sections(self):
        allowed = self.cleaned_data.get('allowed_sections') or []
        valid = {k for k, _ in self.PRODUCT_SECTION_CHOICES}
        for sec in allowed:
            if sec not in valid:
                raise forms.ValidationError(_("انتخاب بخش نامعتبر است."))
        if not allowed:
            raise forms.ValidationError(_("حداقل یک بخش باید انتخاب شود."))
        return allowed

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('job_label') == 'deposit' and not (cleaned.get('deposit_account') or '').strip():
            self.add_error('deposit_account', _("وارد کردن طرف حساب برای امانی الزامی است."))
        return cleaned
