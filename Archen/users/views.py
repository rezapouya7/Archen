# PATH: /Archen/users/views.py
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.views.decorators.http import require_POST
from .models import CustomUser
from .forms import CustomUserCreationForm, CustomUserChangeForm, LoginAuthenticationForm

# --- added imports for logout view ---
from django.contrib.auth import logout, update_session_auth_hash
from django.views.decorators.http import require_http_methods
from django.shortcuts import redirect
# --- end added imports ---

from django.contrib.auth.views import LoginView
from django.conf import settings
from django.http import JsonResponse, HttpResponse, HttpResponseServerError
from django.db.models import Q


class RememberLoginView(LoginView):
    template_name = 'registration/login.html'
    # Use a custom authentication form with Persian messages
    # Comment: Provides localized error messages for invalid credentials
    authentication_form = LoginAuthenticationForm
    # Inject user options for username dropdown on login page
    # Comment: Provide (username, "Full Name - Role") pairs to template
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        # Only include active users in the username dropdown
        # Comment: Exclude inactive users so they do not appear in the list
        users = CustomUser.objects.filter(is_active=True).order_by('full_name', 'username')
        options = []
        for u in users:
            # Compose label with full name and localized role display
            role_display = getattr(u, 'get_role_display', lambda: u.role)()
            label = f"{u.full_name or u.username} - {role_display}"
            options.append((u.username, label))
        ctx['login_user_options'] = options
        return ctx

    def dispatch(self, request, *args, **kwargs):
        # If already authenticated and is accountant, always go to dashboard
        try:
            user = getattr(request, 'user', None)
            if user and user.is_authenticated and getattr(user, 'role', None) == 'accountant':
                from django.urls import reverse
                return redirect(reverse('dashboard'))
        except Exception:
            pass
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        response = super().form_valid(form)
        remember = self.request.POST.get('remember')
        if remember:
            max_age = getattr(settings, 'REMEMBER_ME_SESSION_AGE', 60 * 60 * 24 * 14)
            self.request.session.set_expiry(max_age)
        else:
            self.request.session.set_expiry(0)
        # Role-based post-login redirect: accountants go to main dashboard
        try:
            user = self.request.user
            if getattr(user, 'role', None) == 'accountant':
                from django.urls import reverse
                return redirect(reverse('dashboard'))
        except Exception:
            pass
        return response

    def get_success_url(self):
        try:
            user = getattr(self.request, 'user', None)
            if user and getattr(user, 'role', None) == 'accountant':
                from django.urls import reverse
                return reverse('dashboard')
        except Exception:
            pass
        return super().get_success_url()


def is_manager(user):
    return user.is_authenticated and getattr(user, 'role', None) == 'manager'


def _build_xlsx_response(sheet_title, report_title, headers, rows, filename, column_widths=None):
    """Shared XLSX generator for user exports."""
    try:
        from utils.xlsx import build_table_response
    except ImportError:
        return HttpResponseServerError("کتابخانه openpyxl نصب نشده است؛ لطفاً با مدیر سیستم تماس بگیرید.")

    return build_table_response(
        sheet_title=sheet_title,
        report_title=report_title,
        headers=headers,
        rows=rows,
        filename=filename,
        column_widths=column_widths or [],
        table_name="UsersExport",
    )


@login_required
@user_passes_test(is_manager)
def user_list_view(request):
    """
    Display the list of users with optional filtering by role.

    A role may be supplied via the ``role`` query parameter.  When a role
    value is provided, only users with that role are displayed.  The
    ``current_role`` key in the context is used by the template to mark
    the selected option in the dropdown.  All defined roles are
    enumerated via ``role_choices`` for use as filter options.  The
    number of active users is also computed for display.
    """
    qs = CustomUser.objects.all().order_by('-id')
    # Retrieve the selected role from the query string.  Blank means all roles.
    selected_role = (request.GET.get('role') or '').strip()
    search_query = (request.GET.get('search') or '').strip()
    if selected_role:
        qs = qs.filter(role=selected_role)
    if search_query:
        qs = qs.filter(
            Q(full_name__icontains=search_query) |
            Q(username__icontains=search_query) |
            Q(role__icontains=search_query)
        )
    active_users_count = qs.filter(is_active=True).count()
    # All possible role choices for the filter dropdown
    role_field = CustomUser._meta.get_field('role')
    role_choices = sorted(list(role_field.choices), key=lambda x: x[1])
    context = {
        'users': qs,
        'active_users_count': active_users_count,
        'role_choices': role_choices,
        'current_role': selected_role,
        # Pass through the search query (if any) to preserve input value
        'search_query': search_query,
    }
    return render(request, 'users/user_list.html', context)


@login_required
@user_passes_test(is_manager)
def users_export_xlsx(request):
    qs = CustomUser.objects.all().order_by('-id')
    role_filter = (request.GET.get('role') or '').strip()
    search_query = (request.GET.get('search') or '').strip()

    if role_filter:
        qs = qs.filter(role=role_filter)
    if search_query:
        qs = qs.filter(
            Q(full_name__icontains=search_query) |
            Q(username__icontains=search_query) |
            Q(role__icontains=search_query)
        )

    headers = ['نام و نام خانوادگی', 'نام کاربری', 'نقش', 'وضعیت']
    rows = []
    for user in qs:
        rows.append([
            user.full_name or user.username or '',
            user.username,
            getattr(user, 'get_role_display', lambda: user.role)(),
            'فعال' if user.is_active else 'غیرفعال',
        ])

    return _build_xlsx_response(
        sheet_title="لیست کاربران",
        report_title="گزارش لیست کاربران",
        headers=headers,
        rows=rows,
        filename="users_list.xlsx",
        column_widths=[28, 22, 18, 14],
    )


