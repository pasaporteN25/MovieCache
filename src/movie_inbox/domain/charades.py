"""Charades: deck identity, deterministic generation and difficulty rules.

Pure domain, and deliberately portable. ADR-0005 has the phone playing offline,
so this generator has to be reimplementable in Kotlin and produce byte-identical
decks. That rules out language-specific randomness: the seed is FNV-1a (already
the project's precedent in `back-cover.js`) and the shuffle is a documented LCG,
both a handful of lines in any language.

Scope note: charades is a surface over the existing audiovisual catalogue. It is
not [M1], adds no `kind` values and writes nothing to a work.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

EASY = "facil"
MEDIUM = "medio"
MEDIUM_HIGH = "medio_alto"
HARD = "dificil"

# Ordered easiest to hardest; the order is meaningful for presentation.
DIFFICULTIES = (EASY, MEDIUM, MEDIUM_HIGH, HARD)

# Seconds offered per difficulty. Easy and medium are the owner's values; the
# last two extend the same progression and are adjustable after playing.
TIMER_OPTIONS: dict[str, tuple[int, int, int]] = {
    EASY: (60, 120, 180),
    MEDIUM: (90, 150, 240),
    MEDIUM_HIGH: (120, 180, 300),
    HARD: (180, 240, 360),
}

# A deck needs enough works overall, and enough in the category being played.
# The second is the one that actually decides whether a night works.
MIN_ELIGIBLE_WORKS = 300
MIN_PER_DIFFICULTY = 25

# Vote counts where the public score is decisive on its own. Between them it is
# a suggestion, never a classification -- measured, see docs/briefs/charades-v1.md.
OBSCURE_BELOW_VOTES = 10_000
FAMOUS_ABOVE_VOTES = 1_000_000

_FNV_OFFSET = 2166136261
_FNV_PRIME = 16777619
_MASK32 = 0xFFFFFFFF

# Numerical Recipes' LCG constants. Any language reproduces this exactly.
_LCG_MULTIPLIER = 1664525
_LCG_INCREMENT = 1013904223

_WORD = re.compile(r"[^\W\d_]+", re.UNICODE)


@dataclass(frozen=True)
class CharadeWork:
    """One playable entry, with its identity resolved and its title chosen."""

    key: str
    title: str
    year: str = ""
    difficulty: str = ""
    source: str = "catalog"

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "title": self.title,
            "year": self.year,
            "difficulty": self.difficulty,
            "source": self.source,
        }


def playable_title(item: Mapping[str, Any]) -> str:
    """The single title that gets acted out.

    Fixed order, because two players seeing different titles for the same work
    breaks the game exactly as surely as different works would.
    """

    for field in ("spanish_title", "title", "original_title"):
        value = " ".join(str(item.get(field) or "").split())
        if value:
            return value
    return ""


def work_key(item: Mapping[str, Any]) -> str:
    """Identity that holds across the catalogue and a followed collection.

    Works reach the deck from two stores that do not share ids, so identity
    comes from the strongest external identifier available and falls back to a
    normalised title and year.
    """

    tmdb_id = str(item.get("tmdb_id") or "").strip()
    if tmdb_id.isdigit():
        return f"tmdb:{tmdb_id}"
    imdb = re.search(r"tt\d{7,9}", str(item.get("imdb_url") or ""), re.IGNORECASE)
    if imdb:
        return f"imdb:{imdb.group(0).lower()}"
    wikidata = str(item.get("wikidata_id") or "").strip().upper()
    if re.fullmatch(r"Q\d+", wikidata):
        return f"wikidata:{wikidata}"
    title = normalize_title(playable_title(item))
    year = str(item.get("year") or "").strip()[:4]
    return f"title:{title}|{year}" if title else ""


def normalize_title(value: str) -> str:
    """Casefolded, accent-free, punctuation-free form for comparison only."""

    decomposed = unicodedata.normalize("NFD", str(value or ""))
    stripped = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(_WORD.findall(stripped.casefold()))


def suggest_difficulty(votes: Any) -> str:
    """Classify only where the public score is decisive on its own.

    Between the thresholds the vote count says nothing usable: it measures
    global cinephile attention rather than recognition in the room, and cannot
    separate a famous blockbuster from an art-house classic with the same count.
    Returning "" there is the point -- that work goes to a person.
    """

    try:
        count = int(votes)
    except (TypeError, ValueError):
        return ""
    if count <= 0:
        return ""
    if count < OBSCURE_BELOW_VOTES:
        return HARD
    if count > FAMOUS_ABOVE_VOTES:
        return EASY
    return ""


def resolve_difficulty(manual: Any, suggested: Any) -> str:
    """A person's decision outranks any recomputation, as `locked_fields` does."""

    chosen = str(manual or "").strip()
    if chosen in DIFFICULTIES:
        return chosen
    fallback = str(suggested or "").strip()
    return fallback if fallback in DIFFICULTIES else ""


def deck_fingerprint(keys: Iterable[str]) -> str:
    """Short readable code identifying the set of eligible works.

    Shown on screen so two players can confirm they hold the same deck before
    starting, instead of finding out halfway through.
    """

    digest = _fnv1a("\x1f".join(sorted({key for key in keys if key})))
    return f"{digest:08X}"[:6]


def deck_seed(options: Sequence[Any], fingerprint: str) -> int:
    """Same options plus same deck means same seed, and nothing else does."""

    parts = [str(option) for option in options] + [str(fingerprint or "")]
    return _fnv1a("\x1f".join(parts))


def build_deck(works: Sequence[CharadeWork], seed: int, size: int = 0) -> list[CharadeWork]:
    """Deterministic order for a set of works.

    A Fisher-Yates shuffle driven by the LCG above: given the same works and the
    same seed it returns the same order on any platform. Works are sorted by key
    first so the caller's ordering cannot leak into the result.
    """

    ordered = sorted(works, key=lambda work: work.key)
    state = seed & _MASK32
    for index in range(len(ordered) - 1, 0, -1):
        state = (_LCG_MULTIPLIER * state + _LCG_INCREMENT) & _MASK32
        swap = state % (index + 1)
        ordered[index], ordered[swap] = ordered[swap], ordered[index]
    return ordered[:size] if size > 0 else ordered


def playable_difficulties(counts: Mapping[str, int]) -> list[str]:
    """Categories with enough works to be offered at all.

    A category below the minimum is withheld rather than offered and then made
    to repeat the same six titles all night.
    """

    return [name for name in DIFFICULTIES if counts.get(name, 0) >= MIN_PER_DIFFICULTY]


def deck_is_playable(total_eligible: int, counts: Mapping[str, int]) -> bool:
    return total_eligible >= MIN_ELIGIBLE_WORKS and bool(playable_difficulties(counts))


def _fnv1a(text: str) -> int:
    digest = _FNV_OFFSET
    for byte in text.encode("utf-8"):
        digest ^= byte
        digest = (digest * _FNV_PRIME) & _MASK32
    return digest


__all__ = [
    "DIFFICULTIES",
    "EASY",
    "FAMOUS_ABOVE_VOTES",
    "HARD",
    "MEDIUM",
    "MEDIUM_HIGH",
    "MIN_ELIGIBLE_WORKS",
    "MIN_PER_DIFFICULTY",
    "OBSCURE_BELOW_VOTES",
    "TIMER_OPTIONS",
    "CharadeWork",
    "build_deck",
    "deck_fingerprint",
    "deck_is_playable",
    "deck_seed",
    "normalize_title",
    "playable_difficulties",
    "playable_title",
    "resolve_difficulty",
    "suggest_difficulty",
    "work_key",
]
