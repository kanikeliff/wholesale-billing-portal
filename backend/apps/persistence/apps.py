from django.apps import AppConfig


class PersistenceConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.persistence"

    def ready(self):
        from apps.persistence.runtime import wire_database_persistence

        wire_database_persistence()
