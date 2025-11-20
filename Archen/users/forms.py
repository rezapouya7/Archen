# PATH: /Archen/users/forms.py
from django import forms
from django.contrib.auth.forms import AuthenticationForm
from .models import CustomUser

# ===== Tailwind styling =====
INPUT_CLS = "block w-full rounded-md border border-gray-300 p-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
SELECT_CLS = "block w-full rounded-md border border-gray-300 p-2.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
TEXTAREA_CLS = "block w-full rounded-md border border-gray-300 p-2.5 text-sm min-h-24 focus:outline-none focus:ring-2 focus:ring-blue-500"
CHECK_CLS = "h-4 w-4 text-blue-600 rounded border-gray-300"
RADIO_CLS = "h-4 w-4 text-blue-600 border-gray-300"

# Help texts (FA)
USERNAME_HELP_FA = "الزامی. حداکثر ۱۵۰ کاراکتر؛ فقط حروف، اعداد و نمادهای @ . + - _ مجاز هستند."
IS_ACTIVE_HELP_FA = "مشخص می‌کند این کاربر فعال باشد یا خیر. برای غیرفعال‌سازی، این گزینه را بردارید (به‌جای حذف حساب)."

# Default Persian error messages for all fields (server-side)
DEFAULT_ERRORS_FA = {
    "required": "پر کردن این فیلد الزامی است.",
    "invalid": "مقدار واردشده معتبر نیست.",
    "max_length": "طول این فیلد از حد مجاز بیشتر است.",
    "min_length": "طول این فیلد کمتر از حد مجاز است.",
    "max_value": "مقدار واردشده از حد مجاز بیشتر است.",
    "min_value": "مقدار واردشده از حد مجاز کمتر است.",
    "invalid_choice": "گزینهٔ انتخاب‌شده معتبر نیست.",
    "unique": "این مقدار قبلاً استفاده شده است.",
}


class TailwindFormMixin:
    """ 
     اعمال   کلاس‌های   Tailwind   +   فارسی‌سازی   پیام‌های   error    ( اجباری )  
     و   delete   خصوصیت   HTML    ' required '    برای   جلوگیری   از   پیام‌های   انگلیسی   مرورگر .  
     """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for name, field in self.fields.items():
            w = field.widget

            # ===== CSS class assignment =====
            if isinstance(w, (forms.TextInput, forms.EmailInput, forms.NumberInput,
                              forms.PasswordInput, forms.URLInput)):
                base = INPUT_CLS
            elif isinstance(w, forms.Textarea):
                base = TEXTAREA_CLS
            elif isinstance(w, forms.Select):
                base = SELECT_CLS
            elif isinstance(w, forms.CheckboxInput):
                base = CHECK_CLS
            elif isinstance(w, forms.RadioSelect):
                base = RADIO_CLS
            elif isinstance(w, forms.DateInput):
                base = INPUT_CLS
            else:
                base = INPUT_CLS

            prev = w.attrs.get("class", "")
            w.attrs["class"] = (prev + " " + base).strip()
            w.attrs.setdefault("dir", "rtl")
            w.attrs.setdefault("aria-label", field.label or name)

            # ===== Localize error messages to Persian (mandatory override) =====

            field.error_messages.update(DEFAULT_ERRORS_FA)

            # Remove the HTML5 'required' attribute to neutralize browser validation.
            # Server-side validation is sufficient for our forms.
            if field.required:
                w.attrs.pop("required", None)

            # If the form is bound and this field contains an error, append error styling.
            if self.is_bound and name in self.errors:
                w.attrs["class"] += " ring-1 ring-red-500 focus:ring-red-300"
                w.attrs["aria-invalid"] = "true"


