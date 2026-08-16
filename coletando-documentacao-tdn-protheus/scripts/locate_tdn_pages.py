"""Localiza páginas TDN por título sem baixar seus corpos documentais."""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import deque
from typing import Any
from urllib.parse import urljoin, urlsplit

from collect_tdn import API, WEB, TDNCollector


class LocatorDurationReached(TimeoutError):
    pass


class LocatorUpstreamError(RuntimeError):
    pass


class TDNPageLocator:
    """Navega metadados de filhos da TDN com limites explícitos."""

    def __init__(
        self,
        collector: Any,
        max_list_pages: int,
        limit: int = 50,
        deadline: float | None = None,
        delay: float = 0,
    ) -> None:
        self.collector = collector
        self.max_list_pages = max_list_pages
        self.limit = limit
        self.deadline = deadline
        self.delay = delay
        self.list_pages_fetched = 0

    def _check_deadline(self) -> None:
        if self.deadline is not None and time.monotonic() >= self.deadline:
            raise LocatorDurationReached("prazo máximo atingido durante descoberta")

    def _sleep(self) -> None:
        if self.delay <= 0:
            return
        delay = self.delay
        if self.deadline is not None:
            delay = min(delay, self.deadline - time.monotonic())
            if delay <= 0:
                raise LocatorDurationReached("prazo máximo atingido durante descoberta")
        time.sleep(delay)
        self._check_deadline()

    @staticmethod
    def _trusted_next_url(current_url: str, next_link: str) -> str:
        candidate = urljoin(current_url, next_link)
        expected = urlsplit(API)
        parsed = urlsplit(candidate)
        if (
            parsed.scheme != expected.scheme
            or parsed.netloc != expected.netloc
            or not parsed.path.startswith(f"{expected.path}/")
        ):
            raise LocatorUpstreamError("link de paginação fora da API TDN configurada")
        return candidate

    def _children(self, page_id: int):
        start = 0
        url = f"{API}/content/{page_id}/child/page?limit={self.limit}&start={start}"
        while True:
            self._check_deadline()
            if self.list_pages_fetched >= self.max_list_pages:
                yield None, True
                return
            data = self.collector.get_json(url)
            if data is None:
                return [], False
            self.list_pages_fetched += 1
            batch = data.get("results", [])
            next_link = data.get("_links", {}).get("next")
            yield batch, bool(next_link)
            if next_link:
                url = self._trusted_next_url(url, str(next_link))
                self._sleep()
                continue
            if len(batch) < self.limit:
                return [], False
            start += len(batch)
            url = f"{API}/content/{page_id}/child/page?limit={self.limit}&start={start}"
            self._sleep()

    @staticmethod
    def _matches(title: str, terms: list[str]) -> bool:
        normalized = title.casefold()
        return any(term.casefold() in normalized for term in terms)

    def locate(
        self, root_id: int, terms: list[str], max_depth: int, max_candidates: int
    ) -> dict[str, Any]:
        queue = deque([(root_id, 0)])
        seen = {root_id}
        candidates: list[dict[str, Any]] = []
        stop_reason: str | None = None
        next_cursor_available = False

        try:
            while queue and stop_reason is None:
                page_id, depth = queue.popleft()
                if depth >= max_depth:
                    continue
                batches = self._children(page_id)
                for batch, next_available in batches:
                    if batch is None:
                        stop_reason = "max-list-pages"
                        next_cursor_available = next_available
                        break
                    for child in batch:
                        child_id = child.get("id")
                        if child_id is None:
                            continue
                        child_id = int(child_id)
                        title = str(child.get("title", ""))
                        child_depth = depth + 1
                        if self._matches(title, terms):
                            candidates.append(
                                {
                                    "id": child_id,
                                    "title": title,
                                    "parent_id": page_id,
                                    "depth": child_depth,
                                    "source_url": f"{WEB}/pages/viewpage.action?pageId={child_id}",
                                }
                            )
                            if len(candidates) >= max_candidates:
                                stop_reason = "max-candidates"
                                break
                        if child_depth < max_depth and child_id not in seen:
                            seen.add(child_id)
                            queue.append((child_id, child_depth))
                    if stop_reason is not None:
                        break
        except (LocatorDurationReached, TimeoutError):
            stop_reason = "max-duration"

        return {
            "complete": stop_reason is None,
            "stop_reason": stop_reason,
            "root_id": root_id,
            "terms": terms,
            "max_depth": max_depth,
            "list_pages_fetched": self.list_pages_fetched,
            "nodes_seen": len(seen),
            "candidates": candidates,
            "next_cursor_available": next_cursor_available,
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root-id", type=int, required=True)
    parser.add_argument("--term", action="append", required=True)
    parser.add_argument("--max-depth", type=int, default=1)
    parser.add_argument("--max-list-pages", type=int, required=True)
    parser.add_argument("--max-duration-seconds", type=float, required=True)
    parser.add_argument("--max-candidates", type=int, required=True)
    parser.add_argument("--delay", type=float, default=0.35)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.max_depth < 0 or args.max_list_pages <= 0 or args.max_duration_seconds <= 0 or args.max_candidates <= 0 or args.delay < 0:
        raise SystemExit("limites devem ser positivos; --max-depth e --delay podem ser zero")
    deadline = time.monotonic() + args.max_duration_seconds
    collector = TDNCollector(args.delay, deadline=deadline)
    try:
        result = TDNPageLocator(
            collector, args.max_list_pages, deadline=deadline, delay=args.delay
        ).locate(args.root_id, args.term, args.max_depth, args.max_candidates)
    except (LocatorUpstreamError, RuntimeError, TimeoutError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(2) from error
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else result)


if __name__ == "__main__":
    main()
