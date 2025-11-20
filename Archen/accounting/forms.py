"""
Forms for the accounting app.

This module currently defines a single non‑model form used for capturing
simple financial records.  The form was moved from the production_line app
as part of the separation of accounting functionality into its own
application.  Moving it here helps decouple accounting concerns from
production_line and ensures that future accounting features reside in the
correct domain.
"""

from django import forms


# Tailwind-like CSS classes reused from the production_line forms.  These
# constants mirror the definitions in production_line/forms.py to maintain
# visual consistency across forms in the project.  Should the styling

# accounting logic.
INPUT_CLS = (
    "block w-full rounded-md border border-gray-300 p-2.5 text-sm "
    "focus:outline-none focus:ring-2 focus:ring-blue-500"
)
SELECT_CLS = (
    "block w-full rounded-md border border-gray-300 p-2 text-sm bg-white "
    "focus:outline-none focus:ring-2 focus:ring-blue-500"
)


class FinanceRecordForm(forms.Form):
    """A non‑model form for capturing a single financial record.

    Each record tracks the entity name, the monetary amount, the type of
    account (receivable or payable) and an optional description.  The form
    does not persist data to the database; persistence is handled by the
    accounting views (see accounting/views.py) which store records in a
    JSON file.  This design avoids unnecessary model migrations and keeps
    accounting lightweight while requirements are minimal.
    """

    entity_name = forms.CharField(
        label="نام شخص/شرکت",
        widget=forms.TextInput(
            attrs={"class": INPUT_CLS, "placeholder": "مثلاً: شرکت الف"}
        ),
    )
    amount = forms.DecimalField(
        label="مبلغ",
        widget=forms.NumberInput(
            attrs={
                "class": INPUT_CLS,
                "step": "0.01",
                "inputmode": "decimal",
                "placeholder": "0",
            }
        ),
    )
    record_type = forms.ChoiceField(
        # Insert a visually blank option so no type is selected by default
        choices=[("", "انتخاب نوع حساب"), ("receivable", "بستانکاری"), ("payable", "بدهکاری")],
        label="نوع حساب",
        widget=forms.Select(attrs={"class": SELECT_CLS}),
    )
    description = forms.CharField(
        label="توضیحات",
        required=False,
        widget=forms.Textarea(attrs={"class": INPUT_CLS, "rows": 3}),
    )