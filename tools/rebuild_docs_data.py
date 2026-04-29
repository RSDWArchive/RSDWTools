import argparse
import subprocess
import sys
import shutil
from pathlib import Path


def run_step(command: list[str], cwd: Path) -> None:
    printable = " ".join(command)
    print(f"[STEP] {printable}")
    subprocess.run(command, cwd=cwd, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the full docs data rebuild pipeline in one command."
    )
    parser.add_argument(
        "--game-root",
        default="E:\\Github\\RSDWArchive\\0.11.0.3",
        help="Top-level game archive root used by ingest.",
    )
    parser.add_argument(
        "--raw-core",
        default="data",
        help="Data output folder used by ingest and downstream tools.",
    )
    parser.add_argument(
        "--location-data-root",
        default="E:\\Github\\RSDWArchive\\website\\tools\\LocationData",
        help="External LocationData source folder.",
    )
    parser.add_argument(
        "--loot-data-root",
        default="E:\\Github\\RSDWArchive\\website\\tools\\LootData",
        help="External LootData source folder.",
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
            args.game_root,
            "--output-root",
            raw_core,
            "--location-data-root",
            args.location_data_root,
            "--loot-data-root",
            args.loot_data_root,
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
