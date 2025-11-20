from django.apps import AppConfig


class JobsConfig(AppConfig):
    """Configuration for the jobs app.

    This app encapsulates all logic related to production jobs.  It was
    extracted from the ``production_line`` app to better separate
    responsibilities and to allow the jobs list and forms to live
    directly under the dashboard.  The default auto field is not
    overridden so Django's project‑level setting applies.
    """

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'jobs'