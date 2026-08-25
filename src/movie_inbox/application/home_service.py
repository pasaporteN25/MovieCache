"""Deterministic, explainable programming for the authenticated home view."""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from datetime import date
from typing import Any

from movie_inbox.domain.catalog import catalog_membership, external_urls, title_match_key
from movie_inbox.domain.collections import CuratedCollection
from movie_inbox.domain.normalization import normalize_bool, normalize_rating
from movie_inbox.domain.releases import normalize_release_dates

HOME_SECTION_LIMIT = 6
HOME_SECTION_COUNT = 5
HOME_FEATURED_LIMIT = 4
_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class EditorialHomeService:
    """Build a stable daily home payload without persisting recommendation state."""

    def build(
        self,
        user_id: str,
        local_date: str,
        catalog_items: Sequence[Mapping[str, Any]],
        followed_collections: Sequence[CuratedCollection] = (),
        *,
        warnings: Sequence[str] = (),
    ) -> dict[str, Any]:
        day = self.validate_date(local_date)
        catalog = [dict(item) for item in catalog_items]
        seed = f"{user_id}|{day}"
        used_ids: set[str] = set()

        featured = self._featured(catalog, seed, used_ids)
        sections: list[dict[str, Any]] = []

        # Reserve anniversary works before other programs, then present the
        # small, date-specific shelf at the end of the daily lineup.
        anniversary = self._anniversary_section(catalog, day, seed, used_ids)

        available = self._available_section(catalog, seed, used_ids)
        if available:
            sections.append(available)

        followed = self._followed_section(followed_collections, catalog, seed)
        if followed:
            sections.append(followed)

        memory = self._memory_section(catalog, seed, used_ids)
        if memory:
            sections.append(memory)

        route = self._route_section(catalog, seed, used_ids)
        if route:
            sections.append(route)

        if len(sections) < HOME_SECTION_COUNT and not route:
            recent = self._recent_section(catalog, used_ids)
            if recent:
                sections.append(recent)

        if anniversary:
            sections.append(anniversary)

        return {
            "generated_for": day,
            "featured": featured,
            # Temporary compatibility for clients that still expect one hero entry.
            "hero": featured[0] if featured else None,
            "sections": sections[:HOME_SECTION_COUNT],
            "warnings": list(dict.fromkeys(str(value) for value in warnings if str(value))),
            "limits": {
                "section_items": HOME_SECTION_LIMIT,
                "sections": HOME_SECTION_COUNT,
                "featured_items": HOME_FEATURED_LIMIT,
            },
        }

    @staticmethod
    def validate_date(value: str) -> str:
        requested = str(value or "").strip()
        if not _DATE_PATTERN.fullmatch(requested):
            raise ValueError("invalid_home_date")
        try:
            parsed = date.fromisoformat(requested)
        except ValueError as error:
            raise ValueError("invalid_home_date") from error
        if parsed.isoformat() != requested:
            raise ValueError("invalid_home_date")
        return requested

    @staticmethod
    def featured_snapshot(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
        """Keep only stable catalog references and the reason shown that day."""
        featured = payload.get("featured")
        if not isinstance(featured, list):
            return []
        snapshot: list[dict[str, Any]] = []
        for entry in featured[:HOME_FEATURED_LIMIT]:
            if not isinstance(entry, Mapping):
                continue
            item = entry.get("item")
            origin = entry.get("origin")
            reason = entry.get("reason")
            if not isinstance(item, Mapping) or not isinstance(origin, Mapping):
                continue
            item_id = str(origin.get("item_id") or item.get("id") or "").strip()
            if not item_id:
                continue
            snapshot.append(
                {
                    "item_id": item_id,
                    "reason": {
                        key: str((reason or {}).get(key) or "")
                        for key in ("code", "label", "detail")
                    }
                    if isinstance(reason, Mapping)
                    else {},
                }
            )
        return snapshot

    @staticmethod
    def restore_featured_snapshot(
        snapshot: Sequence[Mapping[str, Any]],
        catalog_items: Sequence[Mapping[str, Any]],
    ) -> list[dict[str, Any]]:
        """Hydrate a saved order with current catalog metadata and availability."""
        by_id = {
            str(item.get("id") or ""): item for item in catalog_items if str(item.get("id") or "")
        }
        restored: list[dict[str, Any]] = []
        seen: set[str] = set()
        for row in snapshot[:HOME_FEATURED_LIMIT]:
            item_id = str(row.get("item_id") or "").strip()
            item = by_id.get(item_id)
            if item is None or item_id in seen:
                continue
            raw_reason = row.get("reason")
            reason = raw_reason if isinstance(raw_reason, Mapping) else {}
            restored.append(
                _catalog_entry(
                    item,
                    {key: str(reason.get(key) or "") for key in ("code", "label", "detail")},
                )
            )
            seen.add(item_id)
        return restored

    def _featured(
        self,
        catalog: list[dict[str, Any]],
        seed: str,
        used_ids: set[str],
    ) -> list[dict[str, Any]]:
        available = [item for item in catalog if normalize_bool(item.get("en_catalogo"))]
        pending = [item for item in available if str(item.get("status") or "") != "watched"]
        illustrated = [
            item for item in available if item.get("backdrop_image") or item.get("page_image")
        ]
        if not illustrated:
            return []
        pending_ids = {_catalog_key(item) for item in pending}
        pending_illustrated = [item for item in illustrated if _catalog_key(item) in pending_ids]
        revisit_illustrated = [
            item for item in illustrated if _catalog_key(item) not in pending_ids
        ]
        selected = (
            self._stable_order(pending_illustrated, f"{seed}|featured|pending", _catalog_key)
            + self._stable_order(revisit_illustrated, f"{seed}|featured|revisit", _catalog_key)
        )[:HOME_FEATURED_LIMIT]
        entries: list[dict[str, Any]] = []
        for item in selected:
            item_key = _catalog_key(item)
            used_ids.add(item_key)
            if item_key in pending_ids:
                reason = _reason(
                    "available_pending",
                    "Disponible y pendiente",
                    "Está en tu biblioteca física y todavía no la marcaste como vista.",
                )
            else:
                reason = _reason(
                    "available_revisit",
                    "Disponible en tu archivo",
                    "Esta obra sigue disponible para volver a encontrarla esta noche.",
                )
            entries.append(_catalog_entry(item, reason))
        return entries

    def _available_section(
        self,
        catalog: list[dict[str, Any]],
        seed: str,
        used_ids: set[str],
    ) -> dict[str, Any] | None:
        candidates = [
            item
            for item in catalog
            if normalize_bool(item.get("en_catalogo"))
            and str(item.get("status") or "") != "watched"
            and _catalog_key(item) not in used_ids
        ]
        selected = self._take(candidates, f"{seed}|available", _catalog_key)
        if not selected:
            return None
        entries = []
        for item in selected:
            used_ids.add(_catalog_key(item))
            entries.append(
                _catalog_entry(
                    item,
                    _reason(
                        "available_pending",
                        "Lista para ver",
                        "El inventario confirma que está disponible y sigue pendiente.",
                    ),
                )
            )
        return _section(
            "available",
            "Para ver ahora",
            "Disponible esta noche",
            "Pendientes que tu biblioteca física confirma como disponibles.",
            {
                "kind": "catalog",
                "label": "Ver colección",
                "filters": {"status": ["to_watch"], "availability": ["available"]},
            },
            entries,
        )

    def _anniversary_section(
        self,
        catalog: list[dict[str, Any]],
        local_date: str,
        seed: str,
        used_ids: set[str],
    ) -> dict[str, Any] | None:
        day = date.fromisoformat(local_date)
        candidates: list[tuple[dict[str, Any], dict[str, Any]]] = []
        for item in catalog:
            if _catalog_key(item) in used_ids:
                continue
            release = _anniversary_release(item, day)
            if release:
                candidates.append((item, release))
        selected = self._take(candidates, f"{seed}|anniversary", lambda row: _catalog_key(row[0]))
        if not selected:
            return None
        entries: list[dict[str, Any]] = []
        for item, release in selected:
            used_ids.add(_catalog_key(item))
            release_day = date.fromisoformat(str(release["date"]))
            elapsed = max(0, day.year - release_day.year)
            elapsed_label = f"hace {elapsed} año" if elapsed == 1 else f"hace {elapsed} años"
            if elapsed == 0:
                elapsed_label = "hoy"
            entries.append(
                _catalog_entry(
                    item,
                    _reason(
                        "release_anniversary",
                        f"Estreno del {_spanish_day_month(release_day)}",
                        f"Su fecha de estreno registrada fue {elapsed_label}.",
                    ),
                )
            )
        return _section(
            "anniversary",
            "Efemérides del archivo",
            "Estrenadas un día como hoy",
            "Obras de tu catálogo con una fecha de estreno completa para esta jornada.",
            {
                "kind": "catalog",
                "label": "Ver fichas",
                "filters": {"release_day": [day.strftime("%m-%d")]},
            },
            entries,
        )

    def _followed_section(
        self,
        collections: Sequence[CuratedCollection],
        catalog: list[dict[str, Any]],
        seed: str,
    ) -> dict[str, Any] | None:
        candidates: list[tuple[CuratedCollection, Any]] = []
        work_keys: set[str] = set()
        for collection in collections:
            if not collection.followed:
                continue
            for entry in collection.items:
                if catalog_membership(entry.item, catalog)["state"] != "missing":
                    continue
                work_key = _work_key(entry.item)
                if work_key in work_keys:
                    continue
                work_keys.add(work_key)
                candidates.append((collection, entry))
        selected = self._take(
            candidates,
            f"{seed}|followed",
            lambda row: f"{row[0].id}:{row[1].id}",
        )
        if not selected:
            return None
        entries = [
            {
                "key": f"collection:{collection.id}:{entry.id}",
                "origin": {
                    "kind": "collection",
                    "collection_id": collection.id,
                    "collection_item_id": entry.id,
                    "collection_title": collection.title,
                },
                "item": dict(entry.item),
                "reason": _reason(
                    "followed_collection",
                    f"En {collection.title}",
                    "Seguís esta colección y la obra todavía no está en tu catálogo personal.",
                ),
            }
            for collection, entry in selected
        ]
        return _section(
            "followed",
            "Desde el Club",
            "De tus colecciones",
            "Obras que esperan en estantes que elegiste seguir.",
            {"kind": "club", "label": "Abrir Club"},
            entries,
        )

    def _memory_section(
        self,
        catalog: list[dict[str, Any]],
        seed: str,
        used_ids: set[str],
    ) -> dict[str, Any] | None:
        candidates = [
            item
            for item in catalog
            if str(item.get("status") or "") == "watched"
            and (
                normalize_rating(item.get("rating")) == 0
                or not str(item.get("review") or "").strip()
            )
            and _catalog_key(item) not in used_ids
        ]
        selected = self._take(candidates, f"{seed}|memory", _catalog_key)
        if not selected:
            return None
        entries = []
        for item in selected:
            used_ids.add(_catalog_key(item))
            missing_rating = normalize_rating(item.get("rating")) == 0
            missing_review = not str(item.get("review") or "").strip()
            if missing_rating and missing_review:
                reason = _reason(
                    "watched_without_record",
                    "Vista, sin registro",
                    "La marcaste como vista pero todavía no tiene puntaje ni review.",
                )
            elif missing_rating:
                reason = _reason(
                    "watched_without_rating",
                    "Vista, sin puntuar",
                    "Tu review está guardada; falta sumar un puntaje.",
                )
            else:
                reason = _reason(
                    "watched_without_review",
                    "Vista, sin review",
                    "Ya tiene puntaje; falta registrar qué te dejó.",
                )
            entries.append(_catalog_entry(item, reason))
        return _section(
            "memory",
            "Memoria personal",
            "Tu archivo pide memoria",
            "Obras vistas cuyo recuerdo todavía puede completarse.",
            {
                "kind": "catalog",
                "label": "Ver fichas",
                "filters": {
                    "status": ["watched"],
                    "record": ["unrated", "unreviewed"],
                },
            },
            entries,
        )

    def _route_section(
        self,
        catalog: list[dict[str, Any]],
        seed: str,
        used_ids: set[str],
    ) -> dict[str, Any] | None:
        available = [item for item in catalog if _catalog_key(item) not in used_ids]
        routes = _routes(available)
        if not routes:
            return None
        route = self._stable_order(routes, f"{seed}|route", lambda row: row["key"])[0]
        selected = self._take(route["items"], f"{seed}|route:{route['key']}", _catalog_key)
        if len(selected) < 3:
            return None
        entries = []
        for item in selected:
            used_ids.add(_catalog_key(item))
            entries.append(
                _catalog_entry(
                    item,
                    _reason(route["reason_code"], route["reason_label"], route["reason_detail"]),
                )
            )
        return _section(
            "route",
            route["eyebrow"],
            route["title"],
            route["description"],
            {
                "kind": "catalog",
                "label": "Explorar colección",
                "filters": dict(route["filters"]),
            },
            entries,
        )

    @staticmethod
    def _recent_section(
        catalog: list[dict[str, Any]],
        used_ids: set[str],
    ) -> dict[str, Any] | None:
        remaining = [item for item in catalog if _catalog_key(item) not in used_ids]
        selected = sorted(
            remaining,
            key=lambda item: (str(item.get("added_at") or ""), _catalog_key(item)),
            reverse=True,
        )[:HOME_SECTION_LIMIT]
        if not selected:
            return None
        entries = [
            _catalog_entry(
                item,
                _reason(
                    "recently_added",
                    "Agregada recientemente",
                    "Es una de las incorporaciones más nuevas de tu catálogo personal.",
                ),
            )
            for item in selected
        ]
        return _section(
            "recent",
            "Nuevos ingresos",
            "Recién llegadas",
            "Las incorporaciones más recientes de tu archivo.",
            {
                "kind": "catalog",
                "label": "Ver colección",
                "filters": {"sort": "added-desc"},
            },
            entries,
        )

    def _take(
        self,
        values: Iterable[Any],
        seed: str,
        identity: Callable[[Any], str],
    ) -> list[Any]:
        return self._stable_order(values, seed, identity)[:HOME_SECTION_LIMIT]

    @staticmethod
    def _stable_order(
        values: Iterable[Any],
        seed: str,
        identity: Callable[[Any], str],
    ) -> list[Any]:
        return sorted(
            values,
            key=lambda value: (
                hashlib.sha256(f"{seed}|{identity(value)}".encode()).hexdigest(),
                identity(value),
            ),
        )


def home_image_items(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Flatten only the works shown by the home payload for image warming."""
    rows: list[dict[str, Any]] = []
    featured = payload.get("featured")
    if isinstance(featured, list) and featured:
        for entry in featured:
            if isinstance(entry, Mapping) and isinstance(entry.get("item"), Mapping):
                rows.append(dict(entry["item"]))
    else:
        hero = payload.get("hero")
        if isinstance(hero, Mapping) and isinstance(hero.get("item"), Mapping):
            rows.append(dict(hero["item"]))
    sections = payload.get("sections")
    if not isinstance(sections, list):
        return rows
    for section in sections:
        if not isinstance(section, Mapping) or not isinstance(section.get("items"), list):
            continue
        for entry in section["items"]:
            if isinstance(entry, Mapping) and isinstance(entry.get("item"), Mapping):
                rows.append(dict(entry["item"]))
    return rows


def _catalog_entry(item: Mapping[str, Any], reason: Mapping[str, str]) -> dict[str, Any]:
    key = _catalog_key(item)
    return {
        "key": f"catalog:{key}",
        "origin": {"kind": "catalog", "item_id": str(item.get("id") or "")},
        "item": dict(item),
        "reason": dict(reason),
    }


def _section(
    section_id: str,
    eyebrow: str,
    title: str,
    description: str,
    action: Mapping[str, Any],
    items: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "id": section_id,
        "eyebrow": eyebrow,
        "title": title,
        "description": description,
        "action": dict(action),
        "items": items,
    }


def _reason(code: str, label: str, detail: str) -> dict[str, str]:
    return {"code": code, "label": label, "detail": detail}


def _catalog_key(item: Mapping[str, Any]) -> str:
    return str(item.get("id") or _work_key(item))


def _work_key(item: Mapping[str, Any]) -> str:
    wikidata = str(item.get("wikidata_id") or "").strip().casefold()
    if wikidata:
        return f"wikidata:{wikidata}"
    urls = sorted(external_urls(item))
    if urls:
        return f"url:{urls[0]}"
    item_id = str(item.get("id") or "").strip().casefold()
    if item_id:
        return f"id:{item_id}"
    title = title_match_key(str(item.get("title") or item.get("original_title") or ""))
    return ":".join(
        (
            "title",
            title,
            str(item.get("year") or "").strip(),
            str(item.get("kind") or "").strip().casefold(),
        )
    )


def _routes(items: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    directors: dict[str, list[dict[str, Any]]] = defaultdict(list)
    genres: dict[str, list[dict[str, Any]]] = defaultdict(list)
    decades: dict[int, list[dict[str, Any]]] = defaultdict(list)
    labels: dict[str, str] = {}
    for item in items:
        for director in _list_values(item.get("directors")):
            key = director.casefold()
            labels.setdefault(f"director:{key}", director)
            directors[key].append(item)
        for genre in _list_values(item.get("genres")):
            key = genre.casefold()
            labels.setdefault(f"genre:{key}", genre)
            genres[key].append(item)
        year = _year(item.get("year"))
        if year:
            decades[(year // 10) * 10].append(item)

    routes: list[dict[str, Any]] = []
    for key, grouped in directors.items():
        if len(grouped) < 3:
            continue
        label = labels[f"director:{key}"]
        routes.append(
            {
                "key": f"director:{key}",
                "eyebrow": "Programa de autor",
                "title": f"Una ruta por {label}",
                "description": f"Una línea de {label} dentro de tu propio archivo.",
                "reason_code": "shared_director",
                "reason_label": f"Dirección: {label}",
                "reason_detail": f"Forma parte de una ruta de obras dirigidas por {label}.",
                "filters": {"director": [label]},
                "items": grouped,
            }
        )
    for key, grouped in genres.items():
        if len(grouped) < 3:
            continue
        label = labels[f"genre:{key}"]
        routes.append(
            {
                "key": f"genre:{key}",
                "eyebrow": "Afinidad de género",
                "title": f"Una ruta por {label}",
                "description": f"Una selección de {label} que ya vive en tu catálogo.",
                "reason_code": "shared_genre",
                "reason_label": f"Género: {label}",
                "reason_detail": f"Comparte el género {label} con el resto de esta ruta.",
                "filters": {"genre": [label]},
                "items": grouped,
            }
        )
    for decade, grouped in decades.items():
        if len(grouped) < 3:
            continue
        routes.append(
            {
                "key": f"decade:{decade}",
                "eyebrow": "Sesión de época",
                "title": f"Una ruta por los años {decade}",
                "description": f"Obras de los años {decade} conservadas en tu archivo.",
                "reason_code": "shared_decade",
                "reason_label": f"De los años {decade}",
                "reason_detail": f"Fue estrenada durante la década de {decade}.",
                "filters": {"decade": [str(decade)]},
                "items": grouped,
            }
        )
    return routes


def _list_values(value: Any) -> list[str]:
    if isinstance(value, str):
        values = [part.strip() for part in value.split(",")]
    elif isinstance(value, (list, tuple, set)):
        values = [str(part).strip() for part in value]
    else:
        values = []
    return list(dict.fromkeys(part for part in values if part))


def _year(value: Any) -> int:
    match = re.search(r"\b(18\d{2}|19\d{2}|20\d{2}|21\d{2})\b", str(value or ""))
    return int(match.group(1)) if match else 0


def _anniversary_release(item: Mapping[str, Any], day: date) -> dict[str, Any] | None:
    for release in normalize_release_dates(item.get("release_dates")):
        if release["precision"] != "day":
            continue
        release_day = date.fromisoformat(str(release["date"]))
        if release_day.year <= day.year and (release_day.month, release_day.day) == (
            day.month,
            day.day,
        ):
            return release
    return None


def _spanish_day_month(value: date) -> str:
    months = (
        "enero",
        "febrero",
        "marzo",
        "abril",
        "mayo",
        "junio",
        "julio",
        "agosto",
        "septiembre",
        "octubre",
        "noviembre",
        "diciembre",
    )
    return f"{value.day} de {months[value.month - 1]}"
