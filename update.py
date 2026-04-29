import argparse
import subprocess
import sys
from pathlib import Path


def run_step(command: list[str], cwd: Path) -> None:
    printable = " ".join(command)
    print(f"[STEP] {printable}")
    subprocess.run(command, cwd=cwd, check=True)


def clean_generated_data(repo_root: Path) -> None:
    """Delete builder-generated outputs before a fresh rebuild.
    Per-tool data files live under website/tools/<name>/data/ and shared
    cross-tool data lives under website/data/.
    """
    generated_files = [
        repo_root / "website" / "tools" / "item-editor" / "data" / "catalog.json",
        repo_root / "website" / "tools" / "recipe-unlocker" / "data" / "recipes.json",
        repo_root / "website" / "tools" / "spell-editor" / "data" / "spells.json",
        repo_root / "website" / "tools" / "character-editor" / "data" / "character_catalog.json",
        repo_root / "website" / "data" / "chest_item_catalog.json",
        repo_root / "website" / "data" / "loot_data.json",
        repo_root / "website" / "data" / "location_data.json",
        repo_root / "website" / "data" / "mapdata_index.json",
        # Legacy compatibility outputs (only written with --write-legacy).
        repo_root / "website" / "data" / "loot_drop_table.json",
        repo_root / "website" / "data" / "loot_drop_table_enemy_names.json",
        repo_root / "website" / "data" / "loot_drop_table_item_names.json",
        repo_root / "website" / "data" / "chest_respawn_profiles.json",
        repo_root / "website" / "data" / "chest_prefabs.json",
        repo_root / "website" / "data" / "chest_sets.json",
        repo_root / "website" / "data" / "chest_drop_table_item_names.json",
    ]
    for path in generated_files:
        if path.exists():
            print(f"[STEP] clean {path}")
            path.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the full DragonWildsWeb update pipeline in one command."
    )
    parser.add_argument(
        "--python",
        default=sys.executable,
        help="Python executable to use for child scripts.",
    )

    # Docs data rebuild options (forwarded to tools/rebuild_docs_data.py)
    parser.add_argument(
        "--game-root",
        default="E:\\Github\\RSDWArchive\\0.11.1.4",
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
        help="Delete docs/icons before rebuilding icon catalogs.",
    )
    parser.add_argument(
        "--fresh",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Run a clean rebuild by default (clean ingest, clean docs/icons, "
            "and remove generated docs data files before rebuild)."
        ),
    )

    # Top-level controls
    parser.add_argument(
        "--skip-docs-rebuild",
        action="store_true",
        help="Skip tools/rebuild_docs_data.py.",
    )
    parser.add_argument(
        "--skip-character-catalog",
        action="store_true",
        help="Skip tools/build_character_catalog.py.",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent
    python_exe = args.python

    effective_clean_ingest = args.clean_ingest or (args.fresh and not args.skip_ingest)
    effective_clean_docs_icons = args.clean_docs_icons or args.fresh

    if args.fresh and not args.skip_docs_rebuild:
        clean_generated_data(repo_root)

    if not args.skip_docs_rebuild:
        rebuild_cmd = [
            python_exe,
            "tools/rebuild_docs_data.py",
            "--game-root",
            args.game_root,
            "--raw-core",
            args.raw_core,
            "--location-data-root",
            args.location_data_root,
            "--loot-data-root",
            args.loot_data_root,
        ]
        if args.skip_ingest:
            rebuild_cmd.append("--skip-ingest")
        if effective_clean_ingest:
            rebuild_cmd.append("--clean-ingest")
        if args.skip_catalog:
            rebuild_cmd.append("--skip-catalog")
        if effective_clean_docs_icons:
            rebuild_cmd.append("--clean-docs-icons")
        run_step(rebuild_cmd, repo_root)

    if not args.skip_character_catalog:
        run_step([python_exe, "tools/build_character_catalog.py"], repo_root)

    print("[INFO] Update pipeline complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
