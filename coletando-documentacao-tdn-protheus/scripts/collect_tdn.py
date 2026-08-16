"""Coleta páginas públicas do TDN Protheus por uma raiz do Confluence."""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import deque
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

API = "https://tdn.totvs.com/rest/api"
WEB = "https://tdn.totvs.com"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"


class TDNCollector:
    def __init__(self, delay: float, deadline: float | None = None) -> None:
        self.delay = delay
        self.deadline = deadline
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        self.errors: list[dict[str, str]] = []

    def _remaining_timeout(self) -> float:
        if self.deadline is None:
            return 30.0
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("prazo global da coleta atingido")
        return min(30.0, remaining)

    def _sleep(self, seconds: float) -> None:
        delay = seconds
        if self.deadline is not None:
            delay = min(delay, self._remaining_timeout())
        time.sleep(delay)
        self._remaining_timeout()

    @staticmethod
    def _trusted_api_url(current_url: str, link: str) -> str:
        candidate = urljoin(current_url, link)
        expected = urlsplit(API)
        parsed = urlsplit(candidate)
        if parsed.scheme != expected.scheme or parsed.netloc != expected.netloc or not parsed.path.startswith(expected.path + "/"):
            raise RuntimeError("paginação fora da API pública TDN configurada")
        return candidate

    @staticmethod
    def _trusted_web_url(link: str, page_id: int) -> str:
        candidate = urljoin(WEB, link or f"/pages/viewpage.action?pageId={page_id}")
        expected = urlsplit(WEB)
        parsed = urlsplit(candidate)
        if parsed.scheme != expected.scheme or parsed.netloc != expected.netloc:
            raise RuntimeError("link de página fora do domínio TDN")
        return candidate

    def get_json(self, url: str) -> dict | None:
        for attempt in range(3):
            try:
                response = self.session.get(url, timeout=self._remaining_timeout(), allow_redirects=False)
                if response.status_code == 404:
                    return None
                if 300 <= response.status_code < 400:
                    raise RuntimeError("redirect HTTP não permitido durante coleta TDN")
                response.raise_for_status()
                data = response.json()
                if not isinstance(data, dict):
                    raise RuntimeError("resposta JSON da TDN deve ser objeto")
                return data
            except (requests.RequestException, ValueError, RuntimeError) as error:
                if attempt == 2:
                    self.errors.append({"url": url, "error": str(error)})
                    raise RuntimeError(f"Falha definitiva na API: {url}") from error
                self._sleep(1.5 * (attempt + 1))
        raise AssertionError("loop de tentativa inesperado")

    def list_children(self, page_id: int, limit: int = 50) -> list[dict]:
        children: list[dict] = []
        start = 0
        url = f"{API}/content/{page_id}/child/page?limit={limit}&start={start}"
        while True:
            data = self.get_json(url)
            if data is None:
                return children
            batch = data.get("results", [])
            if not isinstance(batch, list):
                raise RuntimeError("lista de filhos inválida")
            children.extend(item for item in batch if isinstance(item, dict))
            links = data.get("_links", {})
            if not isinstance(links, dict):
                raise RuntimeError("links de paginação inválidos")
            next_link = links.get("next")
            if next_link:
                if not isinstance(next_link, str):
                    raise RuntimeError("link de paginação inválido")
                url = self._trusted_api_url(url, next_link)
                continue
            if len(batch) < limit:
                return children
            start += len(batch)
            url = f"{API}/content/{page_id}/child/page?limit={limit}&start={start}"

    @staticmethod
    def html_to_text(html: str) -> str:
        if not html or not html.strip():
            return ""
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "footer", "aside"]):
            tag.decompose()
        for table in soup.find_all("table"):
            rows = []
            for tr in table.find_all("tr"):
                cells = [cell.get_text(" ", strip=True) for cell in tr.find_all(["th", "td"])]
                if cells:
                    rows.append(" | ".join(cells))
            if rows:
                table.replace_with(BeautifulSoup("\n" + "\n".join(rows) + "\n", "html.parser"))
        return re.sub(r"\n{3,}", "\n\n", soup.get_text(separator="\n", strip=True)).strip()

    def fetch_page(self, page_id: int) -> dict | None:
        data = self.get_json(f"{API}/content/{page_id}?expand=body.storage")
        if data is None:
            return None
        body = data.get("body", {})
        storage = body.get("storage", {}) if isinstance(body, dict) else {}
        html = storage.get("value", "") if isinstance(storage, dict) else ""
        if not isinstance(html, str):
            raise RuntimeError("body.storage.value inválido")
        links = data.get("_links", {})
        webui = links.get("webui", "") if isinstance(links, dict) else ""
        return {"id": page_id, "title": str(data.get("title", f"page-{page_id}")), "url": self._trusted_web_url(str(webui), page_id), "text": self.html_to_text(html), "body_len": len(html)}

    def crawl(self, root_id: int, max_depth: int) -> list[dict]:
        pages: list[dict] = []
        seen: set[int] = set()
        queue = deque([(root_id, 0)])
        while queue:
            page_id, depth = queue.popleft()
            if page_id in seen or depth > max_depth:
                continue
            seen.add(page_id)
            page = self.fetch_page(page_id)
            if page and len(page["text"]) >= 60:
                pages.append(page)
            if depth < max_depth:
                for child in self.list_children(page_id):
                    child_id = child.get("id")
                    if str(child_id).isdigit():
                        queue.append((int(child_id), depth + 1))
            time.sleep(self.delay)
        return pages


def write_output(pages: list[dict], errors: list[dict[str, str]], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "tdn_pages.json").write_text(json.dumps(pages, ensure_ascii=False, indent=2), encoding="utf-8")
    with (output_dir / "tdn_pages.jsonl").open("w", encoding="utf-8") as file:
        for page in pages:
            file.write(json.dumps(page, ensure_ascii=False) + "\n")
    with (output_dir / "tdn_errors.jsonl").open("w", encoding="utf-8") as file:
        for error in errors:
            file.write(json.dumps(error, ensure_ascii=False) + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root_id", type=int)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--max-depth", type=int, default=8)
    parser.add_argument("--delay", type=float, default=0.35)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.max_depth < 0 or args.delay < 0:
        raise SystemExit("--max-depth e --delay devem ser não negativos")
    collector = TDNCollector(args.delay)
    try:
        pages = collector.crawl(args.root_id, args.max_depth)
    except RuntimeError as error:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        with (args.output_dir / "tdn_errors.jsonl").open("w", encoding="utf-8") as file:
            for item in collector.errors:
                file.write(json.dumps(item, ensure_ascii=False) + "\n")
        raise SystemExit(f"Coleta interrompida para evitar dataset incompleto: {error}") from error
    write_output(pages, collector.errors, args.output_dir)
    print(f"OK: {len(pages)} páginas úteis em {args.output_dir}")


if __name__ == "__main__":
    main()
