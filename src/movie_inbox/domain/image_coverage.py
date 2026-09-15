"""[U7.1]: how much of a catalogue can fill the console's two image windows, and why not.

Coverage is measured from what is already on this machine -- the catalogue, the
collection store and the image cache directory -- so the diagnosis never
downloads anything. That decides which causes it can name. It can tell an empty
field from an address the image proxy would refuse, and an image that was never
cached from one that was. It cannot tell an address that now answers 404, a
provider that is down, or a provider that has no image for the work: those need
the network, and they belong to [U7.2], on a small sample.

Everything here is pure. The two questions that touch the outside world -- would
the proxy accept this address, is it already cached -- arrive as callables.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from movie_inbox.domain.catalog import myanimelist_anime_id, themoviedb_media_reference
from movie_inbox.domain.normalization import normalize_kind

# The two fields the console windows draw from today.
IMAGE_SLOTS = ("page_image", "backdrop_image")

EMPTY = "empty"
REJECTED = "rejected"
UNCACHED = "uncached"
CACHED = "cached"
SLOT_STATES = (EMPTY, REJECTED, UNCACHED, CACHED)

TMDB_IDENTITY = "tmdb"
OTHER_IDENTITY = "other"
NO_IDENTITY = "none"
IDENTITIES = (TMDB_IDENTITY, OTHER_IDENTITY, NO_IDENTITY)

CATALOG_ORIGIN = "catalog"
CLUB_ORIGIN = "club"
ORIGINS = (CATALOG_ORIGIN, CLUB_ORIGIN)

KINDS = ("pelicula", "serie", "anime", "documental")

AddressCheck = Callable[[str], bool]

_TMDB_SIZED = re.compile(r"^/t/p/[^/]+(/[^/]+)$")
_WIKIMEDIA_THUMB = re.compile(r"^(/[^/]+/[^/]+)/thumb(/[0-9a-f]/[0-9a-f]{2}/[^/]+)/[^/]+$")
_AMAZON_HOSTS = frozenset({"m.media-amazon.com", "ia.media-imdb.com"})
_AMAZON_IMAGE = re.compile(r"^(/images/M/.+?)(?:\._V1_[^/]*)?\.(?:jpe?g|png|webp)$")
_FILMAFFINITY_HOSTS = frozenset({"pics.filmaffinity.com", "images.filmaffinity.com"})
_FILMAFFINITY_SIZED = re.compile(
    r"^(/.+-\d+)-(?:large|mmed|msmall|mtiny|full)\.(?:jpe?g|png|webp)$"
)
_MYANIMELIST_SIZED = re.compile(r"^(/images/(?:anime|manga)/\d+/\d+)[lt]?\.(?:jpe?g|webp)$")
_IMDB_ID = re.compile(r"\btt\d{7,9}\b", re.IGNORECASE)
_WIKIDATA_ID = re.compile(r"^Q\d+$")


@dataclass(frozen=True)
class WorkImageCoverage:
    """What one work can put in the console windows, reduced to counts."""

    origin: str
    kind: str
    identity: str
    poster: str
    backdrop: str
    distinct: int


def image_asset_key(url: str) -> str:
    """One key per picture, whatever size it was requested at.

    The same poster at 500 and 780 pixels is not two images, and counting it
    twice would promise the console a second window it does not have. Only size
    patterns known per host are folded; any other address keeps its full path,
    which errs toward calling two images different rather than the same.
    """

    text = str(url or "").strip()
    try:
        parsed = urlparse(text)
        host = (parsed.hostname or "").casefold()
    except ValueError:
        return f"url:{text}"
    path = parsed.path
    if host == "image.tmdb.org" and (match := _TMDB_SIZED.match(path)):
        return f"tmdb:{match.group(1)}"
    if host == "upload.wikimedia.org":
        thumb = _WIKIMEDIA_THUMB.match(path)
        return f"wikimedia:{thumb.group(1)}{thumb.group(2)}" if thumb else f"wikimedia:{path}"
    if host in _AMAZON_HOSTS and (match := _AMAZON_IMAGE.match(path)):
        return f"amazon:{match.group(1)}"
    if host in _FILMAFFINITY_HOSTS and (match := _FILMAFFINITY_SIZED.match(path)):
        return f"filmaffinity:{match.group(1)}"
    if host == "cdn.myanimelist.net" and (match := _MYANIMELIST_SIZED.match(path)):
        return f"myanimelist:{match.group(1)}"
    return f"url:{host}{path}"


def image_identity(item: Mapping[str, Any]) -> str:
    """Whether a provider could be asked for this work's images by identifier.

    [U7.2] may only query a provider on confirmed identity, never on a title
    that looks right, so what a missing image costs depends on this. TMDb is
    counted apart because it is the provider [U7.2] evaluates first.
    """

    if str(item.get("tmdb_id") or "").strip().isdigit() or themoviedb_media_reference(
        str(item.get("tmdb_url") or "")
    ):
        return TMDB_IDENTITY
    if (
        _IMDB_ID.search(str(item.get("imdb_url") or ""))
        or _WIKIDATA_ID.match(str(item.get("wikidata_id") or "").strip().upper())
        or myanimelist_anime_id(str(item.get("myanimelist_url") or ""))
        or str(item.get("mal_id") or "").strip().isdigit()
    ):
        return OTHER_IDENTITY
    return NO_IDENTITY


def slot_state(url: str, *, allowed: AddressCheck, cached: AddressCheck) -> str:
    text = str(url or "").strip()
    if not text:
        return EMPTY
    if not allowed(text):
        return REJECTED
    return CACHED if cached(text) else UNCACHED


def classify_work(
    item: Mapping[str, Any],
    origin: str,
    *,
    allowed: AddressCheck,
    cached: AddressCheck,
) -> WorkImageCoverage:
    urls = {slot: str(item.get(slot) or "").strip() for slot in IMAGE_SLOTS}
    states = {slot: slot_state(urls[slot], allowed=allowed, cached=cached) for slot in IMAGE_SLOTS}
    # Only an address the proxy would serve can fill a window, cached or not.
    showable = {
        image_asset_key(urls[slot]) for slot in IMAGE_SLOTS if states[slot] in (UNCACHED, CACHED)
    }
    return WorkImageCoverage(
        origin=origin,
        kind=normalize_kind(item.get("kind")),
        identity=image_identity(item),
        poster=states["page_image"],
        backdrop=states["backdrop_image"],
        distinct=len(showable),
    )


def summarize(works: Iterable[WorkImageCoverage]) -> dict[str, Any]:
    """Counts in total and per origin and kind. Never a title or an address."""

    rows = list(works)
    segments = [
        {"origin": origin, "kind": kind, **_counts(chosen)}
        for origin in ORIGINS
        for kind in KINDS
        if (chosen := [row for row in rows if row.origin == origin and row.kind == kind])
    ]
    return {"totals": _counts(rows), "segments": segments}


def _counts(rows: list[WorkImageCoverage]) -> dict[str, Any]:
    return {
        "works": len(rows),
        "poster": _tally((row.poster for row in rows), SLOT_STATES),
        "backdrop": _tally((row.backdrop for row in rows), SLOT_STATES),
        "distinct_images": _tally((str(row.distinct) for row in rows), ("0", "1", "2")),
        "identity": _tally((row.identity for row in rows), IDENTITIES),
        # The number [U7.2] starts from: works that cannot fill both windows,
        # split by whether a provider could even be asked about them.
        "short_by_identity": _tally(
            (row.identity for row in rows if row.distinct < len(IMAGE_SLOTS)), IDENTITIES
        ),
    }


def _tally(values: Iterable[str], names: tuple[str, ...]) -> dict[str, int]:
    counts = Counter(values)
    return {name: counts.get(name, 0) for name in names}


__all__ = [
    "CACHED",
    "CATALOG_ORIGIN",
    "CLUB_ORIGIN",
    "EMPTY",
    "IDENTITIES",
    "IMAGE_SLOTS",
    "KINDS",
    "NO_IDENTITY",
    "ORIGINS",
    "OTHER_IDENTITY",
    "REJECTED",
    "SLOT_STATES",
    "TMDB_IDENTITY",
    "UNCACHED",
    "WorkImageCoverage",
    "classify_work",
    "image_asset_key",
    "image_identity",
    "slot_state",
    "summarize",
]
