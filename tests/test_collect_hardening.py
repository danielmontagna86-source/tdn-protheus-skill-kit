from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import requests

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "coletando-documentacao-tdn-protheus" / "scripts" / "collect_tdn.py"


def load_module():
    spec = importlib.util.spec_from_file_location("collect_tdn_hardening", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Response:
    def __init__(self, payload: object = None, status: int = 200, error: Exception | None = None):
        self.payload = payload
        self.status_code = status
        self.error = error

    def raise_for_status(self) -> None:
        if self.error:
            raise self.error
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self):
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


class CollectorHardeningTests(unittest.TestCase):
    def _collector(self):
        module = load_module()
        collector = module.TDNCollector(0)
        collector._sleep = lambda _seconds: None
        return module, collector

    def test_http_statuses_and_transport_failures_are_retried_and_recorded(self) -> None:
        module, collector = self._collector()
        cases = [401, 403, 429, 500, 502, 503, requests.Timeout("timeout"), requests.ConnectionError("offline")]
        for case in cases:
            with self.subTest(case=case):
                if isinstance(case, Exception):
                    collector.session.get = lambda _url, _case=case, **_kwargs: (_ for _ in ()).throw(_case)
                else:
                    collector.session.get = lambda _url, _case=case, **_kwargs: Response(status=_case)
                with self.assertRaisesRegex(RuntimeError, "Falha definitiva"):
                    collector.get_json(module.API + "/failure")
        self.assertEqual(len(collector.errors), len(cases))

    def test_success_not_found_invalid_json_and_invalid_body_contracts(self) -> None:
        module, collector = self._collector()
        collector.session.get = lambda _url, **_kwargs: Response({"ok": True})
        self.assertEqual(collector.get_json(module.API + "/ok"), {"ok": True})
        collector.session.get = lambda _url, **_kwargs: Response(status=404)
        self.assertIsNone(collector.get_json(module.API + "/missing"))
        for payload in (ValueError("bad json"), [], "not an object"):
            collector.session.get = lambda _url, _payload=payload, **_kwargs: Response(_payload)
            with self.assertRaisesRegex(RuntimeError, "Falha definitiva"):
                collector.get_json(module.API + "/invalid")
        collector.get_json = lambda _url: {"title": "Sem body", "version": {"number": 1}}
        page = collector.fetch_page(7)
        self.assertEqual(page["text"], "")
        self.assertEqual(page["url"], "https://tdn.totvs.com/pages/viewpage.action?pageId=7")
        collector.get_json = lambda _url: {"body": {"storage": {"value": 1}}}
        with self.assertRaisesRegex(TypeError, "body.storage.value"):
            collector.fetch_page(7)

    def test_pagination_uses_next_then_offset_and_rejects_invalid_link(self) -> None:
        _module, collector = self._collector()
        seen: list[str] = []
        payloads = iter([
            {"results": [{"id": 1}], "_links": {"next": "/rest/api/content/9/child/page?start=1"}},
            {"results": [{"id": 2}], "_links": {}},
        ])
        collector.get_json = lambda url: (seen.append(url), next(payloads))[1]
        self.assertEqual([item["id"] for item in collector.list_children(9, limit=2)], [1, 2])
        self.assertIn("start=1", seen[1])
        payloads = iter([
            {"results": [{"id": 1}], "_links": {}},
            {"results": [], "_links": {}},
        ])
        collector.get_json = lambda _url: next(payloads)
        self.assertEqual(len(collector.list_children(9, limit=1)), 1)
        collector.get_json = lambda _url: {"results": [], "_links": {"next": 3}}
        with self.assertRaisesRegex(TypeError, "link de paginação"):
            collector.list_children(9)
        collector.get_json = lambda _url: {"results": {}, "_links": {}}
        with self.assertRaisesRegex(TypeError, "lista de filhos"):
            collector.list_children(9)
        collector.get_json = lambda _url: {"results": [], "_links": []}
        with self.assertRaisesRegex(TypeError, "links de paginação"):
            collector.list_children(9)

    def test_trusted_domains_html_unicode_crawl_and_output(self) -> None:
        module, collector = self._collector()
        self.assertEqual(module.TDNCollector._trusted_api_url(module.API + "/x", "/rest/api/content/1"), module.API + "/content/1")
        with self.assertRaisesRegex(RuntimeError, "fora da API"):
            module.TDNCollector._trusted_api_url(module.API, "//evil.example/rest/api/x")
        self.assertEqual(module.TDNCollector._trusted_web_url("", 11), "https://tdn.totvs.com/pages/viewpage.action?pageId=11")
        html = "<style>bad</style><footer>bad</footer><aside>bad</aside><script>bad</script><table><tr><th>Ação</th><td>çã</td></tr></table><p>Olá\n\n\nMundo</p>"
        text = collector.html_to_text(html)
        self.assertIn("Ação | çã", text)
        self.assertIn("Olá", text)
        self.assertNotIn("bad", text)
        self.assertEqual(collector.html_to_text("  "), "")
        collector.fetch_page = lambda page_id: {"id": page_id, "text": "útil " * 20} if page_id != 3 else {"id": 3, "text": "curto"}
        collector.list_children = lambda page_id: [{"id": "2"}, {"id": "3"}, {"id": "x"}] if page_id == 1 else []
        with patch.object(module.time, "sleep") as sleep:
            pages = collector.crawl(1, 1)
        self.assertEqual([page["id"] for page in pages], [1, 2])
        self.assertEqual(sleep.call_count, 3)
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            module.write_output(pages, [{"url": "x", "error": "y"}], output)
            self.assertEqual(json.loads((output / "tdn_pages.json").read_text(encoding="utf-8"))[0]["id"], 1)
            self.assertEqual(len((output / "tdn_pages.jsonl").read_text(encoding="utf-8").splitlines()), 2)

    def test_retry_backoff_and_deadline_are_enforced(self) -> None:
        module, collector = self._collector()
        waits: list[float] = []
        collector.session.get = lambda _url, **_kwargs: Response({"ok": True})
        collector._sleep = waits.append
        self.assertEqual(collector.get_json(module.API + "/ok"), {"ok": True})
        self.assertEqual(waits, [])
        attempts = iter([requests.Timeout("once"), Response({"ok": True})])
        collector.session.get = lambda _url, **_kwargs: (_ for _ in ()).throw(next(attempts)) if False else next(attempts)
        # Convert the first yielded exception into the transport behavior expected by Session.get.
        original = collector.session.get
        def get(_url, **_kwargs):
            value = original(_url, **_kwargs)
            if isinstance(value, Exception):
                raise value
            return value
        collector.session.get = get
        self.assertEqual(collector.get_json(module.API + "/retry"), {"ok": True})
        self.assertEqual(waits, [1.5])
        clock = [0.0]
        collector.deadline = 1.0
        collector._sleep = module.TDNCollector._sleep.__get__(collector)
        with (
            patch.object(module.time, "monotonic", lambda: clock[0]),
            patch.object(module.time, "sleep", lambda seconds: clock.__setitem__(0, clock[0] + seconds)),
            self.assertRaisesRegex(TimeoutError, "prazo global"),
        ):
            collector._sleep(2)


if __name__ == "__main__":
    unittest.main()
