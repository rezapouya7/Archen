# production_line/forms.py
from django import forms
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from inventory.models import Part, Product
from .models import ProductionLog, SectionChoices
from .utils import (
    get_user_role, role_to_section, is_parts_based, is_products_based
)

INPUT_CLS = "block w-full rounded-md border border-gray-300 p-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
SELECT_CLS = "block w-full rounded-md border border-gray-300 p-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"


class WorkEntryForm(forms.ModelForm):
    # انتخاب مدل (ProductModel) — لیست به‌صورت داینامیک در __init__ پر می‌شود
    model = forms.ChoiceField(
        choices=[('', 'انتخاب مدل')],
        label=_("مدل"),
        widget=forms.Select(attrs={"class": SELECT_CLS, "id": "id_model"}),
    )
    # حالت «بخش قطعه‌محور»: انتخاب قطعه
    part = forms.ModelChoiceField(
        queryset=Part.objects.none(), required=False, label=_("قطعه"),
        empty_label=" ", widget=forms.Select(attrs={"class": SELECT_CLS, "id": "id_part"}),
    )
    # حالت «بخش محصول‌محور»: انتخاب محصول
    product = forms.ModelChoiceField(
        queryset=Product.objects.none(), required=False, label=_("محصول"),
        empty_label="انتخاب محصول", widget=forms.Select(attrs={"class": SELECT_CLS, "id": "id_product"}),
    )
    # فقط برای بخش‌های قطعه‌محور نمایش/الزام می‌شود
    produced_qty = forms.IntegerField(
        required=False, min_value=0, initial=0, label=_("تعداد تولید"),
        widget=forms.NumberInput(attrs={"class": INPUT_CLS, "id": "id_produced_qty", "placeholder": "0"}),
    )
    scrap_qty = forms.IntegerField(
        required=False, min_value=0, initial=0, label=_("تعداد ضایعات"),
        widget=forms.NumberInput(attrs={"class": INPUT_CLS, "id": "id_scrap_qty", "placeholder": "0"}),
    )
    # فقط برای بخش‌های محصول‌محور نمایش/الزام می‌شود
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

        # Ensure Persian error messages for choices
        self.fields['model'].error_messages.update({
            'required': 'انتخاب مدل الزامی است.',
            'invalid_choice': 'گزینه انتخاب‌شده معتبر نیست.',
        })
        self.fields['part'].error_messages.update({'invalid_choice': 'گزینه انتخاب‌شده معتبر نیست.'})
        self.fields['product'].error_messages.update({'invalid_choice': 'گزینه انتخاب‌شده معتبر نیست.'})

        role = get_user_role(user)
        section = section_override or role_to_section(role)
        self.user = user
        self.section = section

        # بارگذاری ProductModel ها برای لیست مدل
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
            # Make part selection mandatory in parts-based sections
            self.fields["part"].required = True
            self.fields["part"].error_messages.update({'required': 'لطفاً قطعه را انتخاب کنید.'})
            self.fields["part"].widget.attrs.pop('required', None)
            self.fields["part"].widget.attrs['aria-required'] = 'true'
            # پنهان‌سازی فیلدهای مخصوص محصول‌محور
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
            # پنهان‌سازی فیلدهای مخصوص قطعه‌محور
            self.fields["part"].widget = forms.HiddenInput()
            self.fields["produced_qty"].widget = forms.HiddenInput()
            self.fields["scrap_qty"].widget = forms.HiddenInput()
            # الزام شماره کار
            self.fields["job_number"].required = True
            self.fields["job_number"].error_messages = {**getattr(self.fields["job_number"], 'error_messages', {}), 'required': 'شماره کار الزامی است.'}
            self.fields["job_number"].widget.attrs.pop('required', None)
            self.fields["job_number"].widget.attrs['aria-required'] = 'true'

        # Add error ring styling for fields with errors (align with users app)
        if self.is_bound:
            for name, field in self.fields.items():
                if name in self.errors:
                    w = field.widget
                    prev = w.attrs.get('class', '')
                    w.attrs['class'] = (prev + ' ring-1 ring-red-500 focus:ring-red-300').strip()
                    w.attrs['aria-invalid'] = 'true'

    def clean(self):
        cleaned = super().clean()
        # یک‌دست‌سازی شماره کار
        job_number = cleaned.get("job_number")
        if job_number:
            cleaned["job_number"] = job_number.strip()

        # اعتبارسنجی مخصوص بخش‌ها
        section = getattr(self, 'section', None)
        if is_parts_based(section):
            produced = cleaned.get("produced_qty") or 0
            scrap = cleaned.get("scrap_qty") or 0
            if produced < 0 or scrap < 0:
                raise forms.ValidationError(_("مقادیر تولید یا ضایعات نمی‌تواند منفی باشد."))
            if produced == 0 and scrap == 0:
                raise forms.ValidationError(_("حداقل یکی از تعداد تولید یا ضایعات باید وارد شود."))
            # در حالت قطعه‌محور این فیلدها عملاً کاربرد ندارند
            cleaned["job_number"] = None
            cleaned["is_scrap"] = False
            cleaned["is_external"] = False

        # ناسازگاری همزمان «اسقاط» و «کلاف بیرون»
        if cleaned.get("is_scrap") and cleaned.get("is_external"):
            raise forms.ValidationError(_("نمی‌توانید همزمان اسقاط و کلاف بیرون را انتخاب کنید."))

        return cleaned
        # Require model selection always; localize required message and a11y hints
        self.fields['model'].required = True
        self.fields['model'].error_messages.update({'required': 'لطفاً مدل را انتخاب کنید.'})
        self.fields['model'].widget.attrs.pop('required', None)
        self.fields['model'].widget.attrs['aria-required'] = 'true'
