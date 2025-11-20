# PATH: /Archen/Archen/context_processors.py

def full_name_context(request):
    if request.user.is_authenticated:
        full_name = getattr(request.user, 'full_name', '') or request.user.username
        return {
            'full_name': full_name,
            'role': getattr(request.user, 'role', ''),
            'is_superuser': request.user.is_superuser
        }
    return {}
