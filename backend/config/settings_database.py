from .settings import *

INSTALLED_APPS = [
    *INSTALLED_APPS,
    "apps.persistence.apps.PersistenceConfig",
]
