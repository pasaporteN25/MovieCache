"""Capture isolated P.3/P.4 proposals; never change application styles or data."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.capture_u2_p3_review import TITLES  # noqa: E402
from tests.browser.test_ui_browser import BrowserInterfaceTests  # noqa: E402


def fixture(route) -> None:
    """Use the P.3 review's reference titles and identical three-bay catalogue."""
    response = route.fetch()
    payload = response.json()
    base = payload["items"][0]
    entries = [
        {
            "key": f"p3-{index}",
            "origin": {"kind": "catalog"},
            "item": {
                **base,
                "id": f"p3-{index}",
                "title": title,
                "year": year,
                "description": "",
                "wikipedia_extract": "",
                "directors": [],
                "genres": [],
            },
        }
        for index, (title, year) in enumerate(TITLES)
    ]
    home = payload.get("home") or {}
    home["featured"] = entries[:6]
    home["sections"] = [
        {"id": f"p3-bay-{index}", "title": label, "items": entries[index * 6 : (index + 1) * 6]}
        for index, label in enumerate(
            (
                "Disponible esta noche",
                "Tu archivo pide memoria",
                "Una ruta por cine de suspenso",
            )
        )
    ]
    payload["home"] = home
    route.fulfill(response=response, json=payload)


def spine_geometry(page) -> list[dict]:
    return page.locator(".home-shelf-tape").evaluate_all(
        """nodes => {
            const furniture = document.querySelector('#homeFurniture').getBoundingClientRect();
            return nodes.map(node => {
                const box = node.getBoundingClientRect();
                return {
                    key: node.dataset.entryKey,
                    width: box.width,
                    height: box.height,
                    bottom: box.bottom - furniture.top,
                };
            });
        }"""
    )


def compare_geometry(before: list[dict], after: list[dict]) -> list[dict]:
    assert len(before) == len(after), "Proposal changed the number of spines"
    result = []
    for baseline, proposal in zip(before, after, strict=True):
        assert baseline["key"] == proposal["key"], "Proposal changed spine order"
        result.append(
            {
                "key": baseline["key"],
                "before": baseline,
                "after": proposal,
                "same_width": abs(proposal["width"] - baseline["width"]) <= 1,
                "same_base": abs(proposal["bottom"] - baseline["bottom"]) <= 1,
                "taller": proposal["height"] > baseline["height"] + 1,
            }
        )
    return result


def main() -> None:
    stylesheet = ROOT / "docs/design/u2-p34-proposals.css"
    fonts = ROOT / "docs/design/u2-p-fonts"
    plaque = ROOT / "docs/design/u2-p-plaque-blank-v1.png"
    font_names = ("BebasNeue-Regular.ttf", "Oswald-Variable.ttf")
    for required in (stylesheet, plaque, *(fonts / name for name in font_names)):
        if not required.is_file():
            raise FileNotFoundError(f"Required proposal asset missing: {required}")

    output = ROOT / "docs/design/u2-p34-evidence"
    output.mkdir(exist_ok=True)
    report = []
    BrowserInterfaceTests.setUpClass()
    try:
        for width, height in ((1440, 900), (1920, 1080)):
            page = BrowserInterfaceTests.context.new_page()
            try:
                page.set_viewport_size({"width": width, "height": height})
                page.emulate_media(reduced_motion="reduce")
                page.route("**/api/items?*", fixture)
                page.route(
                    "**/proposal-assets/plaque.png",
                    lambda route: route.fulfill(
                        status=200, content_type="image/png", path=str(plaque)
                    ),
                )
                for name in font_names:
                    page.route(
                        f"**/proposal-fonts/{name}",
                        lambda route, _request, path=fonts / name: route.fulfill(
                            status=200, content_type="font/ttf", path=str(path)
                        ),
                    )
                BrowserInterfaceTests._open_and_wait_for_catalog(page)
                page.locator(".vhs-spine-title").first.wait_for()
                page.evaluate("document.fonts.ready")
                furniture = page.locator("#homeFurniture")
                before = spine_geometry(page)
                if width == 1440:
                    furniture.screenshot(path=str(output / "before-1440.png"))

                page.add_style_tag(path=str(stylesheet))
                for proposal in ("a", "b"):
                    page.evaluate(
                        "proposal => { document.body.dataset.spineProposal = proposal; }",
                        proposal,
                    )
                    page.evaluate("document.fonts.ready")
                    page.locator("#homeSections").evaluate("node => { node.scrollLeft = 0; }")
                    furniture.screenshot(path=str(output / f"{proposal}-{width}.png"))
                    if width == 1440:
                        page.locator('[data-home-section="p3-bay-0"]').screenshot(
                            path=str(output / f"{proposal}-closeup.png")
                        )
                    report.append(
                        {
                            "viewport": {"width": width, "height": height},
                            "proposal": proposal,
                            "spines": compare_geometry(before, spine_geometry(page)),
                        }
                    )
            finally:
                page.close()
    finally:
        BrowserInterfaceTests.tearDownClass()

    print(json.dumps(report, ensure_ascii=False, indent=2))
    failures = [
        {"viewport": item["viewport"], "proposal": item["proposal"], **spine}
        for item in report
        for spine in item["spines"]
        if not (spine["same_width"] and spine["same_base"] and spine["taller"])
    ]
    assert not failures, f"Proposal geometry contract failed: {json.dumps(failures)}"


if __name__ == "__main__":
    main()
