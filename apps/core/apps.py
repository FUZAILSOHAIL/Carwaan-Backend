from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.core'
    verbose_name = 'Core'

    def ready(self):
        """
        Django app ready hook for any initialization
        """
        super().ready()
        # Import admin configurations to ensure they're loaded
        try:
            from . import admin
        except ImportError:
            pass