# =====   create   user   =====
class CustomUserCreationForm(TailwindFormMixin, forms.ModelForm):
    password1 = forms.CharField(
        label="رمز عبور",
        widget=forms.PasswordInput()
    )
    password2 = forms.CharField(
        label="تکرار رمز عبور",
        widget=forms.PasswordInput()
    )

    class Meta:
        model = CustomUser
        fields = ("username", "full_name", "role", "email")
        widgets = {
            "username": forms.TextInput(),
            "full_name": forms.TextInput(),
            "email": forms.EmailInput(),
        }
        labels = {
            "username": "نام کاربری",
            "full_name": "نام و نام خانوادگی",
            "role": "نقش",
            "email": "ایمیل",
        }
        help_texts = {
            "username": USERNAME_HELP_FA,
        }
        error_messages = {
            "role": {"required": "لطفاً نقش را انتخاب کنید."},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].help_text = USERNAME_HELP_FA
        if "role" in self.fields:
            # Retain the custom Persian required message for the role field
            self.fields["role"].error_messages.update({"required": "لطفاً نقش را انتخاب کنید."})
            # Remove any blank choice inserted by Django and prepend a single descriptive placeholder.
            existing = list(self.fields["role"].choices)
            # Keep only non-empty choices (code is not blank)
            filtered = [(code, label) for code, label in existing if code]
            # Prepend our own placeholder as the sole empty option
            self.fields["role"].choices = [("", "انتخاب نقش")] + filtered

    def clean(self):
        cleaned = super().clean()
        p1, p2 = cleaned.get("password1"), cleaned.get("password2")
        if p1 or p2:
            if p1 != p2:
                self.add_error("password2", "رمز عبور و تکرار آن یکسان نیست.")
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        password = self.cleaned_data.get("password1")
        if password:
            user.set_password(password)
        if commit:
            user.save()
        return user


# =====   edit   user   =====
class CustomUserChangeForm(TailwindFormMixin, forms.ModelForm):
    password1 = forms.CharField(
        label="رمز عبور جدید",
        widget=forms.PasswordInput(attrs={"placeholder": "در صورت نیاز، رمز جدید را وارد کنید"}),
        required=False
    )
    password2 = forms.CharField(
        label="تکرار رمز عبور جدید",
        widget=forms.PasswordInput(attrs={"placeholder": "تکرار رمز جدید"}),
        required=False
    )

    class Meta:
        model = CustomUser
        fields = ("username", "full_name", "role", "email", "is_active")
        widgets = {
            "username": forms.TextInput(),
            "full_name": forms.TextInput(),
            "email": forms.EmailInput(),
        }
        labels = {
            "username": "نام کاربری",
            "full_name": "نام و نام خانوادگی",
            "role": "نقش",
            "email": "ایمیل",
            "is_active": "فعال",
        }
        help_texts = {
            "username": USERNAME_HELP_FA,
            "is_active": IS_ACTIVE_HELP_FA,
        }
        error_messages = {
            "role": {"required": "لطفاً نقش را انتخاب کنید."},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].help_text = USERNAME_HELP_FA
        if "is_active" in self.fields:
            self.fields["is_active"].help_text = IS_ACTIVE_HELP_FA
        if "role" in self.fields:
            self.fields["role"].error_messages.update({"required": "لطفاً نقش را انتخاب کنید."})
            # Remove any blank choice inserted by Django and prepend a single descriptive placeholder.
            existing = list(self.fields["role"].choices)
            filtered = [(code, label) for code, label in existing if code]
            self.fields["role"].choices = [("", "انتخاب نقش")] + filtered

    def clean(self):
        cleaned = super().clean()
        p1, p2 = cleaned.get("password1"), cleaned.get("password2")
        if p1 or p2:
            if p1 != p2:
                self.add_error("password2", "رمز عبور جدید با تکرار آن یکسان نیست.")
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        p1 = self.cleaned_data.get("password1")
        if p1:
            user.set_password(p1)
        if commit:
            user.save()
        return user


# =====   authentication (login)   =====
class LoginAuthenticationForm(TailwindFormMixin, AuthenticationForm):
    """Authentication form with Persian error messages and Tailwind styling.

    This overrides the default invalid login message to Persian and also
    localizes the inactive account message. The TailwindFormMixin applies
    consistent styling and RTL attributes across fields.
    """
    error_messages = {
        # Shown when username/password combination is incorrect
        'invalid_login': (
            'لطفاً نام کاربری و گذرواژه صحیح را وارد کنید. '
            'توجه داشته باشید که هر دو فیلد ممکن است به بزرگی و کوچکی حروف حساس باشند.'
        ),
        # Shown when the user account is inactive
        'inactive': 'این حساب کاربری غیرفعال است.'
    }

    def __init__(self, *args, **kwargs):
        # Initialize parent classes and then adjust field labels/placeholders
        super().__init__(*args, **kwargs)
        if 'username' in self.fields:
            self.fields['username'].label = 'نام کاربری'
        if 'password' in self.fields:
            self.fields['password'].label = 'گذرواژه'
