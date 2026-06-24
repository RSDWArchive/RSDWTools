import argparse
import subprocess
import sys
from pathlib import Path

from tools.archive_sources import (
    DEFAULT_ARCHIVE_ROOT,
    print_archive_sources,
    resolve_archive_sources,
)


DEFAULT_GIT_BATCH_GB = 1.9
DEFAULT_GIT_FILE_LIMIT_MB = 100.0


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
        repo_root / "website" / "tools" / "quest-editor" / "data" / "quests.json",
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
    parser.add_argument(
        "--skip-git-plan",
        action="store_true",
        help="Skip final Git commit batch planning.",
    )
    parser.add_argument(
        "--git-plan-output",
        type=Path,
        default=None,
        help="Git commit plan JSON output path.",
    )
    parser.add_argument(
        "--git-max-batch-gb",
        type=float,
        default=DEFAULT_GIT_BATCH_GB,
        help="Estimated uncompressed size limit per commit batch.",
    )
    parser.add_argument(
        "--git-file-limit-mb",
        type=float,
        default=DEFAULT_GIT_FILE_LIMIT_MB,
        help="Maximum allowed changed-file size.",
    )
    parser.add_argument(
        "--git-commit-batches",
        action="store_true",
        help="Create Git commits from the final batch plan. This stages and commits files.",
    )
    parser.add_argument(
        "--git-push-each",
        action="store_true",
        help="Push after each Git commit batch. Requires --git-commit-batches.",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent
    python_exe = args.python
    archive_sources = None

    if args.git_push_each and not args.git_commit_batches:
        print("[ERROR] --git-push-each requires --git-commit-batches.")
        return 1

    if not args.skip_docs_rebuild and not args.skip_ingest:
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

    effective_clean_ingest = args.clean_ingest or (args.fresh and not args.skip_ingest)
    effective_clean_docs_icons = args.clean_docs_icons or args.fresh

    if args.fresh and not args.skip_docs_rebuild:
        clean_generated_data(repo_root)

    if not args.skip_docs_rebuild:
        rebuild_cmd = [
            python_exe,
            "tools/rebuild_docs_data.py",
            "--archive-root",
            args.archive_root,
            "--raw-core",
            args.raw_core,
        ]
        if archive_sources:
            rebuild_cmd.extend(
                [
                    "--game-root",
                    str(archive_sources.game_root),
                    "--location-data-root",
                    str(archive_sources.location_data_root),
                    "--loot-data-root",
                    str(archive_sources.loot_data_root),
                ]
            )
        else:
            if args.game_root:
                rebuild_cmd.extend(["--game-root", args.game_root])
            if args.location_data_root:
                rebuild_cmd.extend(["--location-data-root", args.location_data_root])
            if args.loot_data_root:
                rebuild_cmd.extend(["--loot-data-root", args.loot_data_root])
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
        character_cmd = [
            python_exe,
            "tools/build_character_catalog.py",
            "--archive-root",
            args.archive_root,
            "--skills-source",
            str(Path(args.raw_core) / "skills"),
            "--content-root",
            str(Path(args.raw_core) / "icons"),
        ]
        if archive_sources:
            character_cmd.extend(["--game-root", str(archive_sources.game_root)])
        elif args.game_root:
            character_cmd.extend(["--game-root", args.game_root])
        run_step(character_cmd, repo_root)

    if not args.skip_git_plan:
        git_plan_output = args.git_plan_output or (repo_root / "GitCommitPlan.json")
        if not git_plan_output.is_absolute():
            git_plan_output = repo_root / git_plan_output
        git_mode = "commit-batches" if args.git_commit_batches else "plan"
        message_version = archive_sources.dataset_version if archive_sources else "data"
        git_cmd = [
            python_exe,
            "tools/PlanGitCommits.py",
            git_mode,
            "--repo",
            str(repo_root),
            "--out",
            str(git_plan_output),
            "--max-batch-gb",
            str(args.git_max_batch_gb),
            "--file-limit-mb",
            str(args.git_file_limit_mb),
            "--message-prefix",
            f"Update RSDWTools {message_version}",
        ]
        if args.git_commit_batches:
            git_cmd.append("--execute")
        if args.git_push_each:
            git_cmd.append("--push-each")
        run_step(git_cmd, repo_root)

    print("[INFO] Update pipeline complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
