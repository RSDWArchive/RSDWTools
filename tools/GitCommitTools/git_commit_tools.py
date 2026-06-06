from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence


GITHUB_FILE_LIMIT_BYTES = 100 * 1024 * 1024
DEFAULT_BATCH_LIMIT_BYTES = int(1.9 * 1024 * 1024 * 1024)


@dataclass(frozen=True)
class Change:
    status: str
    path: str
    old_path: str | None
    size_bytes: int
    exists: bool
    oversized: bool


@dataclass(frozen=True)
class Batch:
    index: int
    size_bytes: int
    changes: list[Change]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def format_bytes(value: int) -> str:
    units = ["B", "KiB", "MiB", "GiB", "TiB"]
    number = float(value)
    for unit in units:
        if number < 1024 or unit == units[-1]:
            return f"{number:.2f} {unit}" if unit != "B" else f"{int(number)} B"
        number /= 1024
    return f"{value} B"


def run_git(repo: Path, args: Sequence[str], *, check: bool = True) -> subprocess.CompletedProcess:
    cmd = ["git", *args]
    proc = subprocess.run(
        cmd,
        cwd=str(repo),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if check and proc.returncode != 0:
        stderr = proc.stderr.decode("utf-8", errors="replace").strip()
        raise SystemExit(f"git {' '.join(args)} failed with exit code {proc.returncode}\n{stderr}")
    return proc


def repo_root(path: Path) -> Path:
    proc = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "--show-toplevel"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0:
        raise SystemExit(f"Not a git repository: {path}")
    return Path(proc.stdout.strip()).resolve()


def parse_status_z(payload: bytes) -> list[tuple[str, str, str | None]]:
    entries = [part for part in payload.split(b"\0") if part]
    parsed: list[tuple[str, str, str | None]] = []
    i = 0
    while i < len(entries):
        entry = entries[i]
        if len(entry) < 4:
            i += 1
            continue
        status = entry[:2].decode("ascii", errors="replace")
        path = entry[3:].decode("utf-8", errors="replace")
        old_path: str | None = None

        if "R" in status or "C" in status:
            i += 1
            if i < len(entries):
                old_path = entries[i].decode("utf-8", errors="replace")

        parsed.append((status, path, old_path))
        i += 1
    return parsed


def worktree_changes(repo: Path, file_limit_bytes: int) -> list[Change]:
    proc = run_git(repo, ["status", "--porcelain=v1", "-z", "--untracked-files=all"])
    changes: list[Change] = []
    for status, rel_path, old_path in parse_status_z(proc.stdout):
        path = repo / rel_path
        exists = path.exists()
        size = path.stat().st_size if exists and path.is_file() else 0
        status_is_delete_only = status.strip() == "D"
        oversized = exists and size > file_limit_bytes and not status_is_delete_only
        changes.append(
            Change(
                status=status,
                path=rel_path.replace("\\", "/"),
                old_path=old_path.replace("\\", "/") if old_path else None,
                size_bytes=size,
                exists=exists,
                oversized=oversized,
            )
        )
    changes.sort(key=lambda change: (change.oversized, change.path.lower()))
    return changes


def status_summary(changes: Iterable[Change]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for change in changes:
        summary[change.status] = summary.get(change.status, 0) + 1
    return dict(sorted(summary.items()))


def top_level_summary(changes: Iterable[Change]) -> list[dict]:
    buckets: dict[str, dict[str, int]] = {}
    for change in changes:
        top = change.path.split("/", 1)[0]
        if top not in buckets:
            buckets[top] = {"files": 0, "bytes": 0, "oversized": 0}
        buckets[top]["files"] += 1
        buckets[top]["bytes"] += change.size_bytes
        buckets[top]["oversized"] += 1 if change.oversized else 0
    return [
        {"path": key, **value}
        for key, value in sorted(buckets.items(), key=lambda item: (-item[1]["bytes"], item[0].lower()))
    ]


def plan_batches(changes: list[Change], max_batch_bytes: int, deletions_last: bool) -> tuple[list[Batch], list[Change]]:
    allowed = [change for change in changes if not change.oversized]
    blocked = [change for change in changes if change.oversized]

    deletion_like = [change for change in allowed if change.size_bytes == 0]
    content_changes = [change for change in allowed if change.size_bytes > 0]
    content_changes.sort(key=lambda change: (change.path.split("/", 1)[0].lower(), change.path.lower()))

    batches: list[Batch] = []
    current: list[Change] = []
    current_size = 0

    if deletion_like and not deletions_last:
        batches.append(Batch(index=1, size_bytes=0, changes=deletion_like))

    for change in content_changes:
        if current and current_size + change.size_bytes > max_batch_bytes:
            batches.append(Batch(index=len(batches) + 1, size_bytes=current_size, changes=current))
            current = []
            current_size = 0
        current.append(change)
        current_size += change.size_bytes

    if current:
        batches.append(Batch(index=len(batches) + 1, size_bytes=current_size, changes=current))

    if deletion_like and deletions_last:
        batches.append(Batch(index=len(batches) + 1, size_bytes=0, changes=deletion_like))

    return batches, blocked


def printable_plan(
    repo: Path,
    changes: list[Change],
    batches: list[Batch],
    blocked: list[Change],
    max_batch_bytes: int,
    file_limit_bytes: int,
) -> str:
    total_bytes = sum(change.size_bytes for change in changes if not change.oversized)
    lines = [
        f"Repository: {repo}",
        f"Changed paths: {len(changes):,}",
        f"Estimated allowed bytes: {format_bytes(total_bytes)}",
        f"Batch limit: {format_bytes(max_batch_bytes)}",
        f"File limit: {format_bytes(file_limit_bytes)}",
        f"Oversized blocked files: {len(blocked):,}",
        "",
        "Status counts:",
    ]
    for status, count in status_summary(changes).items():
        lines.append(f"  {status!r}: {count:,}")

    lines.append("")
    lines.append("Top-level size buckets:")
    for bucket in top_level_summary(changes)[:20]:
        oversized_note = f", oversized={bucket['oversized']:,}" if bucket["oversized"] else ""
        lines.append(f"  {bucket['path']}: {bucket['files']:,} paths, {format_bytes(bucket['bytes'])}{oversized_note}")

    if blocked:
        lines.append("")
        lines.append(f"Blocked files over {format_bytes(file_limit_bytes)}:")
        for change in sorted(blocked, key=lambda item: -item.size_bytes)[:50]:
            lines.append(f"  {format_bytes(change.size_bytes)}  {change.path}")
        if len(blocked) > 50:
            lines.append(f"  ... {len(blocked) - 50:,} more")

    lines.append("")
    lines.append("Commit batches:")
    if not batches:
        lines.append("  None")
    for batch in batches:
        lines.append(
            f"  Batch {batch.index:03d}: {len(batch.changes):,} paths, {format_bytes(batch.size_bytes)}"
        )
        for change in batch.changes[:8]:
            lines.append(f"    {change.status} {format_bytes(change.size_bytes):>12}  {change.path}")
        if len(batch.changes) > 8:
            lines.append(f"    ... {len(batch.changes) - 8:,} more")
    return "\n".join(lines)


def plan_payload(
    repo: Path,
    changes: list[Change],
    batches: list[Batch],
    blocked: list[Change],
    max_batch_bytes: int,
    file_limit_bytes: int,
) -> dict:
    return {
        "schema": "GitCommitTools.Plan.v1",
        "generated_at_utc": utc_now(),
        "repo": str(repo),
        "max_batch_bytes": max_batch_bytes,
        "file_limit_bytes": file_limit_bytes,
        "changed_path_count": len(changes),
        "allowed_path_count": len(changes) - len(blocked),
        "blocked_path_count": len(blocked),
        "status_counts": status_summary(changes),
        "top_level_summary": top_level_summary(changes),
        "blocked": [asdict(change) for change in blocked],
        "batches": [
            {
                "index": batch.index,
                "size_bytes": batch.size_bytes,
                "path_count": len(batch.changes),
                "changes": [asdict(change) for change in batch.changes],
            }
            for batch in batches
        ],
    }


def write_plan(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote plan: {path}")


def ensure_clean_index(repo: Path) -> None:
    proc = run_git(repo, ["diff", "--cached", "--name-only"])
    if proc.stdout.strip():
        raise SystemExit("Index already has staged changes. Commit or unstage them before running commit-batches.")


def add_pathspec(repo: Path, args: list[str], changes: list[Change]) -> None:
    with tempfile.NamedTemporaryFile("wb", delete=False) as tmp:
        tmp_path = Path(tmp.name)
        for change in changes:
            tmp.write(change.path.encode("utf-8"))
            tmp.write(b"\0")
            if change.old_path:
                tmp.write(change.old_path.encode("utf-8"))
                tmp.write(b"\0")
    try:
        run_git(repo, [str(tmp_path) if arg == "{pathspec}" else arg for arg in args])
    finally:
        try:
            tmp_path.unlink()
        except FileNotFoundError:
            pass


def stage_paths(repo: Path, changes: list[Change]) -> None:
    tracked_changes = [change for change in changes if change.status != "??"]
    untracked_changes = [change for change in changes if change.status == "??"]

    if tracked_changes:
        add_pathspec(
            repo,
            [
                "add",
                "-u",
                "--pathspec-from-file",
                "{pathspec}",
                "--pathspec-file-nul",
            ],
            tracked_changes,
        )
    if untracked_changes:
        add_pathspec(
            repo,
            [
                "add",
                "-A",
                "--pathspec-from-file",
                "{pathspec}",
                "--pathspec-file-nul",
            ],
            untracked_changes,
        )


def commit_batches(repo: Path, batches: list[Batch], message_prefix: str, execute: bool, push_each: bool) -> None:
    if not execute:
        print("Dry run: no files were staged, committed, or pushed.")
        for batch in batches:
            print(f"Would commit batch {batch.index:03d}: {len(batch.changes):,} paths, {format_bytes(batch.size_bytes)}")
        print("Add --execute to stage and commit these batches.")
        return

    ensure_clean_index(repo)
    for batch in batches:
        print(f"Committing batch {batch.index:03d}: {len(batch.changes):,} paths, {format_bytes(batch.size_bytes)}")
        stage_paths(repo, batch.changes)
        message = f"{message_prefix} batch {batch.index:03d}"
        run_git(repo, ["commit", "-m", message])
        if push_each:
            run_git(repo, ["push"])


def max_batch_bytes_from_args(value: float) -> int:
    if value <= 0:
        raise argparse.ArgumentTypeError("batch size must be positive")
    return int(value * 1024 * 1024 * 1024)


def file_limit_bytes_from_args(value: float) -> int:
    if value <= 0:
        raise argparse.ArgumentTypeError("file limit must be positive")
    return int(value * 1024 * 1024)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Analyze and split large git worktrees into safe commit batches.")
    parser.add_argument("command", choices=["analyze", "plan", "commit-batches"])
    parser.add_argument("repo", type=Path, help="Path inside the target git repository.")
    parser.add_argument(
        "--max-batch-gb",
        type=float,
        default=DEFAULT_BATCH_LIMIT_BYTES / (1024 * 1024 * 1024),
        help="Estimated uncompressed size limit per commit batch. Default: 1.9 GiB.",
    )
    parser.add_argument(
        "--file-limit-mb",
        type=float,
        default=GITHUB_FILE_LIMIT_BYTES / (1024 * 1024),
        help="Maximum allowed file size. Default: 100 MiB.",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON output instead of text.")
    parser.add_argument("--out", type=Path, default=None, help="Write plan JSON to this path.")
    parser.add_argument("--message-prefix", default="Update archive data", help="Commit message prefix for commit-batches.")
    parser.add_argument("--execute", action="store_true", help="Actually stage and commit batches.")
    parser.add_argument("--push-each", action="store_true", help="Push after each created commit. Requires --execute.")
    parser.add_argument(
        "--deletions-last",
        action="store_true",
        help="Put delete-only changes in the final batch instead of the first batch.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo = repo_root(args.repo)
    max_batch_bytes = max_batch_bytes_from_args(args.max_batch_gb)
    file_limit_bytes = file_limit_bytes_from_args(args.file_limit_mb)

    changes = worktree_changes(repo, file_limit_bytes)
    batches, blocked = plan_batches(changes, max_batch_bytes, args.deletions_last)
    payload = plan_payload(repo, changes, batches, blocked, max_batch_bytes, file_limit_bytes)

    if args.out:
        out_path = args.out if args.out.is_absolute() else Path.cwd() / args.out
        write_plan(out_path, payload)

    if args.command == "analyze":
        if args.json:
            print(json.dumps({key: payload[key] for key in payload if key != "batches"}, indent=2))
        else:
            print(printable_plan(repo, changes, [], blocked, max_batch_bytes, file_limit_bytes))
        return 0 if not blocked else 2

    if args.command == "plan":
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print(printable_plan(repo, changes, batches, blocked, max_batch_bytes, file_limit_bytes))
        return 0 if not blocked else 2

    if args.command == "commit-batches":
        if blocked:
            print(printable_plan(repo, changes, batches, blocked, max_batch_bytes, file_limit_bytes))
            raise SystemExit("Refusing to commit while files over 100 MiB are present in the plan.")
        if args.push_each and not args.execute:
            raise SystemExit("--push-each requires --execute.")
        commit_batches(repo, batches, args.message_prefix, args.execute, args.push_each)
        return 0

    raise AssertionError(f"Unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
