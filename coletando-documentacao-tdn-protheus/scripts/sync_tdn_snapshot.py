"""Mantém snapshots TDN locais, transacionais e compatíveis com leitores v1/v2."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import tempfile
import time
import uuid
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from collect_tdn import API, TDNCollector

SCHEMA_VERSION = 2
GENERATIONS_TO_RETAIN = 2


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        delete=False,
        dir=path.parent,
        suffix=".tmp",
    ) as file:
        json.dump(value, file, ensure_ascii=False, indent=2)
        temporary = Path(file.name)
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


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


def page_summary(
    record: dict[str, Any], *, status: str = "active"
) -> dict[str, Any]:
    summary = {
        key: record.get(key)
        for key in (
            "id",
            "title",
            "url",
            "body_len",
            "version_number",
            "version_when",
            "text_sha256",
            "fetched_at",
        )
    }
    summary["status"] = status
    return summary


def page_changed(
    summary: dict[str, Any] | None,
    version: dict[str, Any] | None,
) -> bool:
    if not summary or not version:
        return True
    return (
        summary.get("version_number") != version.get("number")
        or summary.get("version_when") != version.get("when")
    )


class SnapshotLock:
    """Lock exclusivo de escrita por raiz, sem expiração automática."""

    def __init__(self, root: Path) -> None:
        self.path = Path(root) / ".snapshot.lock"
        self.fd: int | None = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError as error:
            message = (
                "outra atualização já está escrevendo esta raiz ou existe lock "
                f"órfão: {self.path}. Confirme que não há processo ativo antes "
                "de remover o lock manualmente."
            )
            raise RuntimeError(message) from error
        payload = json.dumps({"pid": os.getpid(), "at": now_utc()}).encode("utf-8")
        os.write(self.fd, payload)
        return self

    def __exit__(self, _type, _value, _traceback) -> None:
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None
        self.path.unlink(missing_ok=True)


class SnapshotStore:
    def __init__(self, cache_dir: Path, root_id: int) -> None:
        self.root = Path(cache_dir).expanduser().resolve() / str(int(root_id))
        self.manifest_path = self.root / "manifest.json"
        self.state_path = self.root / "run_state.json"
        self.errors_path = self.root / "tdn_errors.jsonl"

    def load_manifest(self) -> dict[str, Any] | None:
        if not self.manifest_path.is_file():
            return None
        try:
            data = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise RuntimeError("manifesto inválido") from error
        if not isinstance(data, dict):
            raise TypeError("manifesto deve ser um objeto JSON")
        if not isinstance(data.get("pages"), dict):
            raise TypeError("manifesto deve conter pages como objeto")
        schema = data.get("schema_version", 1)
        if schema not in (1, 2):
            raise RuntimeError(f"schema_version não suportado: {schema}")
        manifest_root = data.get("root_id")
        if manifest_root is not None and int(manifest_root) != int(self.root.name):
            raise RuntimeError("root_id do manifesto não corresponde à pasta")
        return data

    def pages_dir(self, manifest: dict[str, Any]) -> Path:
        relative = manifest.get("page_directory", "pages")
        if not isinstance(relative, str):
            raise TypeError("page_directory deve ser string")
        if not relative or Path(relative).is_absolute():
            raise RuntimeError("page_directory inválido")
        candidate = (self.root / relative).resolve()
        try:
            candidate.relative_to(self.root.resolve())
        except ValueError as error:
            raise RuntimeError("page_directory fora da raiz do snapshot") from error
        return candidate

    def read_page(
        self,
        page_id: int,
        manifest: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        manifest = manifest or self.load_manifest()
        if not manifest:
            raise RuntimeError("manifesto inexistente")
        path = self.pages_dir(manifest) / f"{int(page_id)}.json"
        if not path.is_file():
            raise RuntimeError(f"arquivo ausente para página {page_id}")
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise RuntimeError(f"arquivo inválido para página {page_id}") from error
        if not isinstance(record, dict):
            raise TypeError(f"registro da página {page_id} deve ser objeto")
        if int(record.get("id", -1)) != int(page_id):
            raise RuntimeError(f"identificador inválido para página {page_id}")
        return record

    def staging_dir(self, run_id: str) -> Path:
        return self.root / ".staging" / run_id

    def staged_page(self, run_id: str, page_id: int) -> Path:
        return self.staging_dir(run_id) / "pages" / f"{int(page_id)}.json"

    def write_staged_page(self, run_id: str, record: dict[str, Any]) -> None:
        write_json_atomic(self.staged_page(run_id, int(record["id"])), record)

    def copy_active_page_to_stage(
        self,
        run_id: str,
        page_id: int,
        manifest: dict[str, Any],
    ) -> None:
        source = self.pages_dir(manifest) / f"{int(page_id)}.json"
        if not source.is_file():
            raise RuntimeError(f"página ativa ausente no snapshot anterior: {page_id}")
        target = self.staged_page(run_id, page_id)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)

    def write_state(self, state: dict[str, Any]) -> None:
        write_json_atomic(self.state_path, state)

    def load_state(self) -> dict[str, Any] | None:
        if not self.state_path.is_file():
            return None
        try:
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise RuntimeError("estado retomável inválido") from error
        if not isinstance(data, dict):
            raise TypeError("estado retomável deve ser um objeto JSON")
        return data

    def clear_state(self) -> None:
        self.state_path.unlink(missing_ok=True)

    def abort_staging(self, run_id: str) -> None:
        shutil.rmtree(self.staging_dir(run_id), ignore_errors=True)

    def publish(self, run_id: str, manifest: dict[str, Any]) -> None:
        stage = self.staging_dir(run_id)
        pages = stage / "pages"
        pages.mkdir(parents=True, exist_ok=True)
        generations = self.root / "generations"
        generations.mkdir(parents=True, exist_ok=True)
        generation = generations / run_id
        if generation.exists():
            raise RuntimeError("generation_id já existe")
        os.replace(stage, generation)
        published = {
            **manifest,
            "schema_version": SCHEMA_VERSION,
            "generation_id": run_id,
            "page_directory": f"generations/{run_id}/pages",
        }
        try:
            write_json_atomic(self.manifest_path, published)
        except Exception:
            shutil.rmtree(generation, ignore_errors=True)
            raise
        self.clear_state()
        self._prune_generations(generation)

    def _prune_generations(self, current: Path) -> None:
        generations = self.root / "generations"
        candidates = [path for path in generations.iterdir() if path.is_dir()]
        previous = sorted(
            (path for path in candidates if path != current),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )[: GENERATIONS_TO_RETAIN - 1]
        retained = {current, *previous}
        for path in candidates:
            if path not in retained:
                try:
                    shutil.rmtree(path)
                except OSError:
                    pass

    def append_errors(self, errors: list[dict[str, str]]) -> None:
        if not errors:
            return
        self.root.mkdir(parents=True, exist_ok=True)
        with self.errors_path.open("a", encoding="utf-8") as file:
            for error in errors:
                event = {"at": now_utc(), **error}
                file.write(json.dumps(event, ensure_ascii=False) + "\n")


class PageLimitReached(RuntimeError):
    pass


class SnapshotDurationReached(TimeoutError):
    pass


class SnapshotSynchronizer:
    def __init__(self, root_id: int, cache_dir: Path, delay: float) -> None:
        self.root_id = int(root_id)
        if self.root_id <= 0:
            raise ValueError("root_id deve ser positivo")
        self.store = SnapshotStore(cache_dir, self.root_id)
        self.collector = TDNCollector(delay)
        self.delay = delay
        self._deadline: float | None = None
        self._discovered_count = 0

    def _run_id(self) -> str:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        return f"{timestamp}-{uuid.uuid4().hex[:10]}"

    def _set_deadline(self, max_duration_seconds: float | None) -> None:
        self._deadline = (
            time.monotonic() + max_duration_seconds
            if max_duration_seconds is not None
            else None
        )
        self.collector.deadline = self._deadline

    def _clear_deadline(self) -> None:
        self._deadline = None
        self.collector.deadline = None

    def _check_deadline(self) -> None:
        if self._deadline is not None and time.monotonic() >= self._deadline:
            raise SnapshotDurationReached("prazo máximo da operação atingido")

    def _sleep(self) -> None:
        delay = self.delay
        if self._deadline is not None:
            remaining = self._deadline - time.monotonic()
            if remaining <= 0:
                raise SnapshotDurationReached("prazo máximo da operação atingido")
            delay = min(delay, remaining)
        time.sleep(delay)
        self._check_deadline()

    def _estimate(self) -> dict[str, Any]:
        requests = self._discovered_count * 2
        return {
            "pages_discovered": self._discovered_count,
            "estimated_requests": requests,
            "minimum_delay_seconds": round(requests * self.delay, 1),
        }

    def discover_tree(self, max_depth: int, max_pages: int | None) -> list[int]:
        queue = deque([(self.root_id, 0)])
        seen: set[int] = set()
        discovered: list[int] = []
        while queue:
            self._check_deadline()
            page_id, depth = queue.popleft()
            if page_id in seen or depth > max_depth:
                continue
            if max_pages is not None and len(discovered) >= max_pages:
                raise PageLimitReached(
                    f"limite de {max_pages} páginas atingido durante descoberta"
                )
            seen.add(page_id)
            discovered.append(page_id)
            self._discovered_count = len(discovered)
            if depth < max_depth:
                for child in self.collector.list_children(page_id):
                    child_id = child.get("id")
                    if str(child_id).isdigit():
                        queue.append((int(child_id), depth + 1))
            self._sleep()
        return discovered

    def fetch_version(self, page_id: int) -> dict[str, Any] | None:
        data = self.collector.get_json(f"{API}/content/{page_id}?expand=version")
        if data is None:
            return None
        version = data.get("version", {})
        if not isinstance(version, dict):
            raise TypeError(f"version inválida para página {page_id}")
        return version

    def fetch_page(self, page_id: int) -> dict[str, Any] | None:
        url = f"{API}/content/{page_id}?expand=version,body.storage"
        data = self.collector.get_json(url)
        if data is None:
            return None
        body = data.get("body", {})
        storage = body.get("storage", {}) if isinstance(body, dict) else {}
        html = storage.get("value", "") if isinstance(storage, dict) else ""
        if not isinstance(html, str):
            raise TypeError(f"body.storage inválido para página {page_id}")
        version = data.get("version", {})
        if not isinstance(version, dict):
            raise TypeError(f"version inválida para página {page_id}")
        links = data.get("_links", {})
        fallback = f"/pages/viewpage.action?pageId={page_id}"
        webui = links.get("webui", fallback) if isinstance(links, dict) else fallback
        page_url = self.collector._trusted_web_url(str(webui), page_id)
        return page_record(
            page_id,
            str(data.get("title", f"page-{page_id}")),
            page_url,
            self.collector.html_to_text(html),
            len(html),
            version.get("number"),
            version.get("when"),
        )

    def snapshot(
        self,
        max_depth: int,
        max_pages: int | None,
        checkpoint_every: int,
        dry_run: bool,
        resume: bool,
        max_duration_seconds: float | None = None,
    ) -> dict[str, Any]:
        if dry_run and resume:
            raise RuntimeError("--dry-run e --resume são mutuamente exclusivos")
        self._discovered_count = 0
        self._set_deadline(max_duration_seconds)
        try:
            if dry_run:
                try:
                    self.discover_tree(max_depth, max_pages)
                    return {
                        "mode": "dry-run",
                        "root_id": self.root_id,
                        "complete": True,
                        **self._estimate(),
                    }
                except (PageLimitReached, SnapshotDurationReached, TimeoutError) as error:
                    stop_reason = (
                        "max-pages"
                        if isinstance(error, PageLimitReached)
                        else "max-duration"
                    )
                    return {
                        "mode": "dry-run",
                        "root_id": self.root_id,
                        "complete": False,
                        "stop_reason": stop_reason,
                        **self._estimate(),
                    }
            with SnapshotLock(self.store.root):
                existing_state = self.store.load_state()
                if resume:
                    state = existing_state
                    if (
                        not state
                        or state.get("root_id") != self.root_id
                        or state.get("mode") != "snapshot"
                    ):
                        raise RuntimeError("não existe estado retomável para esta raiz")
                    run_id = str(state.get("run_id", ""))
                    if not run_id or not self.store.staging_dir(run_id).is_dir():
                        raise RuntimeError("staging da execução retomável não existe")
                else:
                    if existing_state is not None:
                        raise RuntimeError(
                            "existe execução parcial; use --resume ou revise run_state.json"
                        )
                    discovered = self.discover_tree(max_depth, max_pages)
                    run_id = self._run_id()
                    state = {
                        "mode": "snapshot",
                        "run_id": run_id,
                        "root_id": self.root_id,
                        "max_depth": max_depth,
                        "delay_seconds": self.delay,
                        "pending_ids": discovered,
                        "completed_ids": [],
                        "pages": {},
                        "started_at": now_utc(),
                    }
                    (self.store.staging_dir(run_id) / "pages").mkdir(
                        parents=True,
                        exist_ok=True,
                    )
                    self.store.write_state(state)
                pending = [int(value) for value in state.get("pending_ids", [])]
                processed = 0
                while pending:
                    self._check_deadline()
                    page_id = pending.pop(0)
                    record = self.fetch_page(page_id)
                    if record is not None:
                        status = "active" if len(record["text"]) >= 60 else "filtered"
                        if status == "active":
                            self.store.write_staged_page(run_id, record)
                        state["pages"][str(page_id)] = page_summary(
                            record,
                            status=status,
                        )
                    state["completed_ids"].append(page_id)
                    state["pending_ids"] = pending
                    processed += 1
                    if processed % checkpoint_every == 0:
                        self.store.write_state(state)
                    self._sleep()
                self.store.write_state(state)
                completed_at = now_utc()
                manifest = {
                    "root_id": self.root_id,
                    "max_depth": int(state["max_depth"]),
                    "delay_seconds": float(state["delay_seconds"]),
                    "created_at": state["started_at"],
                    "updated_at": completed_at,
                    "last_complete_at": completed_at,
                    "pages": state["pages"],
                }
                self.store.publish(run_id, manifest)
                return {
                    "mode": "snapshot",
                    "root_id": self.root_id,
                    "pages_saved": sum(
                        item.get("status") == "active"
                        for item in state["pages"].values()
                    ),
                    "filtered": sum(
                        item.get("status") == "filtered"
                        for item in state["pages"].values()
                    ),
                }
        finally:
            self._clear_deadline()

    def refresh(
        self,
        max_depth: int,
        max_pages: int | None,
        max_duration_seconds: float | None = None,
    ) -> dict[str, Any]:
        self._discovered_count = 0
        self._set_deadline(max_duration_seconds)
        try:
            with SnapshotLock(self.store.root):
                if self.store.load_state() is not None:
                    raise RuntimeError(
                        "existe execução parcial; conclua/revise antes do refresh"
                    )
                previous_manifest = self.store.load_manifest()
                if not previous_manifest:
                    raise RuntimeError(
                        "snapshot inexistente; execute snapshot antes de refresh"
                    )
                discovered = self.discover_tree(max_depth, max_pages)
                run_id = self._run_id()
                (self.store.staging_dir(run_id) / "pages").mkdir(
                    parents=True,
                    exist_ok=True,
                )
                pages: dict[str, dict[str, Any]] = {}
                stats = {
                    "new": 0,
                    "changed": 0,
                    "unchanged": 0,
                    "removed": 0,
                    "filtered": 0,
                }
                try:
                    current_ids = {str(page_id) for page_id in discovered}
                    old_pages = dict(previous_manifest.get("pages", {}))
                    for page_id in discovered:
                        self._check_deadline()
                        key = str(page_id)
                        previous = old_pages.get(key)
                        version = self.fetch_version(page_id)
                        if version is None:
                            if previous:
                                pages[key] = {**previous, "status": "removed"}
                                if previous.get("status") != "removed":
                                    stats["removed"] += 1
                            continue
                        if previous and not page_changed(previous, version):
                            pages[key] = dict(previous)
                            if previous.get("status") == "active":
                                self.store.copy_active_page_to_stage(
                                    run_id,
                                    page_id,
                                    previous_manifest,
                                )
                            stats["unchanged"] += 1
                            self._sleep()
                            continue
                        record = self.fetch_page(page_id)
                        if record is None:
                            if previous:
                                pages[key] = {**previous, "status": "removed"}
                                if previous.get("status") != "removed":
                                    stats["removed"] += 1
                            continue
                        if len(record["text"]) >= 60:
                            self.store.write_staged_page(run_id, record)
                            pages[key] = page_summary(record)
                            stats["changed" if previous else "new"] += 1
                        else:
                            pages[key] = page_summary(record, status="filtered")
                            stats["filtered"] += 1
                        self._sleep()
                    for page_id, summary in old_pages.items():
                        if page_id not in current_ids:
                            pages[page_id] = {**summary, "status": "removed"}
                            if summary.get("status") != "removed":
                                stats["removed"] += 1
                    completed_at = now_utc()
                    manifest = {
                        "root_id": self.root_id,
                        "max_depth": max_depth,
                        "delay_seconds": self.delay,
                        "created_at": previous_manifest.get(
                            "created_at",
                            completed_at,
                        ),
                        "updated_at": completed_at,
                        "last_complete_at": completed_at,
                        "pages": pages,
                    }
                    self.store.publish(run_id, manifest)
                    return {"mode": "refresh", "root_id": self.root_id, **stats}
                except Exception:
                    self.store.abort_staging(run_id)
                    raise
        finally:
            self._clear_deadline()


def export_offline(store: SnapshotStore, output_dir: Path) -> int:
    manifest = store.load_manifest()
    if not manifest:
        raise RuntimeError("manifesto inexistente; não há snapshot local para exportar")
    pages: list[dict[str, Any]] = []
    for page_id, summary in sorted(
        manifest.get("pages", {}).items(),
        key=lambda item: int(item[0]),
    ):
        if summary.get("status") != "active":
            continue
        record = store.read_page(int(page_id), manifest)
        pages.append(
            {
                key: record[key]
                for key in ("id", "title", "url", "text", "body_len")
            }
        )
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
    pages_dir = store.pages_dir(manifest)
    size = (
        sum(path.stat().st_size for path in pages_dir.glob("*.json"))
        if pages_dir.is_dir()
        else 0
    )
    return {
        "root_id": manifest["root_id"],
        "schema_version": manifest.get("schema_version", 1),
        "generation_id": manifest.get("generation_id"),
        "last_complete_at": manifest.get("last_complete_at"),
        "active_pages": sum(item.get("status") == "active" for item in summaries),
        "removed_pages": sum(item.get("status") == "removed" for item in summaries),
        "filtered_pages": sum(
            item.get("status") == "filtered" for item in summaries
        ),
        "cache_bytes": size,
    }


def add_common_sync_options(
    parser: argparse.ArgumentParser,
    *,
    output: bool = False,
) -> None:
    parser.add_argument("--root-id", required=True, type=int, help="Raiz TDN")
    parser.add_argument(
        "--cache-dir",
        required=True,
        type=Path,
        help="Diretório-base do cache",
    )
    if output:
        parser.add_argument(
            "--output-dir",
            required=True,
            type=Path,
            help="Diretório de exportação",
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog="Modos: snapshot, refresh, export --offline e status.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    snapshot = sub.add_parser("snapshot", help="Cria snapshot transacional")
    add_common_sync_options(snapshot)
    snapshot.add_argument("--max-depth", type=int, default=8)
    snapshot.add_argument("--delay", type=float, default=0.35)
    snapshot.add_argument("--max-pages", type=int)
    snapshot.add_argument("--checkpoint-every", type=int, default=25)
    snapshot.add_argument("--max-duration-seconds", type=float)
    mode = snapshot.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--resume", action="store_true")

    refresh = sub.add_parser("refresh", help="Atualiza snapshot transacionalmente")
    add_common_sync_options(refresh)
    refresh.add_argument("--max-depth", type=int, default=8)
    refresh.add_argument("--delay", type=float, default=0.35)
    refresh.add_argument("--max-pages", type=int)
    refresh.add_argument("--max-duration-seconds", type=float)

    export = sub.add_parser("export", help="Exporta somente do cache local")
    add_common_sync_options(export, output=True)
    export.add_argument("--offline", action="store_true", required=True)

    inspect = sub.add_parser("status", help="Mostra estado local")
    add_common_sync_options(inspect)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if getattr(args, "max_depth", 0) < 0 or getattr(args, "delay", 0) < 0:
        raise SystemExit("--max-depth e --delay devem ser não negativos")
    if getattr(args, "max_pages", None) is not None and args.max_pages <= 0:
        raise SystemExit("--max-pages deve ser maior que zero")
    if getattr(args, "checkpoint_every", 1) < 1:
        raise SystemExit("--checkpoint-every deve ser maior que zero")
    max_duration = getattr(args, "max_duration_seconds", None)
    if max_duration is not None and max_duration <= 0:
        raise SystemExit("--max-duration-seconds deve ser maior que zero")

    store = SnapshotStore(args.cache_dir, args.root_id)
    try:
        if args.command == "export":
            result = {
                "mode": "export-offline",
                "pages_exported": export_offline(store, args.output_dir),
            }
        elif args.command == "status":
            result = status(store)
        else:
            sync = SnapshotSynchronizer(args.root_id, args.cache_dir, args.delay)
            if args.command == "snapshot":
                result = sync.snapshot(
                    args.max_depth,
                    args.max_pages,
                    args.checkpoint_every,
                    args.dry_run,
                    args.resume,
                    args.max_duration_seconds,
                )
            else:
                result = sync.refresh(
                    args.max_depth,
                    args.max_pages,
                    args.max_duration_seconds,
                )
            sync.store.append_errors(sync.collector.errors)
    except (RuntimeError, TypeError, PageLimitReached, TimeoutError, ValueError) as error:
        if "sync" in locals():
            sync.store.append_errors(sync.collector.errors)
        raise SystemExit(f"ERRO: {error}") from error
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
