# PATH: /Archen/Archen/__init__.py

"""Project package initialization.

This module tweaks Django's default form error messages so that common
validation strings appear in Persian instead of the built‑in English
phrasing.  The adjustment is applied once on import and affects all
forms across the project.
"""

from django import forms
from django.core import validators
from functools import wraps


_ERROR_TRANSLATIONS = {
    'required': 'پر کردن این فیلد الزامی است.',
    'invalid': 'مقدار وارد شده معتبر نیست.',
    'max_length': 'حداکثر طول مجاز این فیلد %(max_length)s کاراکتر است.',
    'min_length': 'حداقل طول مجاز این فیلد %(min_length)s کاراکتر است.',
    'max_value': 'حداکثر مقدار مجاز %(limit_value)s است.',
    'min_value': 'حداقل مقدار مجاز %(limit_value)s است.',
    'invalid_choice': 'گزینه انتخاب‌شده معتبر نیست.',
    'unique': 'این مقدار قبلاً ثبت شده است.',
    'invalid_list': 'باید یک لیست معتبر وارد کنید.',
}


def _localise_default_error_messages() -> None:
    """Patch Django form fields so default errors display in Persian."""

    # Iterate over every Field subclass defined in django.forms.fields and
    # replace the standard error strings where applicable.
    for attr in dir(forms.fields):
        field_cls = getattr(forms.fields, attr)
        if not isinstance(field_cls, type):
            continue
        if not issubclass(field_cls, forms.Field):
            continue
        messages = getattr(field_cls, 'default_error_messages', None)
        if not isinstance(messages, dict):
            continue
        for key, value in _ERROR_TRANSLATIONS.items():
            if key in messages:
                messages[key] = value

    # Base Form/ModelForm keep their own dictionaries for non-field errors.
    base_messages = getattr(forms.Form, 'default_error_messages', None)
    if isinstance(base_messages, dict):
        for key, value in _ERROR_TRANSLATIONS.items():
            if key in base_messages:
                base_messages[key] = value

    model_form_messages = getattr(forms.ModelForm, 'default_error_messages', None)
    if isinstance(model_form_messages, dict):
        for key, value in _ERROR_TRANSLATIONS.items():
            if key in model_form_messages:
                model_form_messages[key] = value


def _localise_core_validators() -> None:
    """Update built-in validator messages to Persian."""

    translations = {
        validators.MinValueValidator: 'مقدار باید حداقل %(limit_value)s باشد.',
        validators.MaxValueValidator: 'مقدار باید حداکثر %(limit_value)s باشد.',
        validators.MinLengthValidator: 'این مقدار باید حداقل %(limit_value)d کاراکتر باشد (اکنون %(show_value)d کاراکتر وارد شده است).',
        validators.MaxLengthValidator: 'این مقدار باید حداکثر %(limit_value)d کاراکتر باشد (اکنون %(show_value)d کاراکتر وارد شده است).',
    }

    for validator_cls, message in translations.items():
        validator_cls.message = message

        original_init = validator_cls.__init__

        @wraps(original_init)
        def wrapped_init(self, *args, __orig=original_init, __message=message, **kwargs):
            if 'message' not in kwargs or kwargs['message'] is None:
                kwargs['message'] = __message
            __orig(self, *args, **kwargs)

        validator_cls.__init__ = wrapped_init


_localise_default_error_messages()
_localise_core_validators()
