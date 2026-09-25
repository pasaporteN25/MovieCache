# ruff: noqa: E402, I001
"""Serve the real app against a disposable U4 fixture; no browser automation.

Run with .venv/Scripts/python.exe scripts/serve_u4_2c_review.py.
Only this review process replaces editorial data, never production modules.
"""

from __future__ import annotations

import json
import socket
import sys
import tempfile
from datetime import date
from pathlib import Path

import uvicorn
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from movie_inbox.application.auth_service import AuthService
from movie_inbox.domain.catalog import normalize_item
from movie_inbox.infrastructure.identity_repository import SqliteIdentityRepository
from movie_inbox.infrastructure.json_repository import JsonCatalogRepository
from movie_inbox.web.app import create_app
from movie_inbox.web.config import ViewerConfig


TITLES = [
    "Metropolis",
    "El faro de niebla",
    "Las calles recuerdan",
    "Ecos del invierno",
    "Bajo la superficie",
    "Tren fuera de hora",
    "La última función",
    "Órbitas de papel",
    "La habitación 27",
    "Verano en pausa",
    "Crónicas del puerto",
    "Luces de neón",
    "La noche perdida",
    "Sombras en la costa",
    "Cinta de recuerdos",
    "Punto ciego",
    "El archivo de las cosas que dejamos para después",
    "Más allá del último fotograma",
]

REVIEW_CASES = [
    ("populated", "Poblada"),
    ("sparse", "Títulos largos"),
    ("missing", "Sin imágenes"),
    ("broken", "Imagen fallida"),
    ("empty", "Vacía"),
    ("club", "Origen Club"),
    ("list-1", "1 obra"),
    ("list-6", "6 obras"),
    ("list-20", "20 obras"),
    ("list-100", "100 obras"),
]


def editorial(rows, day, mode):
    entries = [{"key": row["id"], "origin": {"kind": "catalog"}, "item": dict(row)} for row in rows]
    for entry in entries:
        if entry["item"]["id"] == "u4-demo-1":
            entry["item"].update(
                directors=["Dirección de muestra"],
                writers=["Guionista de muestra"],
                cast=["Intérprete de muestra A", "Intérprete de muestra B"],
                duration_minutes=104,
                backdrop_image="https://fixture.invalid/u4-metropolis.jpg",
                page_image="https://fixture.invalid/u4-metropolis.jpg",
            )
        if mode == "missing":
            entry["item"]["page_image"] = ""
            entry["item"]["backdrop_image"] = ""
        if mode == "broken":
            entry["item"]["page_image"] = "https://fixture.invalid/u4-broken.jpg"
            entry["item"]["backdrop_image"] = "https://fixture.invalid/u4-metropolis.jpg"
    sections = [
        {
            "id": f"u4-{n}",
            "title": title,
            "action": {"kind": "catalog", "label": "Ver colección", "filters": {}},
            "items": entries[n * 6 : (n + 1) * 6],
        }
        for n, title in enumerate(
            ["Disponible esta noche", "Tu archivo pide memoria", "Una ruta por cine"]
        )
    ]
    if mode == "sparse":
        sections = [
            {
                **sections[-1],
                "title": "Una ruta por historias que esperan una segunda mirada",
                "items": entries[-2:],
            }
        ]
    if mode.startswith("list-"):
        count = int(mode.split("-")[1])
        extended = [
            {
                "key": f"u5-stress-{index}",
                "origin": {"kind": "catalog"},
                "item": {
                    "id": f"u5-stress-{index}",
                    "title": (
                        f"Obra {index + 1:03d} — Crónicas del archivo: "
                        "una historia que merece volver a verse"
                    ),
                    "year": "2000",
                    "kind": "pelicula",
                    "description": (
                        "Datos sintéticos de escala, no obras del catálogo. "
                        "Sólo prueba de lista y selección."
                    ),
                },
            }
            for index in range(count)
        ]
        sections = [
            {
                "id": "u5-stress",
                "title": (
                    "Una selección de historias del archivo que esperan una segunda "
                    "mirada y una nueva conversación"
                ),
                "items": extended,
            },
            sections[0],
        ]
    if mode == "club":
        external = {
            "key": "club-demo",
            "origin": {
                "kind": "collection",
                "collection_title": "Colección de demostración",
                "collection_id": "demo",
            },
            "item": {
                "id": "club-demo",
                "title": "Obra externa de demostración",
                "description": "Ficha sintética del Club; no pertenece al catálogo personal.",
            },
        }
        sections = [{"id": "club-demo", "title": "Desde el Club", "items": [external]}]
    featured = entries[:6] if day == date.today().isoformat() else list(reversed(entries[:6]))
    return {
        "generated_for": day,
        "featured": [] if mode == "empty" else featured,
        "sections": [] if mode == "empty" else sections,
        "warnings": [],
        "limits": {"featured_items": 6},
    }


