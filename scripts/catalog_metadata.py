from _package_bootstrap import ensure_src

ensure_src()

from movie_inbox.external.metadata import *  # noqa: F401,F403,E402
from movie_inbox.external.common import fetch_json_safe as fetch_json  # noqa: F401,E402
from movie_inbox.external.imdb import *  # noqa: F401,F403,E402
from movie_inbox.external.wikidata import *  # noqa: F401,F403,E402
from movie_inbox.external.wikipedia import *  # noqa: F401,F403,E402
