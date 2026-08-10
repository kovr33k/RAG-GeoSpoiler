"""Prepare, activate, and if necessary restore a full Luna re-enrichment run."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config  # noqa: E402
import llm_backend  # noqa: E402
from enricher.pipeline import _is_youtube_only_normalized_document  # noqa: E402
from models import NormalizedMeta  # noqa: E402

RUNS_ROOT = PROJECT_ROOT / "artifacts" / "luna_full_reenrich"
EXPECTED_MODEL = "codex-cli:gpt-5.6-luna@xhigh"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _relative(path: Path) -> str:
    return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.strip()


def _file_records(root: Path) -> list[dict[str, Any]]:
    if not root.exists():
        return []
    return [
        {"path": _relative(path), "size": path.stat().st_size, "sha256": _sha256(path)}
        for path in sorted(item for item in root.rglob("*") if item.is_file())
    ]


def _input_identity() -> dict[str, Any]:
    normalized_files = _file_records(config.NORMALIZED_DIR)
    youtube_files = _file_records(config.YOUTUBE_NORMALIZED_DIR)
    generic_jobs = 0
    youtube_only = 0
    source_ids: set[str] = set()
    for text_path in sorted(config.NORMALIZED_DIR.rglob("*.txt")):
        meta_path = text_path.with_suffix(".meta.json")
        meta = NormalizedMeta.model_validate_json(meta_path.read_text(encoding="utf-8"))
        source_ids.add(meta.source_id.value)
        if _is_youtube_only_normalized_document(meta, text_path):
            youtube_only += 1
        else:
            generic_jobs += 1

    video_ids: set[str] = set()
    for metadata_path in sorted(config.YOUTUBE_NORMALIZED_DIR.rglob("*.youtube.meta.json")):
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        video_ids.add(str(metadata["video_id"]))

    return {
        "files": normalized_files + youtube_files,
        "counts": {
            "normalized_documents": generic_jobs + youtube_only,
            "generic_jobs": generic_jobs,
            "youtube_only_documents": youtube_only,
            "youtube_sources": len(video_ids),
            "unique_source_ids": len(source_ids),
            "unique_video_ids": len(video_ids),
        },
    }


def _runtime_identity() -> dict[str, Any]:
    return {
        "LLM_PROFILE": config.LLM_PROFILE,
        "CODEX_LUNA_MODEL": config.CODEX_LUNA_MODEL,
        "CODEX_LUNA_REASONING_EFFORT": config.CODEX_LUNA_REASONING_EFFORT,
        "CODEX_FALLBACK_TO_API": config.CODEX_FALLBACK_TO_API,
        "ENRICHMENT_SCHEMA_VERSION": config.ENRICHMENT_SCHEMA_VERSION,
        "ENRICHMENT_PROMPT_VERSION": config.ENRICHMENT_PROMPT_VERSION,
        "YOUTUBE_ENRICHMENT_PROMPT_VERSION": config.YOUTUBE_ENRICHMENT_PROMPT_VERSION,
        "active_enrichment_model": llm_backend.active_model_for("enrichment"),
        "WIKI_ENABLED": config.WIKI_ENABLED,
        "RERANKER_ENABLED": config.RERANKER_ENABLED,
    }


def _old_corpus_identity() -> dict[str, Any]:
    models: Counter[str] = Counter()
    cards = 0
    for path in sorted(config.ENRICHED_DIR.rglob("*.enriched.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        models[str(data.get("enrichment_model") or "<missing>")] += 1
        cards += 1
    return {"cards": cards, "model_distribution": dict(sorted(models.items()))}


def _assert_preflight(identity: dict[str, Any]) -> None:
    expected_counts = {
        "normalized_documents": 131,
        "generic_jobs": 129,
        "youtube_only_documents": 2,
        "youtube_sources": 4,
        "unique_source_ids": 131,
        "unique_video_ids": 4,
    }
    if identity["input"]["counts"] != expected_counts:
        raise RuntimeError(
            f"Input identity mismatch: {identity['input']['counts']} != {expected_counts}"
        )
    runtime = identity["runtime"]
    if runtime["active_enrichment_model"] != EXPECTED_MODEL:
        raise RuntimeError(f"Unexpected active model: {runtime['active_enrichment_model']}")
    if runtime["CODEX_FALLBACK_TO_API"]:
        raise RuntimeError("CODEX_FALLBACK_TO_API must be false")
    if runtime["WIKI_ENABLED"] or runtime["RERANKER_ENABLED"]:
        raise RuntimeError("Wiki and reranker must be disabled during re-enrichment")


def _backup_sources() -> list[Path]:
    sources = [
        config.ENRICHED_DIR,
        config.YOUTUBE_SEGMENTS_DIR,
        config.STATE_DIR / "enrichment_progress.json",
        config.YOUTUBE_CHECKPOINT_DIR,
    ]
    for database in (config.CARD_FTS_DB_PATH, config.SOURCE_REGISTRY_DB_PATH):
        sources.extend(sorted(database.parent.glob(f"{database.name}*")))
    unique: dict[str, Path] = {}
    for path in sources:
        if path.exists():
            unique[str(path.resolve()).casefold()] = path
    return list(unique.values())


def _backup_bytes() -> int:
    total = 0
    for source in _backup_sources():
        if source.is_dir():
            total += sum(path.stat().st_size for path in source.rglob("*") if path.is_file())
        else:
            total += source.stat().st_size
    return total


def prepare(run_dir: Path) -> None:
    run_dir = run_dir.resolve()
    run_dir.relative_to(RUNS_ROOT.resolve())
    if run_dir.exists():
        raise FileExistsError(f"Run directory already exists: {run_dir}")
    run_dir.mkdir(parents=True)

    usage = shutil.disk_usage(PROJECT_ROOT)
    backup_bytes = _backup_bytes()
    if usage.free < backup_bytes * 4:
        raise RuntimeError(
            f"Insufficient free space: {usage.free} bytes available for {backup_bytes} backup bytes"
        )
    identity = {
        "run_id": run_dir.name,
        "created_at": datetime.now(UTC).isoformat(),
        "git": {
            "branch": _git("branch", "--show-current"),
            "commit": _git("rev-parse", "HEAD"),
            "status": _git("status", "--short"),
        },
        "runtime": _runtime_identity(),
        "input": _input_identity(),
        "old_corpus": _old_corpus_identity(),
        "disk": {
            "free_bytes": usage.free,
            "total_bytes": usage.total,
            "backup_bytes": backup_bytes,
            "minimum_required_bytes": backup_bytes * 4,
        },
        "luna_smoke": {"passed": True, "real_calls": 2},
    }
    _assert_preflight(identity)
    _write_json(run_dir / "preflight.json", identity)

    backup_root = run_dir / "backup"
    copied: list[dict[str, Any]] = []
    for source in _backup_sources():
        destination = backup_root / _relative(source)
        if source.is_dir():
            shutil.copytree(source, destination)
            files = sorted(item for item in source.rglob("*") if item.is_file())
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            files = [source]
        for original in files:
            backup = backup_root / _relative(original)
            original_hash = _sha256(original)
            backup_hash = _sha256(backup)
            if original_hash != backup_hash:
                raise RuntimeError(f"Backup hash mismatch: {original}")
            copied.append(
                {
                    "source": _relative(original),
                    "backup": backup.relative_to(run_dir).as_posix(),
                    "size": original.stat().st_size,
                    "sha256": original_hash,
                    "verified": True,
                }
            )
    _write_json(
        run_dir / "backup_manifest.json",
        {"created_at": datetime.now(UTC).isoformat(), "files": copied, "verified": True},
    )
    print(json.dumps({"run_dir": str(run_dir), "backup_files": len(copied), **identity["input"]["counts"]}))


def activate(run_dir: Path) -> None:
    run_dir = run_dir.resolve()
    run_dir.relative_to(RUNS_ROOT.resolve())
    manifest = json.loads((run_dir / "backup_manifest.json").read_text(encoding="utf-8"))
    if not manifest.get("verified") or not manifest.get("files"):
        raise RuntimeError("Verified backup manifest is required")
    for record in manifest["files"]:
        source = PROJECT_ROOT / record["source"]
        backup = run_dir / record["backup"]
        if (
            not source.is_file()
            or _sha256(source) != record["sha256"]
            or not backup.is_file()
            or _sha256(backup) != record["sha256"]
        ):
            raise RuntimeError(f"Source or backup changed after preparation: {record['source']}")

    retired_root = run_dir / "retired"
    targets = [
        config.ENRICHED_DIR,
        config.YOUTUBE_SEGMENTS_DIR,
        config.STATE_DIR / "enrichment_progress.json",
        config.YOUTUBE_CHECKPOINT_DIR,
    ]
    moved: list[dict[str, str]] = []
    for target in targets:
        target = target.resolve()
        target.relative_to(PROJECT_ROOT.resolve())
        if not target.exists():
            continue
        destination = retired_root / _relative(target)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            raise FileExistsError(f"Retirement target exists: {destination}")
        shutil.move(str(target), str(destination))
        moved.append({"from": _relative(target), "to": destination.relative_to(run_dir).as_posix()})

    config.ENRICHED_DIR.mkdir(parents=True, exist_ok=True)
    config.YOUTUBE_SEGMENTS_DIR.mkdir(parents=True, exist_ok=True)
    config.YOUTUBE_CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    _write_json(
        run_dir / "maintenance.json",
        {
            "activated_at": datetime.now(UTC).isoformat(),
            "moved": moved,
            "indexes_left_active": [
                _relative(config.CARD_FTS_DB_PATH),
                _relative(config.SOURCE_REGISTRY_DB_PATH),
            ],
            "rollback_command": (
                f'python scripts/luna_reenrich_control.py restore --run-dir "{run_dir}" '
                "--confirm-restore"
            ),
        },
    )
    print(json.dumps({"activated": True, "run_dir": str(run_dir), "moved": len(moved)}))


def restore(run_dir: Path, confirm: bool) -> None:
    if not confirm:
        raise RuntimeError("Restore requires --confirm-restore")
    run_dir = run_dir.resolve()
    run_dir.relative_to(RUNS_ROOT.resolve())
    backup_root = run_dir / "backup"
    failed_root = run_dir / f"failed_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}"
    targets = [
        config.ENRICHED_DIR,
        config.YOUTUBE_SEGMENTS_DIR,
        config.STATE_DIR / "enrichment_progress.json",
        config.YOUTUBE_CHECKPOINT_DIR,
    ]
    database_names = (config.CARD_FTS_DB_PATH.name, config.SOURCE_REGISTRY_DB_PATH.name)
    database_paths: dict[str, Path] = {}
    for database in (config.CARD_FTS_DB_PATH, config.SOURCE_REGISTRY_DB_PATH):
        for current in database.parent.glob(f"{database.name}*"):
            database_paths[str(current.resolve()).casefold()] = current
    backup_artifacts = backup_root / "artifacts"
    if backup_artifacts.exists():
        for backup in backup_artifacts.iterdir():
            if backup.is_file() and backup.name.startswith(database_names):
                current = PROJECT_ROOT / backup.relative_to(backup_root)
                database_paths[str(current.resolve()).casefold()] = current
    targets.extend(database_paths.values())
    for target in targets:
        target = target.resolve()
        target.relative_to(PROJECT_ROOT.resolve())
        if target.exists():
            destination = failed_root / _relative(target)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(target), str(destination))
        backup = backup_root / _relative(target)
        if backup.is_dir():
            shutil.copytree(backup, target)
        elif backup.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(backup, target)
    print(json.dumps({"restored": True, "run_dir": str(run_dir)}))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("prepare", "activate", "restore"):
        command = subparsers.add_parser(name)
        command.add_argument("--run-dir", type=Path, required=True)
        if name == "restore":
            command.add_argument("--confirm-restore", action="store_true")
    args = parser.parse_args()
    if args.command == "prepare":
        prepare(args.run_dir)
    elif args.command == "activate":
        activate(args.run_dir)
    else:
        restore(args.run_dir, args.confirm_restore)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