def main():
    with tempfile.TemporaryDirectory(prefix="movie-inbox-u4-review-") as temporary:
        root = Path(temporary)
        catalog = root / "catalog.json"
        items = [
            normalize_item(
                {
                    "id": f"u4-demo-{i}",
                    "title": title,
                    "year": "1927" if i == 0 else "" if i == 16 else str(2010 + i),
                    "kind": "pelicula",
                    "en_catalogo": i < 6,
                    "status": "watched" if 6 <= i < 12 else "to_watch",
                    "description": ""
                    if i == 0
                    else (
                        "Ficha sintética para comprobar el espacio de lectura y los "
                        "estados de la interfaz."
                    ),
                    "page_image": "https://fixture.invalid/u4-metropolis.jpg" if i == 0 else "",
                }
            )
            for i, title in enumerate(TITLES)
        ]
        JsonCatalogRepository(catalog, normalize_item).write(items)
        instance = root / "instance.db"
        AuthService(SqliteIdentityRepository(instance)).bootstrap_owner(
            "visual",
            "u4-review-only-password",
            catalog_name="U4 — datos de demostración",
            source_paths=[str(catalog)],
            write_path=str(catalog),
        )
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        config = ViewerConfig(
            patterns=[str(catalog)],
            title="Movie Inbox",
            write_json=str(catalog),
            image_cache=False,
            image_cache_dir=str(root / "images"),
            image_cache_max_bytes=1024,
            port=port,
            api_token="u4-review-token",
            instance_db=str(instance),
            member_catalog_dir=str(root / "members"),
            library_scheduler_poll_seconds=3600,
        )
        app = create_app(config)

        @app.middleware("http")
        async def review_fixture(request, call_next):
            if request.url.path == "/__review__":
                mode = request.query_params.get("case", "populated")
                if mode not in {entry[0] for entry in REVIEW_CASES}:
                    return Response(status_code=400)
                response = RedirectResponse("/", status_code=303)
                response.set_cookie("u4_case", mode, httponly=True, samesite="strict")
                return response
            if request.url.path == "/__review__.css":
                return Response(
                    (
                        ".u4-review-note{font:12px/1.5 monospace;padding:8px 32px;"
                        "color:#efd09b;background:#041219}.u4-review-note a{color:"
                        "#a4e3e9;margin-left:18px}"
                    ),
                    media_type="text/css",
                )
            if request.url.path == "/image-cache":
                if request.query_params.get("url") == "https://fixture.invalid/u4-metropolis.jpg":
                    return Response(
                        (
                            ROOT / "docs/design/u4-2b-integrated-junction-v1/metropolis-poster.jpg"
                        ).read_bytes(),
                        media_type="image/jpeg",
                    )
                return Response(status_code=404)
            response = await call_next(request)
            if response.status_code != 200:
                return response
            if request.url.path in {"/api/items", "/api/home"}:
                content = b"".join([chunk async for chunk in response.body_iterator])
                payload = json.loads(content)
                rows = (
                    payload["items"]
                    if request.url.path == "/api/items"
                    else [item.to_dict() for item in items]
                )
                day = (
                    request.query_params.get("home_date")
                    or request.query_params.get("date")
                    or date.today().isoformat()
                )
                home = editorial(rows, day, request.cookies.get("u4_case", "populated"))
                payload = {**payload, "home": home} if request.url.path == "/api/items" else home
                return JSONResponse(payload)
            if request.url.path == "/":
                content = b"".join([chunk async for chunk in response.body_iterator]).decode()
                if 'id="homeView"' in content:
                    banner = (
                        '<aside class="u4-review-note">U5 · Aplicación real con datos '
                        "de demostración. Listas extendidas: sólo prueba visual."
                    )
                    for mode, label in REVIEW_CASES:
                        banner += f'<a href="/__review__?case={mode}">{label}</a>'
                    banner += "</aside>"
                    content = content.replace(
                        "</head>", '<link rel="stylesheet" href="/__review__.css"></head>'
                    ).replace("<body>", "<body>" + banner)
                headers = {
                    k: v
                    for k, v in response.headers.items()
                    if k.lower() not in {"content-length", "content-type"}
                }
                return HTMLResponse(content, headers=headers)
            return response

        print(f"U4 real app review: http://127.0.0.1:{port}/", flush=True)
        print("Disposable login: visual / u4-review-only-password", flush=True)
        uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
