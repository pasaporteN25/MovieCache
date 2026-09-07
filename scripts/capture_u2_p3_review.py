"""Render P.3 with reference titles in an isolated, temporary test catalogue."""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests.browser.test_ui_browser import BrowserInterfaceTests  # noqa: E402

TITLES = (
    ("City of Angels", "1998"),
    ("Let Me In", "2010"),
    ("Amores perros", "2000"),
    ("Antichrist", "2009"),
    ("Millennium Actress", "2001"),
    ("Lost Highway", "1997"),
    ("Back to the Future III", "1990"),
    ("12 Years a Slave", "2013"),
    ("The Mummy", "1999"),
    ("Chappie", "2015"),
    ("Fahrenheit 11/9", "2018"),
    ("X-Men", "2000"),
    ("Come and See", "1985"),
    ("Night Moves", "2013"),
    ("District 9", "2009"),
    ("The Killing of a Sacred Deer", "2017"),
    ("La insoportable levedad del ser", "1988"),
    ("El asesinato de Jesse James por el cobarde Robert Ford", "2007"),
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default="docs/design/u2-p3-evidence")
    args = parser.parse_args()
    output = ROOT / args.output_dir
    output.mkdir(exist_ok=True)
    BrowserInterfaceTests.setUpClass()
    try:
        page = BrowserInterfaceTests.context.new_page()
        page.emulate_media(reduced_motion="reduce")

        def fixture(route) -> None:
            response = route.fetch()
            payload = response.json()
            base = payload["items"][0]
            entries = [
                {
                    "key": f"p3-{i}",
                    "origin": {"kind": "catalog"},
                    "item": {
                        **base,
                        "id": f"p3-{i}",
                        "title": title,
                        "year": year,
                        "description": "",
                        "wikipedia_extract": "",
                        "directors": [],
                        "genres": [],
                    },
                }
                for i, (title, year) in enumerate(TITLES)
            ]
            home = payload.get("home") or {}
            home["featured"] = entries[:6]
            home["sections"] = [
                {"id": f"p3-bay-{i}", "title": label, "items": entries[i * 6 : (i + 1) * 6]}
                for i, label in enumerate(
                    (
                        "Disponible esta noche",
                        "Tu archivo pide memoria",
                        "Una ruta por cine de suspenso",
                    )
                )
            ]
            payload["home"] = home
            route.fulfill(response=response, json=payload)

        page.route("**/api/items?*", fixture)
        BrowserInterfaceTests._open_and_wait_for_catalog(page)
        page.locator(".vhs-spine-title").first.wait_for()
        page.evaluate("document.fonts.ready")
        for width, height in ((1280, 720), (1440, 900), (1920, 1080), (390, 844), (320, 740)):
            page.set_viewport_size({"width": width, "height": height})
            page.locator("#homeFurniture").screenshot(path=str(output / f"furniture-{width}.png"))
            assert not page.evaluate("document.documentElement.scrollWidth > innerWidth + 1")
            assert page.locator(".vhs-spine-title").evaluate_all(
                "els => els.every(el => el.scrollWidth <= el.clientWidth + 1 "
                "&& el.scrollHeight <= el.clientHeight + 1)"
            ), f"Reference title clipped at {width}px"
            if width < 861:
                page.evaluate("""() => {
                    const furniture = document.querySelector('#homeFurniture');
                    const header = document.querySelector('.app-header');
                    document.querySelectorAll('.home-shelf-rail').forEach(el => el.scrollLeft = 0);
                    window.scrollTo(0, furniture.getBoundingClientRect().top + scrollY
                        - header.getBoundingClientRect().height - 16);
                }""")
                page.screenshot(path=str(output / f"mobile-{width}.png"))
            if width == 1440:
                page.locator('[data-home-section="p3-bay-0"] .home-shelf-rail').screenshot(
                    path=str(output / "spines-closeup.png")
                )
                page.locator(".vhs-spine").nth(17).focus()
                page.locator(".vhs-spine").nth(17).scroll_into_view_if_needed()
                page.locator("#homeFurniture").screenshot(
                    path=str(output / "long-titles-focus.png")
                )
                page.locator("#homeSections").evaluate("el => el.scrollLeft = 0")
        print(
            page.locator(".vhs-spine-title").evaluate_all(
                "els => els.map(el => ({title: el.textContent, width: el.clientWidth, "
                "scrollWidth: el.scrollWidth, height: el.clientHeight, "
                "scrollHeight: el.scrollHeight}))"
            )
        )
    finally:
        BrowserInterfaceTests.tearDownClass()


if __name__ == "__main__":
    main()
