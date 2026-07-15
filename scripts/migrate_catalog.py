#!/usr/bin/env python3
from _package_bootstrap import ensure_src

ensure_src()

from movie_inbox.cli.migrate import *  # noqa: F401,F403,E402


if __name__ == "__main__":
    raise SystemExit(main())
