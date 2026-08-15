"""Command line interface for the local TDN Protheus MCP."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .config import ConfigError, McpConfig, load_config


def doctor_payload(config: McpConfig) -> dict[str, Any]:
    diagnostics: list[dict[str, str]] = []
    for root_id in sorted(config.allowed_root_ids):
        manifest = config.cache_root / root_id / "manifest.json"
        if not manifest.is_file():
            diagnostics.append(
                {
                    "code": "SNAPSHOT_NOT_FOUND",
                    "severity": "warning",
                    "message": f"snapshot ausente para root_id={root_id}; use a skill para criar ou importar um snapshot local",
                }
            )
    return {
        "ok": True,
        "config": {
            "cache_root": str(config.cache_root),
            "allowed_root_ids": sorted(config.allowed_root_ids),
            "offline": config.offline,
            "allow_mutations": config.allow_mutations,
            "max_results": config.max_results,
            "max_chars": config.max_chars,
        },
        "diagnostics": diagnostics,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tdn-protheus-mcp", description="MCP local para snapshot TDN Protheus.")
    subcommands = parser.add_subparsers(dest="command", required=True)
    doctor = subcommands.add_parser("doctor", help="valida a configuração local sem rede")
    doctor.add_argument("--config", required=True, help="caminho para o arquivo JSON de configuração")
    doctor.add_argument("--json", action="store_true", help="emite diagnóstico estruturado em stdout")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command != "doctor":
        return 2
    try:
        payload = doctor_payload(load_config(Path(args.config)))
    except ConfigError as error:
        if args.json:
            print(json.dumps({"ok": False, "error": {"code": error.code, "message": str(error)}}, ensure_ascii=False))
        else:
            print(str(error), file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    else:
        print("Configuração válida.")
        for diagnostic in payload["diagnostics"]:
            print(f"{diagnostic['code']}: {diagnostic['message']}", file=sys.stderr)
    return 0
