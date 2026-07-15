from _package_bootstrap import ensure_src

ensure_src()

from movie_inbox.application.external_service import *  # noqa: F401,F403,E402
from movie_inbox.infrastructure.external_catalog import *  # noqa: F401,F403,E402
