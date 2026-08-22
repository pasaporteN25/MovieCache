from _package_bootstrap import ensure_src

ensure_src()

from movie_inbox.web.security import *  # noqa: F401,F403,E402
