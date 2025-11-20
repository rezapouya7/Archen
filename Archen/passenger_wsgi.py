import os
from django.core.wsgi import get_wsgi_application
# from Archen.wsgi import application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Archen.settings')
application = get_wsgi_application()

