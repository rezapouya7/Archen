# PATH: /Archen/Archen/views.py
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required

# We keep dashboard for managers and accountants; other roles are routed to their work page.
@login_required(login_url='/users/login/')
def dashboard_view(request):
    user = request.user
    role = getattr(user, 'role', '')
    # Route production_line roles to their daily work entry page
    # Allow 'manager' and 'accountant' to see the main dashboard
    if role and role not in ('manager', 'accountant'):
        return redirect('production_line:work_entry')

    # Manager/Accountant dashboard (keep it minimal as before)
    context = {"production_stages": []}
    return render(request, "dashboard.html", context)
