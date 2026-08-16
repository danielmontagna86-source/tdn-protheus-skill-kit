from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

KIT = Path(__file__).parents[1]
SCRIPT = KIT / "coletando-documentacao-tdn-protheus" / "scripts" / "locate_tdn_pages.py"


def load_module():
    if not SCRIPT.is_file():
        raise AssertionError(f"script ausente: {SCRIPT}")
    spec = importlib.util.spec_from_file_location("locate_tdn_pages", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(SCRIPT.parent))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
    return module


class FakeCollector:
    def __init__(self, batches: dict[tuple[int, int], dict]) -> None:
        self.batches = batches
        self.urls: list[str] = []

    def get_json(self, url: str) -> dict:
        self.urls.append(url)
        page_id = int(url.split("/content/")[1].split("/")[0])
        start = int(url.split("start=")[1])
        return self.batches[(page_id, start)]


class TDNLocatorTests(unittest.TestCase):
    def test_finds_titles_across_paginated_children_without_fetching_bodies(self) -> None:
        locator_module = load_module()
        collector = FakeCollector(
            {
                (1, 0): {
                    "results": [{"id": "11", "title": "Rotina MATA103"}],
                    "_links": {"next": "/rest/api/content/1/child/page?limit=1&start=1"},
                },
                (1, 1): {
                    "results": [{"id": "12", "title": "Ponto de Entrada SD1100I"}],
                    "_links": {},
                },
            }
        )

        result = locator_module.TDNPageLocator(collector, max_list_pages=2).locate(
            root_id=1, terms=["mata103", "sd1100i"], max_depth=1, max_candidates=10
        )

        self.assertTrue(result["complete"])
        self.assertEqual(result["list_pages_fetched"], 2)
        self.assertEqual([item["id"] for item in result["candidates"]], [11, 12])
        self.assertEqual(result["candidates"][0]["parent_id"], 1)
        self.assertEqual(result["candidates"][0]["depth"], 1)
        self.assertTrue(all("child/page" in url for url in collector.urls))

    def test_returns_partial_result_when_list_page_limit_is_reached(self) -> None:
        locator_module = load_module()
        collector = FakeCollector(
            {
                (1, 0): {
                    "results": [{"id": "11", "title": "MATA103"}],
                    "_links": {"next": "/rest/api/content/1/child/page?limit=1&start=1"},
                }
            }
        )

        result = locator_module.TDNPageLocator(collector, max_list_pages=1).locate(
            root_id=1, terms=["mata103"], max_depth=1, max_candidates=10
        )

        self.assertFalse(result["complete"])
        self.assertEqual(result["stop_reason"], "max-list-pages")
        self.assertTrue(result["next_cursor_available"])
        self.assertEqual([item["id"] for item in result["candidates"]], [11])

    def test_returns_partial_result_when_candidate_limit_is_reached(self) -> None:
        locator_module = load_module()
        collector = FakeCollector(
            {
                (1, 0): {
                    "results": [
                        {"id": "11", "title": "MATA103 A"},
                        {"id": "12", "title": "MATA103 B"},
                    ],
                    "_links": {},
                }
            }
        )

        result = locator_module.TDNPageLocator(collector, max_list_pages=2).locate(
            root_id=1, terms=["mata103"], max_depth=1, max_candidates=1
        )

        self.assertFalse(result["complete"])
        self.assertEqual(result["stop_reason"], "max-candidates")
        self.assertEqual([item["id"] for item in result["candidates"]], [11])

    def test_duration_limit_clips_the_delay_before_the_next_list_request(self) -> None:
        locator_module = load_module()
        collector = FakeCollector(
            {
                (1, 0): {
                    "results": [{"id": "11", "title": "MATA103"}],
                    "_links": {"next": "/rest/api/content/1/child/page?limit=1&start=1"},
                }
            }
        )
        clock = [0.0]

        def monotonic() -> float:
            return clock[0]

        def sleep(seconds: float) -> None:
            clock[0] += seconds

        try:
            locator = locator_module.TDNPageLocator(
                collector, max_list_pages=2, deadline=0.1, delay=1
            )
        except TypeError as error:
            self.fail(f"TDNPageLocator deve aceitar deadline e delay: {error}")
        with patch.object(locator_module.time, "monotonic", monotonic), patch.object(locator_module.time, "sleep", sleep):
            result = locator.locate(root_id=1, terms=["mata103"], max_depth=1, max_candidates=10)

        self.assertFalse(result["complete"])
        self.assertEqual(result["stop_reason"], "max-duration")
        self.assertLessEqual(clock[0], 0.1)
        self.assertEqual(len(collector.urls), 1)

    def test_fallback_pagination_restarts_the_offset_for_each_parent(self) -> None:
        locator_module = load_module()
        children = [{"id": str(index), "title": f"Página {index}"} for index in range(10, 60)]
        collector = FakeCollector(
            {
                (1, 0): {"results": [{"id": "2", "title": "Subárvore"}], "_links": {}},
                (2, 0): {"results": children, "_links": {}},
                (2, 50): {"results": [], "_links": {}},
                (2, 100): {"results": [], "_links": {}},
            }
        )

        result = locator_module.TDNPageLocator(collector, max_list_pages=3).locate(
            root_id=1, terms=["ausente"], max_depth=2, max_candidates=10
        )

        self.assertTrue(result["complete"])
        self.assertTrue(any("/content/2/child/page?limit=50&start=50" in url for url in collector.urls))
        self.assertFalse(any("/content/2/child/page?limit=50&start=100" in url for url in collector.urls))

    def test_refuses_an_external_pagination_link_without_requesting_it(self) -> None:
        locator_module = load_module()
        if not hasattr(locator_module, "LocatorUpstreamError"):
            self.fail("o localizador deve expor LocatorUpstreamError para paginação externa")
        collector = FakeCollector(
            {
                (1, 0): {
                    "results": [{"id": "11", "title": "MATA103"}],
                    "_links": {"next": "http://127.0.0.1/internal"},
                }
            }
        )

        with self.assertRaises(locator_module.LocatorUpstreamError):
            locator_module.TDNPageLocator(collector, max_list_pages=2).locate(
                root_id=1, terms=["mata103"], max_depth=1, max_candidates=10
            )

        self.assertTrue(all("127.0.0.1" not in url for url in collector.urls))


if __name__ == "__main__":
    unittest.main()
