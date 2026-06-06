from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


DEFAULT_BATCH_GB = 1.9
DEFAULT_FILE_LIMIT_MB = 100.0


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def command_text(cmd: list[str]) -> str:
    return subprocess.list2cmdline([str(part) for part in cmd])


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plan RSDWTools git commit batches.")
    parser.add_argument(
        "command",
        nargs="?",
        choices=["analyze", "plan", "commit-batches"],
        default="plan",
    )
    parser.add_argument("--repo", type=Path, default=None, help="Repo to inspect. Defaults to this repo.")
    parser.add_argument("--out", type=Path, default=None, help="Write plan JSON to this path.")
    parser.add_argument("--max-batch-gb", type=float, default=DEFAULT_BATCH_GB)
    parser.add_argument("--file-limit-mb", type=float, default=DEFAULT_FILE_LIMIT_MB)
    parser.add_argument("--message-prefix", default="Update RSDWTools data")
    parser.add_argument("--execute", action="store_true", help="Actually create commit batches.")
    parser.add_argument("--push-each", action="store_true", help="Push after each created commit. Requires --execute.")
    parser.add_argument(
        "--deletions-first",
        action="store_true",
        help="Put delete-only changes first. RSDWTools defaults to deletions last.",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON output from the underlying planner.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = repo_root()
    repo = (args.repo or root).resolve()
    planner = root / "tools" / "GitCommitTools" / "git_commit_tools.py"

    cmd = [
        sys.executable,
        str(planner),
        args.command,
        str(repo),
        "--max-batch-gb",
        str(args.max_batch_gb),
        "--file-limit-mb",
        str(args.file_limit_mb),
        "--message-prefix",
        args.message_prefix,
    ]
    if args.out:
        out = args.out if args.out.is_absolute() else root / args.out
        cmd.extend(["--out", str(out.resolve())])
    if args.execute:
        cmd.append("--execute")
    if args.push_each:
        cmd.append("--push-each")
    if not args.deletions_first:
        cmd.append("--deletions-last")
    if args.json:
        cmd.append("--json")

    print(command_text(cmd), flush=True)
    return subprocess.call(cmd, cwd=str(root))


if __name__ == "__main__":
    raise SystemExit(main())
