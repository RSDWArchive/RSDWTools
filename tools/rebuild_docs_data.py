import argparse
import subprocess
import sys
import shutil
from pathlib import Path

from archive_sources import (
    DEFAULT_ARCHIVE_ROOT,
    print_archive_sources,
    resolve_archive_sources,
)


def run_step(command: list[str], cwd: Path) -> None:
    printable = " ".join(command)
    print(f"[STEP] {printable}")
    subprocess.run(command, cwd=cwd, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the full docs data rebuild pipeline in one command."
    )
    parser.add_argument(
        "--archive-root",
        default=str(DEFAULT_ARCHIVE_ROOT),
        help=(
            "RSDWArchive checkout root. Used to auto-detect the latest "
            "dataset from website/data.config.json when --game-root is omitted."
        ),
    )
    parser.add_argument(
        "--game-root",
        default="",
        help=(
            "Explicit top-level game archive root used by ingest. "
            "Defaults to <archive-root>/<datasetVersion> from RSDWArchive."
        ),
    )
    parser.add_argument(
        "--raw-core",
        default="data",
        help="Data output folder used by ingest and downstream tools.",
    )
    parser.add_argument(
        "--location-data-root",
        default="",
        help=(
            "External LocationData source folder. Defaults to "
            "<archive-root>/website/tools/LocationData."
        ),
    )
    parser.add_argument(
        "--loot-data-root",
        default="",
        help=(
            "External LootData source folder. Defaults to "
            "<archive-root>/website/tools/LootData."
        ),
    )
    parser.add_argument(
        "--python",
        default=sys.executable,
        help="Python executable to use for child scripts.",
    )
    parser.add_argument(
        "--skip-ingest",
        action="store_true",
        help="Skip ingest and rebuild docs from existing data folder.",
    )
    parser.add_argument(
        "--clean-ingest",
        action="store_true",
        help="Clean ingest output folder before rebuilding.",
    )
    parser.add_argument(
        "--skip-catalog",
        action="store_true",
        help="Skip build_dwe_catalog.py.",
    )
    parser.add_argument(
        "--clean-docs-icons",
        action="store_true",
        help="Delete website/shared/icons before rebuilding icon catalogs.",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    python_exe = args.python
    raw_core = args.raw_core
    archive_sources = None

    if not args.skip_ingest:
        try:
            archive_sources = resolve_archive_sources(
                archive_root=args.archive_root,
                game_root=args.game_root or None,
                location_data_root=args.location_data_root or None,
                loot_data_root=args.loot_data_root or None,
            )
        except ValueError as exc:
            print(f"[ERROR] {exc}")
            return 1
        print_archive_sources(archive_sources)

    if args.clean_docs_icons:
        docs_icons = repo_root / "website" / "shared" / "icons"
        if docs_icons.exists():
            print(f"[STEP] clean {docs_icons}")
            shutil.rmtree(docs_icons)

    if not args.skip_ingest:
        ingest_cmd = [
            python_exe,
            "tools/ingest_game_data.py",
            "--game-root",
            str(archive_sources.game_root),
            "--output-root",
            raw_core,
            "--location-data-root",
            str(archive_sources.location_data_root),
            "--loot-data-root",
            str(archive_sources.loot_data_root),
        ]
        if args.clean_ingest:
            ingest_cmd.append("--clean")
        run_step(ingest_cmd, repo_root)

    run_step([python_exe, "tools/build_chest_item_catalog.py"], repo_root)
    run_step([python_exe, "tools/build_recipe_index.py"], repo_root)
    run_step([python_exe, "tools/build_spell_catalog.py"], repo_root)
    run_step([python_exe, "tools/build_mapdata_index.py"], repo_root)
    run_step([python_exe, "tools/export_docs_data_from_raw_core.py"], repo_root)

    if not args.skip_catalog:
        run_step([python_exe, "tools/build_dwe_catalog.py"], repo_root)

    print("[INFO] Docs data rebuild complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
