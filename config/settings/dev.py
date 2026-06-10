from .base import *  # noqa: F403

DEBUG = True

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Tests run tasks inline; `runserver` + `run_huey` use Redis as configured in base.
import sys  # noqa: E402

if "pytest" in sys.modules or "test" in sys.argv:
    HUEY = {"huey_class": "huey.MemoryHuey", "name": "atlas", "immediate": True}
    ATLAS_AUTO_FETCH_PDF = False  # tests opt in explicitly; no surprise network calls
