"""Versioned starter collections bundled with Movie Inbox."""

from __future__ import annotations

from datetime import UTC, datetime
from urllib.parse import quote

from movie_inbox.domain.collections import (
    CollectionItem,
    CuratedCollection,
    normalize_collection_item,
)

AKIRA_KUROSAWA_SEED_KEY = "starter-akira-kurosawa-v1"

_AKIRA_KUROSAWA_FILMS = (
    ("Sanshiro Sugata", "Sugata Sanshiro", "1943", "Sanshiro Sugata"),
    ("The Most Beautiful", "Ichiban utsukushiku", "1944", "The Most Beautiful"),
    ("Sanshiro Sugata Part II", "Zoku Sugata Sanshiro", "1945", "Sanshiro Sugata Part II"),
    (
        "The Men Who Tread on the Tiger's Tail",
        "Tora no o wo fumu otokotachi",
        "1945",
        "The Men Who Tread on the Tiger's Tail",
    ),
    ("Those Who Make Tomorrow", "Asu o tsukuru hitobito", "1946", "Those Who Make Tomorrow"),
    ("No Regrets for Our Youth", "Waga seishun ni kuinashi", "1946", "No Regrets for Our Youth"),
    ("One Wonderful Sunday", "Subarashiki nichiyobi", "1947", "One Wonderful Sunday"),
    ("Drunken Angel", "Yoidore tenshi", "1948", "Drunken Angel"),
    ("The Quiet Duel", "Shizukanaru ketto", "1949", "The Quiet Duel"),
    ("Stray Dog", "Nora inu", "1949", "Stray Dog (film)"),
    ("Scandal", "Shubun", "1950", "Scandal (1950 film)"),
    ("Rashomon", "Rashomon", "1950", "Rashomon"),
    ("The Idiot", "Hakuchi", "1951", "The Idiot (1951 film)"),
    ("Ikiru", "Ikiru", "1952", "Ikiru"),
    ("Seven Samurai", "Shichinin no samurai", "1954", "Seven Samurai"),
    ("I Live in Fear", "Ikimono no kiroku", "1955", "I Live in Fear"),
    ("Throne of Blood", "Kumonosu-jo", "1957", "Throne of Blood"),
    ("The Lower Depths", "Donzoko", "1957", "The Lower Depths (1957 film)"),
    ("The Hidden Fortress", "Kakushi toride no san akunin", "1958", "The Hidden Fortress"),
    ("The Bad Sleep Well", "Warui yatsu hodo yoku nemuru", "1960", "The Bad Sleep Well"),
    ("Yojimbo", "Yojinbo", "1961", "Yojimbo"),
    ("Sanjuro", "Tsubaki Sanjuro", "1962", "Sanjuro"),
    ("High and Low", "Tengoku to jigoku", "1963", "High and Low (1963 film)"),
    ("Red Beard", "Akahige", "1965", "Red Beard"),
    ("Dodes'ka-den", "Dodesukaden", "1970", "Dodes'ka-den"),
    ("Dersu Uzala", "Derusu Uzara", "1975", "Dersu Uzala (1975 film)"),
    ("Kagemusha", "Kagemusha", "1980", "Kagemusha"),
    ("Ran", "Ran", "1985", "Ran (film)"),
    ("Dreams", "Yume", "1990", "Dreams (1990 film)"),
    ("Rhapsody in August", "Hachigatsu no rapusodi", "1991", "Rhapsody in August"),
    ("Madadayo", "Madadayo", "1993", "Madadayo"),
)


def akira_kurosawa_collection(owner_user_id: str) -> CuratedCollection:
    now = datetime.now(UTC).isoformat()
    entries = []
    for position, (title, original_title, year, page) in enumerate(_AKIRA_KUROSAWA_FILMS):
        wikipedia_url = "https://en.wikipedia.org/wiki/" + quote(
            page.replace(" ", "_"), safe="()_-"
        )
        item = normalize_collection_item(
            {
                "url": wikipedia_url,
                "source": "wikipedia",
                "title": title,
                "original_title": original_title,
                "english_title": title,
                "year": year,
                "kind": "pelicula",
                "wikipedia_url": wikipedia_url,
                "wikipedia_title": page,
                "directors": ["Akira Kurosawa"],
            }
        )
        entries.append(CollectionItem(str(item["id"]), position, item))
    return CuratedCollection(
        id="starter-akira-kurosawa",
        slug="akira-kurosawa",
        title="Akira Kurosawa",
        description=(
            "Filmografia como director, incluida la obra codirigida Those Who Make Tomorrow. "
            "Una coleccion inicial para probar seguimiento y copia selectiva."
        ),
        owner_user_id=owner_user_id,
        visibility="published",
        source_kind="builtin",
        source_url="https://en.wikipedia.org/wiki/List_of_works_by_Akira_Kurosawa",
        source_label="Wikipedia - List of works by Akira Kurosawa",
        built_in=True,
        version=1,
        created_at=now,
        updated_at=now,
        items=tuple(entries),
    )
