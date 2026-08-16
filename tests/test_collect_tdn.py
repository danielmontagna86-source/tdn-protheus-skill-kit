from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "coletando-documentacao-tdn-protheus" / "scripts" / "collect_tdn.py"


def load_module():
    spec = importlib.util.spec_from_file_location("collect_tdn", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Response:
    def __init__(self, payload, status=200): self.payload, self.status_code = payload, status
    def raise_for_status(self):
        if self.status_code >= 400: raise RuntimeError("http")
    def json(self): return self.payload


class CollectorTests(unittest.TestCase):
    def test_get_json_disables_redirects(self) -> None:
        module = load_module()
        calls = []
        collector = module.TDNCollector(0)
        collector.session.get = lambda url, **kwargs: calls.append((url, kwargs)) or Response({"ok": True})
        self.assertEqual(collector.get_json(module.API + "/x"), {"ok": True})
        self.assertFalse(calls[0][1]["allow_redirects"])

    def test_list_children_refuses_external_next_link(self) -> None:
        module = load_module()
        collector = module.TDNCollector(0)
        collector.get_json = lambda _url: {"results": [], "_links": {"next": "http://127.0.0.1/internal"}}
        with self.assertRaisesRegex(RuntimeError, "fora da API"):
            collector.list_children(1)

    def test_fetch_page_refuses_external_web_url(self) -> None:
        module = load_module()
        collector = module.TDNCollector(0)
        collector.get_json = lambda _url: {"title": "X", "body": {"storage": {"value": "texto"}}, "_links": {"webui": "https://example.invalid/private"}}
        with self.assertRaisesRegex(RuntimeError, "fora do domínio"):
            collector.fetch_page(1)

    def test_html_to_text_removes_scripts_and_preserves_table_cells(self) -> None:
        module = load_module()
        text = module.TDNCollector.html_to_text("<script>bad</script><table><tr><td>A</td><td>B</td></tr></table>")
        self.assertNotIn("bad", text)
        self.assertIn("A | B", text)


if __name__ == "__main__": unittest.main()
