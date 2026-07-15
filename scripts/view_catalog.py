#!/usr/bin/env python3
"""Compatibility entrypoint for the packaged local catalog viewer."""

from _package_bootstrap import ensure_src

ensure_src()

from movie_inbox.web.assets import render_html  # noqa: E402
from movie_inbox.web.catalog_api import *  # noqa: F401,F403,E402
from movie_inbox.web.config import ViewerConfig  # noqa: E402
from movie_inbox.web.handlers import make_handler  # noqa: E402
from movie_inbox.web.image_proxy import *  # noqa: F401,F403,E402
from movie_inbox.web.server import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
