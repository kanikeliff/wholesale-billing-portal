import os

from .settings import *


# Database runtime defaults to the real Django/PostgreSQL billing repository.
# Tests or local workflows may explicitly override this environment variable.
# Default config.settings behavior remains unchanged.
os.environ.setdefault("USE_MOCK_BILLING_PROVIDER", "false")

INSTALLED_APPS = [
    *INSTALLED_APPS,
    "apps.persistence.apps.PersistenceConfig",
]
