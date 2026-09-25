"""HTML parsers keep their own state out of HTMLParser's namespace.

CPython 3.11.16 and 3.14.7 changed `HTMLParser.feed` to buffer its input in
`self._pending`, a list that `reset()` creates (gh-153030).
`FilmAffinityMetadataParser` already had a `self._pending` of its own -- a
string naming the field the next text fills -- and assigned it right after
`super().__init__()`. From those releases on, feeding that parser an empty body
raised `AttributeError: 'str' object has no attribute 'append'`: in CI, which
installs the newest patch release, and not on a machine still on 3.14.4.

A subclass shares its instance `__dict__` with the base class, and the base
keeps its parser state in underscore names that patch releases add to. These
tests keep every parser in the package out of that namespace, report the
collisions the running interpreter can see, and pin the case that broke.
"""

from __future__ import annotations

import importlib
import pkgutil
import unittest
from collections.abc import Iterator
from html.parser import HTMLParser
from unittest.mock import patch

import movie_inbox
from movie_inbox.external.filmaffinity import fetch_filmaffinity_metadata

# The documented extension points: overriding these is how HTMLParser is used.
_HOOKS = frozenset(
    {name for name in dir(HTMLParser) if name.startswith("handle_")} | {"unknown_decl"}
)


def _subclasses(cls: type[HTMLParser]) -> Iterator[type[HTMLParser]]:
    for subclass in cls.__subclasses__():
        yield subclass
        yield from _subclasses(subclass)


def _package_parsers() -> list[type[HTMLParser]]:
    for module in pkgutil.walk_packages(movie_inbox.__path__, "movie_inbox."):
        # A __main__ module runs the CLI when imported.
        if module.name.rsplit(".", 1)[-1] != "__main__":
            importlib.import_module(module.name)
    found = {cls for cls in _subclasses(HTMLParser) if cls.__module__.startswith("movie_inbox.")}
    return sorted(found, key=lambda cls: (cls.__module__, cls.__qualname__))


class HtmlParserNamespaceTests(unittest.TestCase):
    parsers: list[type[HTMLParser]]
    base_state: dict[str, object]

    @classmethod
    def setUpClass(cls) -> None:
        cls.parsers = _package_parsers()
        cls.base_state = vars(HTMLParser())

    def test_the_parsers_are_found(self) -> None:
        # Guards the discovery itself: finding nothing would pass every test below.
        names = {parser.__qualname__ for parser in self.parsers}
        self.assertLessEqual(
            {"FilmAffinityParser", "FilmAffinityMetadataParser", "MetadataParser"}, names
        )

    def test_no_parser_keeps_its_state_in_underscore_names(self) -> None:
        # The check that does not depend on which patch release runs it: any
        # underscore name may be the next one CPython adds.
        for parser_class in self.parsers:
            with self.subTest(parser=parser_class.__qualname__):
                own = set(vars(parser_class())) - set(self.base_state)
                self.assertEqual(sorted(name for name in own if name.startswith("_")), [])

    def test_no_parser_replaces_state_this_python_gives_the_base_class(self) -> None:
        # Public names collide too: 3.14 added `scripting`.
        for parser_class in self.parsers:
            with self.subTest(parser=parser_class.__qualname__):
                state = vars(parser_class())
                replaced = sorted(
                    name
                    for name, value in self.base_state.items()
                    if type(state.get(name)) is not type(value)
                )
                self.assertEqual(replaced, [])

    def test_no_parser_overrides_more_than_the_handler_hooks(self) -> None:
        for parser_class in self.parsers:
            with self.subTest(parser=parser_class.__qualname__):
                overridden = sorted(
                    name
                    for name in vars(parser_class)
                    if not name.startswith("__")
                    and (hasattr(HTMLParser, name) or name in self.base_state)
                    and name not in _HOOKS
                )
                self.assertEqual(overridden, [])


class EmptyBodyTests(unittest.TestCase):
    """An empty response is an ordinary answer, not a crash: the case that broke."""

    def test_every_parser_accepts_an_empty_body(self) -> None:
        for parser_class in _package_parsers():
            with self.subTest(parser=parser_class.__qualname__):
                parser_class().feed("")

    def test_an_empty_film_page_yields_no_metadata(self) -> None:
        # The path 0.8.0 already had: filling a work in from a FilmAffinity address.
        with patch("movie_inbox.external.filmaffinity.fetch_text", return_value=""):
            metadata = fetch_filmaffinity_metadata(
                "https://www.filmaffinity.com/es/film759533.html"
            )

        self.assertEqual(metadata, {})


if __name__ == "__main__":
    unittest.main()
