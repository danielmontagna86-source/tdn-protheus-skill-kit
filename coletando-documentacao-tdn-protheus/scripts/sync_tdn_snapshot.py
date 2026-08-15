"""Mantém um snapshot local e incremental de uma árvore pública do TDN."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from collect_tdn import API, WEB, TDNCollector


SCHEMA_VERSION = 1


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=path.parent, suffix=".tmp") as file:
        json.dump(value, file, ensure_ascii=False, indent=2)
        temp_path = Path(file.name)
    os.replace(temp_path, path)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def page_record(
    page_id: int,
    title: str,
    url: str,
    text: str,
    body_len: int,
    version_number: int | None,
    version_when: str | None,
) -> dict[str, Any]:
    return {
        "id": int(page_id),
        "title": title,
        "url": url,
        "text": text,
        "body_len": int(body_len),
        "version_number": version_number,
        "version_when": version_when,
        "text_sha256": sha256_text(text),
        "status": "active",
        "fetched_at": now_utc(),
    }


def page_summary(record: dict[str, Any]) -> dict[str, Any]:
    return {
        key: record[key]
        for key in (
            "id", "title", "url", "body_len", "version_number", "version_when",
            "text_sha256", "status", "fetched_at",
        )
    }


def new_manifest(root_id: int, max_depth: int, delay: float) -> dict[str, Any]:
    created_at = now_utc()
    return {
        "schema_version": SCHEMA_VERSION,
        "root_id": int(root_id),
        "max_depth": int(max_depth),
        "delay_seconds": float(delay),
        "created_at": created_at,
        "updated_at": created_at,
        "last_complete_at": None,
        "pages": {},
    }


def page_changed(summary: dict[str, Any] | None, version: dict[str, Any] | None) -> bool:
    if not summary or not version:
        return True
    return (
        summary.get("version_number") != version.get("number")
        or summary.get("version_when") != version.get("when")
    )


class SnapshotStore:
    def __init__(self, cache_dir: Path, root_id: int) -> None:
        self.root = Path(cache_dir).expanduser().resolve() / str(root_id)
        self.pages_dir = self.root / "pages"
        self.manifest_path = self.root / "manifest.json"
        self.state_path = self.root / "run_state.json"
        self.errors_path = self.root / "tdn_errors.jsonl"

    def page_path(self, page_id: int) -> Path:
        return self.pages_dir / f"{page_id}.json"

    def write_page(self, record: dict[str, Any]) -> None:
        write_json_atomic(self.page_path(int(record["id"])), record)

    def read_page(self, page_id: int) -> dict[str, Any]:
        return json.loads(self.page_path(page_id).read_text(encoding="utf-8"))

    def write_manifest(self, manifest: dict[str, Any]) -> None:
        write_json_atomic(self.manifest_path, manifest)

    def load_manifest(self) -> dict[str, Any] | None:
        if not self.manifest_path.is_file():
            return None
        return json.loads(self.manifest_path.read_text(encoding="utf-8"))

    def write_state(self, state: dict[str, Any]) -> None:
        write_json_atomic(self.state_path, state)

    def load_state(self) -> dict[str, Any] | None:
        if not self.state_path.is_file():
            return None
        return json.loads(self.state_path.read_text(encoding="utf-8"))

    def clear_state(self) -> None:
        if self.state_path.exists():
            self.state_path.unlink()

    def append_errors(self, errors: list[dict[str, str]]) -> None:
        if not errors:
            return
        self.root.mkdir(parents=True, exist_ok=True)
        with self.errors_path.open("a", encoding="utf-8") as file:
            for error in errors:
                file.write(json.dumps({"at": now_utc(), **error}, ensure_ascii=False) + "\n")


class PageLimitReached(RuntimeError):
    pass


class SnapshotSynchronizer:
    def __init__(self, root_id: int, cache_dir: Path, delay: float) -> None:
        self.root_id = int(root_id)
        self.store = SnapshotStore(cache_dir, self.root_id)
        self.collector = TDNCollector(delay)
        self.delay = delay

    def discover_tree(self, max_depth: int, max_pages: int | None) -> list[int]:
        queue = deque([(self.root_id, 0)])
        seen: set[int] = set()
        discovered: list[int] = []
        while queue:
            page_id, depth = queue.popleft()
            if page_id in seen or depth > max_depth:
                continue
            if max_pages is not None and len(discovered) >= max_pages:
                raise PageLimitReached(f"limite de {max_pages} páginas atingido durante descoberta")
            seen.add(page_id)
            discovered.append(page_id)
            if depth < max_depth:
                for child in self.collector.list_children(page_id):
                    child_id = child.get("id")
                    if child_id:
                        queue.append((int(child_id), depth + 1))
            time.sleep(self.delay)
        return discovered

    def fetch_version(self, page_id: int) -> dict[str, Any] | None:
        data = self.collector.get_json(f"{API}/content/{page_id}?expand=version")
        if data is None:
            return None
        return data.get("version", {})

    def fetch_page(self, page_id: int) -> dict[str, Any] | None:
        data = self.collector.get_json(f"{API}/content/{page_id}?expand=version,body.storage")
        if data is None:
            return None
        html = data.get("body", {}).get("storage", {}).get("value", "")
        version = data.get("version", {})
        webui = data.get("_links", {}).get("webui", f"/pages/viewpage.action?pageId={page_id}")
        return page_record(
            page_id,
            data.get("title", f"page-{page_id}"),
            f"{WEB}{webui}",
            self.collector.html_to_text(html),
            len(html),
            version.get("number"),
            version.get("when"),
        )

    def _checkpoint(self, state: dict[str, Any]) -> None:
        state["updated_at"] = now_utc()
        self.store.write_state(state)

    def snapshot(
        self,
        max_depth: int,
        max_pages: int | None,
        checkpoint_every: int,
        dry_run: bool,
        resume: bool,
    ) -> dict[str, Any]:
        if resume:
            state = self.store.load_state()
            if not state or state.get("root_id") != self.root_id:
                raise RuntimeError("não existe estado retomável para esta raiz")
            pending = [int(page_id) for page_id in state.get("pending_ids", [])]
        else:
            discovered = self.discover_tree(max_depth, max_pages)
            estimate = len(discovered) * 2
            if dry_run:
                return {
                    "mode": "dry-run", "root_id": self.root_id, "pages_discovered": len(discovered),
                    "estimated_requests": estimate, "minimum_delay_seconds": round(estimate * self.delay, 1),
                }
            state = {
                "root_id": self.root_id,
                "max_depth": max_depth,
                "delay_seconds": self.delay,
                "pending_ids": discovered,
                "completed_ids": [],
                "pages": {},
                "started_at": now_utc(),
            }
            self._checkpoint(state)
            pending = discovered
        processed = 0
        while pending:
            page_id = pending.pop(0)
            record = self.fetch_page(page_id)
            if record and len(record["text"]) >= 60:
                self.store.write_page(record)
                state["pages"][str(page_id)] = page_summary(record)
            state["completed_ids"].append(page_id)
            state["pending_ids"] = pending
            processed += 1
            if processed % checkpoint_every == 0:
                self._checkpoint(state)
            time.sleep(self.delay)
        self._checkpoint(state)
        manifest = new_manifest(self.root_id, int(state["max_depth"]), float(state["delay_seconds"]))
        manifest["created_at"] = state["started_at"]
        manifest["updated_at"] = now_utc()
        manifest["last_complete_at"] = manifest["updated_at"]
        manifest["pages"] = state["pages"]
        self.store.write_manifest(manifest)
        self.store.clear_state()
        return {"mode": "snapshot", "root_id": self.root_id, "pages_saved": len(manifest["pages"])}

    def refresh(self, max_depth: int, max_pages: int | None) -> dict[str, Any]:
        manifest = self.store.load_manifest()
        if not manifest:
            raise RuntimeError("snapshot inexistente; execute snapshot antes de refresh")
        discovered = self.discover_tree(max_depth, max_pages)
        current_ids = {str(page_id) for page_id in discovered}
        pages = dict(manifest.get("pages", {}))
        stats = {"new": 0, "changed": 0, "unchanged": 0, "removed": 0}
        for page_id in discovered:
            version = self.fetch_version(page_id)
            if version is None:
                previous = pages.get(str(page_id))
                if previous and previous.get("status") != "removed":
                    previous["status"] = "removed"
                    stats["removed"] += 1
                continue
            previous = pages.get(str(page_id))
            if previous and not page_changed(previous, version):
                stats["unchanged"] += 1
                time.sleep(self.delay)
                continue
            record = self.fetch_page(page_id)
            if record and len(record["text"]) >= 60:
                self.store.write_page(record)
                pages[str(page_id)] = page_summary(record)
                stats["changed" if previous else "new"] += 1
            time.sleep(self.delay)
        for page_id, summary in pages.items():
            if page_id not in current_ids and summary.get("status") != "removed":
                summary["status"] = "removed"
                stats["removed"] += 1
        manifest["max_depth"] = max_depth
        manifest["updated_at"] = now_utc()
        manifest["last_complete_at"] = manifest["updated_at"]
        manifest["pages"] = pages
        self.store.write_manifest(manifest)
        return {"mode": "refresh", "root_id": self.root_id, **stats}


def export_offline(store: SnapshotStore, output_dir: Path) -> int:
    manifest = store.load_manifest()
    if not manifest:
        raise RuntimeError("manifesto inexistente; não há snapshot local para exportar")
    pages: list[dict[str, Any]] = []
    for page_id, summary in sorted(manifest.get("pages", {}).items(), key=lambda item: int(item[0])):
        if summary.get("status") != "active":
            continue
        record = store.read_page(int(page_id))
        pages.append({key: record[key] for key in ("id", "title", "url", "text", "body_len")})
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json_atomic(output_dir / "tdn_pages.json", pages)
    with (output_dir / "tdn_pages.jsonl").open("w", encoding="utf-8") as file:
        for page in pages:
            file.write(json.dumps(page, ensure_ascii=False) + "\n")
    return len(pages)


def status(store: SnapshotStore) -> dict[str, Any]:
    manifest = store.load_manifest()
    if not manifest:
        raise RuntimeError("manifesto inexistente")
    summaries = list(manifest.get("pages", {}).values())
    size = sum(path.stat().st_size for path in store.pages_dir.glob("*.json")) if store.pages_dir.exists() else 0
    return {
        "root_id": manifest["root_id"],
        "last_complete_at": manifest.get("last_complete_at"),
        "active_pages": sum(item.get("status") == "active" for item in summaries),
        "removed_pages": sum(item.get("status") == "removed" for item in summaries),
        "cache_bytes": size,
    }


def add_common_sync_options(parser: argparse.ArgumentParser, *, output: bool = False) -> None:
    parser.add_argument("--root-id", required=True, type=int, help="Raiz TDN a sincronizar")
    parser.add_argument("--cache-dir", required=True, type=Path, help="Diretório-base do cache local")
    if output:
        parser.add_argument("--output-dir", required=True, type=Path, help="Diretório do JSON/JSONL exportado")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog="Modos: snapshot, refresh, export --offline e status. Use --dry-run antes de snapshot amplo.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    snapshot = sub.add_parser("snapshot", help="Baixa uma raiz para cache local")
    add_common_sync_options(snapshot)
    snapshot.add_argument("--max-depth", type=int, default=8)
    snapshot.add_argument("--delay", type=float, default=0.35)
    snapshot.add_argument("--max-pages", type=int)
    snapshot.add_argument("--checkpoint-every", type=int, default=25)
    snapshot.add_argument("--dry-run", action="store_true")
    snapshot.add_argument("--resume", action="store_true")
    refresh = sub.add_parser("refresh", help="Atualiza apenas páginas alteradas")
    add_common_sync_options(refresh)
    refresh.add_argument("--max-depth", type=int, default=8)
    refresh.add_argument("--delay", type=float, default=0.35)
    refresh.add_argument("--max-pages", type=int)
    export = sub.add_parser("export", help="Exporta apenas do cache local")
    add_common_sync_options(export, output=True)
    export.add_argument("--offline", action="store_true", required=True, help="Confirma operação sem HTTP")
    inspect = sub.add_parser("status", help="Mostra estado do cache sem rede")
    add_common_sync_options(inspect)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if getattr(args, "max_depth", 0) < 0 or getattr(args, "delay", 0) < 0:
        raise SystemExit("--max-depth e --delay devem ser não negativos")
    if getattr(args, "checkpoint_every", 1) < 1:
        raise SystemExit("--checkpoint-every deve ser maior que zero")
    store = SnapshotStore(args.cache_dir, args.root_id)
    try:
        if args.command == "export":
            result = {"mode": "export-offline", "pages_exported": export_offline(store, args.output_dir)}
        elif args.command == "status":
            result = status(store)
        else:
            sync = SnapshotSynchronizer(args.root_id, args.cache_dir, args.delay)
            if args.command == "snapshot":
                result = sync.snapshot(args.max_depth, args.max_pages, args.checkpoint_every, args.dry_run, args.resume)
            else:
                result = sync.refresh(args.max_depth, args.max_pages)
            sync.store.append_errors(sync.collector.errors)
    except (RuntimeError, PageLimitReached) as error:
        if "sync" in locals():
            sync.store.append_errors(sync.collector.errors)
        raise SystemExit(f"ERRO: {error}") from error
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