@login_required
@user_passes_test(is_manager)
def user_create_view(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'کاربر جدید با موفقیت ایجاد شد.')
            return redirect('users:user_list')
    else:
        form = CustomUserCreationForm()
    return render(request, 'users/user_form.html', {
        'form': form,
        'is_editing': False,
    })


@login_required
@user_passes_test(is_manager)
def user_edit_view(request, pk):
    user_obj = get_object_or_404(CustomUser, pk=pk)
    original_is_active = user_obj.is_active

    def _disable_active_field(form_obj):
        """Disable is_active field for superuser edits."""
        field = form_obj.fields.get('is_active')
        if not field:
            return
        field.disabled = True
        css_classes = field.widget.attrs.get('class', '')
        extra = 'opacity-50 cursor-not-allowed'
        if extra not in css_classes:
            field.widget.attrs['class'] = (css_classes + ' ' + extra).strip()

    if request.method == 'POST':
        form = CustomUserChangeForm(request.POST, instance=user_obj)
        if user_obj.is_superuser and 'is_active' in form.fields:
            _disable_active_field(form)
        if form.is_valid():
            if user_obj.is_superuser:
                # Preserve superuser active state regardless of form data.
                updated_user = form.save(commit=False)
                updated_user.is_active = original_is_active
                updated_user.save()
            else:
                updated_user = form.save()
            # Keep current session valid when a manager edits their own password.
            if updated_user.pk == request.user.pk:
                update_session_auth_hash(request, updated_user)
            messages.success(request, 'تغییرات کاربر با موفقیت ذخیره شد.')
            return redirect('users:user_list')
    else:
        form = CustomUserChangeForm(instance=user_obj)
        if user_obj.is_superuser and 'is_active' in form.fields:
            _disable_active_field(form)
    return render(request, 'users/user_form.html', {
        'form': form,
        'is_editing': True,
        'user_obj': user_obj,
    })


@login_required
@user_passes_test(is_manager)
@require_POST
def user_toggle_active_view(request, pk):
    """
    Toggle the user's active/inactive status without emitting any success messages.
    This endpoint accepts only POST requests.
    """
    user_obj = get_object_or_404(CustomUser, pk=pk)
    if user_obj.is_superuser:
        messages.error(request, 'امکان غیرفعال کردن سوپر یوزر وجود ندارد.')
        return redirect('users:user_list')
    user_obj.is_active = not user_obj.is_active
    user_obj.save(update_fields=['is_active'])
    # Do not add any success messages here
    return redirect('users:user_list')


@login_required
@user_passes_test(is_manager)
@require_POST
def user_bulk_delete_view(request):
    """Delete multiple users if ``ids`` are submitted via the form."""
    # Accept either ``selected_users`` (used by the template) or a generic ``ids`` key.
    ids = request.POST.getlist('selected_users') or request.POST.getlist('ids')
    if ids:
        # Only delete if there are selected IDs.  Coerce to integers to prevent
        # accidental injection of invalid values.
        try:
            id_ints = [int(pk) for pk in ids]
        except (TypeError, ValueError):
            id_ints = []
        if id_ints:
            queryset = CustomUser.objects.filter(id__in=id_ints)
            superuser_ids = list(queryset.filter(is_superuser=True).values_list('id', flat=True))
            if superuser_ids:
                messages.error(request, 'امکان حذف سوپر یوزر وجود ندارد. کاربران دیگر حذف می‌شوند.')
            deleted = queryset.exclude(is_superuser=True).delete()[0]
            if deleted:
                messages.success(request, 'کاربران انتخاب شده حذف شدند.')
            elif not superuser_ids:
                messages.warning(request, 'هیچ کاربری حذف نشد.')
        else:
            messages.warning(request, 'هیچ کاربری انتخاب نشده است.')
    else:
        messages.warning(request, 'هیچ کاربری انتخاب نشده است.')
    return redirect('users:user_list')


# --- Session & authentication utilities ---
@require_http_methods(["GET", "POST"])  # Allow GET for mobile/PWA environments
def logout_view(request):
    """Log the user out and redirect to the login page.
    Notes:
    - We accept GET for environments where POST forms may be intercepted by the WebView or PWA shell.
    - For security, the template uses a POST form; GET remains as a safe fallback.
    """
    logout(request)
    return redirect('login')


@login_required
@user_passes_test(is_manager)
def user_stats_view(request):
    """Return JSON stats for users list based on optional filters.

    Query params:
    - role: optional role key to filter by (exact match)
    - search: optional substring to filter by (applied to username, full_name, email)

    Response JSON:
    {"total": <int>, "active": <int>}
    """
    qs = CustomUser.objects.all()

    # Apply role filter if provided
    role = (request.GET.get('role') or '').strip()
    if role:
        qs = qs.filter(role=role)

    # Apply simple text search across common fields when provided
    search = (request.GET.get('search') or '').strip()
    if search:
        qs = qs.filter(
            Q(username__icontains=search) |
            Q(full_name__icontains=search) |
            Q(email__icontains=search)
        )

    total = qs.count()
    active = qs.filter(is_active=True).count()
    return JsonResponse({"total": total, "active": active})
