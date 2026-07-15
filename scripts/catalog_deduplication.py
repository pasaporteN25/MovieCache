from _package_bootstrap import ensure_src

ensure_src()

from movie_inbox.domain.deduplication import *  # noqa: F401,F403,E402
