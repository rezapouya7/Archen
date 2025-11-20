# PATH: /Archen/users/admin.py
# Path: users/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import CustomUser
from .forms import CustomUserCreationForm, CustomUserChangeForm


@admin.register(CustomUser)
class CustomUserAdmin(BaseUserAdmin):
    add_form = CustomUserCreationForm
    form = CustomUserChangeForm
    model = CustomUser

    list_display = ("username", "full_name", "role", "is_active", "is_staff")

    # --- helpers -------------------------------------------------------------
    def _strip_fields(self, fieldsets, to_remove=("first_name", "last_name")):
        """
        Remove unwanted fields from any fieldset safely, regardless of the set name
        (which may be translated). If a fieldset becomes empty, drop it.
        """
        new_sets = []
        for name, opts in fieldsets:
            fields = opts.get("fields", ())
            # Normalize to tuple (can be a tuple of tuples sometimes)
            if isinstance(fields, (list, tuple)):
                # Flatten if fields is a tuple of tuples (rare but safe to guard)
                flat = []
                for item in fields:
                    if isinstance(item, (list, tuple)):
                        flat.extend(item)
                    else:
                        flat.append(item)
                new_fields = tuple(f for f in flat if f not in to_remove)
                if new_fields:
                    new_opts = {**opts, "fields": new_fields}
                    new_sets.append((name, new_opts))
                # else: drop empty set
            else:
                # Unexpected shape; keep as is
                new_sets.append((name, opts))
        return tuple(new_sets)


    def get_fieldsets(self, request, obj=None):
        base = super().get_fieldsets(request, obj)
        base = self._strip_fields(base, to_remove=("first_name", "last_name"))
        # Append our extra fields section
        extra = (None, {"fields": ("full_name", "role")})
        return base + (extra,)

    # --- add view (create user) ---------------------------------------------
    def get_add_fieldsets(self, request):
        """
        Build the add form without first_name/last_name and include our custom fields.
        If USERNAME_FIELD is email, swap accordingly.
        """
        fields = [
            "username",    # change to "email" if USERNAME_FIELD == "email"
            "password1",
            "password2",
            "full_name",
            "role",
            "is_active",
            "is_staff",
        ]
        return (
            (None, {
                "classes": ("wide",),
                "fields": tuple(fields),
            }),
        )


