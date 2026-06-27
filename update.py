import argparse
import json
import subprocess
import sys
from pathlib import Path

from tools.archive_sources import (
    DEFAULT_ARCHIVE_ROOT,
    print_archive_sources,
    resolve_archive_sources,
)
from tools.pipeline_summary import (
    PipelineRun,
    PipelineStepError,
    command_argv,
    read_summary,
)


DEFAULT_GIT_BATCH_GB = 1.9
DEFAULT_GIT_FILE_LIMIT_MB = 100.0


GENERATED_ARTIFACTS = {
    "ingestManifest": Path("data") / "_ingest_manifest.json",
    "itemEditorCatalog": Path("website") / "tools" / "item-editor" / "data" / "catalog.json",
    "recipeCatalog": Path("website") / "tools" / "recipe-unlocker" / "data" / "recipes.json",
    "questCatalog": Path("website") / "tools" / "quest-editor" / "data" / "quests.json",
    "spellCatalog": Path("website") / "tools" / "spell-editor" / "data" / "spells.json",
    "characterCatalog": Path("website") / "tools" / "character-editor" / "data" / "character_catalog.json",
    "chestItemCatalog": Path("website") / "data" / "chest_item_catalog.json",
    "lootData": Path("website") / "data" / "loot_data.json",
    "locationData": Path("website") / "data" / "location_data.json",
    "mapdataIndex": Path("website") / "data" / "mapdata_index.json",
    "sharedIcons": Path("website") / "shared" / "icons",
}


def clean_generated_data(repo_root: Path) -> list[str]:
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
    removed: list[str] = []
    for path in generated_files:
        if path.exists():
            print(f"[STEP] clean {path}")
            path.unlink()
            removed.append(str(path))
    return removed


def build_validate_command(args: argparse.Namespace, repo_root: Path, python_exe: str, mode: str) -> list[str]:
    command = [
        python_exe,
        "tools/validate_pipeline_outputs.py",
        "--repo-root",
        str(repo_root),
        "--archive-root",
        str(args.archive_root),
        "--mode",
        mode,
    ]
    if args.validate_summary:
        command.extend(["--summary", str(args.validate_summary)])
    if args.game_root:
        command.extend(["--game-root", args.game_root])
    if args.expected_dataset_version:
        command.extend(["--expected-dataset-version", args.expected_dataset_version])
    if args.allow_unknown_warnings:
        command.append("--allow-unknown-warnings")
    return command


def run_validation_mode(args: argparse.Namespace, repo_root: Path, python_exe: str, mode: str) -> int:
    command = build_validate_command(args, repo_root, python_exe, mode)
    print(f"[STEP] {' '.join(command)}")
    return subprocess.run(command, cwd=repo_root, check=False).returncode


def derive_git_mode(args: argparse.Namespace) -> str:
    if args.git_mode:
        return args.git_mode
    if args.git_push_each:
        return "push-each"
    if args.git_commit_batches:
        return "commit-only"
    return "plan-only"


def resolve_path(repo_root: Path, value: Path | None) -> Path | None:
    if value is None:
        return None
    return value if value.is_absolute() else repo_root / value


def load_json_if_exists(path: Path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def item_editor_count(catalog: object) -> int:
    if not isinstance(catalog, dict):
        return 0
    tabs = catalog.get("tabs")
    if not isinstance(tabs, dict):
        return 0
    total = 0
    for tab in tabs.values():
        if isinstance(tab, list):
            total += len(tab)
        elif isinstance(tab, dict) and isinstance(tab.get("items"), list):
            total += len(tab["items"])
    return total


def collect_generated_counts(repo_root: Path) -> dict[str, int]:
    counts: dict[str, int] = {}

    manifest = load_json_if_exists(repo_root / "data" / "_ingest_manifest.json")
    if isinstance(manifest, dict) and isinstance(manifest.get("summary"), dict):
        summary = manifest["summary"]
        for source_key, target_key in (
            ("json_scanned", "ingestJsonScanned"),
            ("json_unmatched", "ingestJsonUnmatched"),
            ("duplicates_skipped", "ingestDuplicatesSkipped"),
        ):
            value = summary.get(source_key)
            if isinstance(value, int):
                counts[target_key] = value

    chest_items = load_json_if_exists(repo_root / "website" / "data" / "chest_item_catalog.json")
    if isinstance(chest_items, list):
        counts["itemsIndexed"] = len(chest_items)

    item_catalog = load_json_if_exists(
        repo_root / "website" / "tools" / "item-editor" / "data" / "catalog.json"
    )
    item_count = item_editor_count(item_catalog)
    if item_count:
        counts["itemEditorItems"] = item_count

    recipes = load_json_if_exists(
        repo_root / "website" / "tools" / "recipe-unlocker" / "data" / "recipes.json"
    )
    if isinstance(recipes, list):
        counts["recipesIndexed"] = len(recipes)

    quest_catalog = load_json_if_exists(
        repo_root / "website" / "tools" / "quest-editor" / "data" / "quests.json"
    )
    if isinstance(quest_catalog, dict) and isinstance(quest_catalog.get("quests"), list):
        counts["questsIndexed"] = len(quest_catalog["quests"])

    spells = load_json_if_exists(
        repo_root / "website" / "tools" / "spell-editor" / "data" / "spells.json"
    )
    if isinstance(spells, list):
        counts["spellsIndexed"] = len(spells)

    mapdata = load_json_if_exists(repo_root / "website" / "data" / "mapdata_index.json")
    if isinstance(mapdata, dict) and isinstance(mapdata.get("points"), list):
        counts["mapPointsIndexed"] = len(mapdata["points"])

    character = load_json_if_exists(
        repo_root / "website" / "tools" / "character-editor" / "data" / "character_catalog.json"
    )
    if isinstance(character, dict):
        for source_key, target_key in (
            ("Skills", "characterSkillsIndexed"),
            ("Mounts", "mountsIndexed"),
            ("VendorReputations", "vendorReputationsIndexed"),
        ):
            value = character.get(source_key)
            if isinstance(value, list):
                counts[target_key] = len(value)

    return counts


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the RSDWTools update pipeline in one command."
    )
    parser.add_argument(
        "--python",
        default=sys.executable,
        help="Python executable to use for child scripts.",
    )
    parser.add_argument(
        "--mode",
        choices=["full", "build-local", "validate-local", "publish", "validate-published"],
        default="full",
        help=(
            "Pipeline mode. full preserves the historical behavior; build-local "
            "rebuilds without Git; publish validates existing outputs then runs Git."
        ),
    )
    parser.add_argument(
        "--git-mode",
        choices=["plan-only", "commit-only", "push-each"],
        default=None,
        help="Git behavior for full/publish modes.",
    )
    parser.add_argument(
        "--pipeline-log-dir",
        type=Path,
        default=None,
        help="Canonical PipelineLogs run directory.",
    )
    parser.add_argument(
        "--pipeline-summary-output",
        type=Path,
        default=None,
        help="Latest-summary compatibility output. Defaults to PipelineRun.json.",
    )
    parser.add_argument(
        "--validate-summary",
        type=Path,
        default=None,
        help="PipelineRun.json to validate for validate/publish modes.",
    )
    parser.add_argument(
        "--allow-unknown-warnings",
        action="store_true",
        help="Allow unknown warning categories in release validation.",
    )
    parser.add_argument(
        "--expected-dataset-version",
        default="",
        help="Expected archive dataset version for validation.",
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
        help="Push after each Git commit batch. Requires commit mode.",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent
    python_exe = args.python

    if args.mode == "validate-local":
        return run_validation_mode(args, repo_root, python_exe, "local")
    if args.mode == "validate-published":
        return run_validation_mode(args, repo_root, python_exe, "published")

    git_mode = derive_git_mode(args)
    if args.git_push_each and args.git_mode == "plan-only":
        print("[ERROR] --git-push-each conflicts with --git-mode plan-only.")
        return 1
    if args.git_push_each and args.git_mode == "commit-only":
        print("[ERROR] --git-push-each conflicts with --git-mode commit-only.")
        return 1
    if args.git_commit_batches and args.git_mode == "plan-only":
        print("[ERROR] --git-commit-batches conflicts with --git-mode plan-only.")
        return 1
    if args.git_push_each and not args.git_commit_batches and args.git_mode != "push-each":
        print("[ERROR] --git-push-each requires --git-commit-batches or --git-mode push-each.")
        return 1

    effective_fresh = args.fresh
    effective_skip_docs_rebuild = args.skip_docs_rebuild
    effective_skip_character_catalog = args.skip_character_catalog
    effective_skip_git_plan = args.skip_git_plan

    previous_summary = None
    validated_summary_path = None
    if args.mode == "build-local":
        effective_skip_git_plan = True
    elif args.mode == "publish":
        validation_code = run_validation_mode(args, repo_root, python_exe, "local")
        if validation_code != 0:
            return validation_code
        effective_fresh = False
        effective_skip_docs_rebuild = True
        effective_skip_character_catalog = True
        effective_skip_git_plan = False
        summary_path = resolve_path(repo_root, args.validate_summary) or (repo_root / "PipelineRun.json")
        if summary_path.exists():
            validated_summary_path = summary_path
            previous_summary = read_summary(summary_path)

    effective_git_commit_batches = git_mode in ("commit-only", "push-each")
    effective_git_push_each = git_mode == "push-each"
    if effective_skip_git_plan:
        effective_git_commit_batches = False
        effective_git_push_each = False

    log_dir = resolve_path(repo_root, args.pipeline_log_dir)
    latest_summary_path = resolve_path(repo_root, args.pipeline_summary_output)
    runner = PipelineRun(
        repo_root,
        command_argv(),
        mode=args.mode,
        git_mode=None if effective_skip_git_plan else git_mode,
        log_dir=log_dir,
        latest_summary_path=latest_summary_path,
        allow_unknown_warnings=args.allow_unknown_warnings,
    )

    try:
        archive_sources = None
        needs_archive_resolution = (
            (not effective_skip_docs_rebuild and not args.skip_ingest)
            or not effective_skip_character_catalog
        )

        if previous_summary and validated_summary_path:
            runner.set_validated_summary(previous_summary, validated_summary_path)

        if needs_archive_resolution:
            stage = runner.begin_stage("resolve_archive_sources")
            try:
                archive_sources = resolve_archive_sources(
                    archive_root=args.archive_root,
                    game_root=args.game_root or None,
                    location_data_root=args.location_data_root or None,
                    loot_data_root=args.loot_data_root or None,
                )
            except ValueError as exc:
                print(f"[ERROR] {exc}")
                runner.finish_stage(stage, status="failed", exit_code=1, error=str(exc))
                runner.fail(str(exc))
                return 1
            print_archive_sources(archive_sources)
            runner.set_archive(archive_sources)
            runner.finish_stage(stage, status="complete", exit_code=0)

        effective_clean_ingest = args.clean_ingest or (effective_fresh and not args.skip_ingest)
        effective_clean_docs_icons = args.clean_docs_icons or effective_fresh

        if effective_fresh and not effective_skip_docs_rebuild:
            stage = runner.begin_stage("clean_generated_data")
            removed = clean_generated_data(repo_root)
            runner.finish_stage(
                stage,
                status="complete",
                exit_code=0,
                details={"removedFiles": removed, "removedFileCount": len(removed)},
            )

        if not effective_skip_docs_rebuild:
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
            runner.run_command("rebuild_docs_data", rebuild_cmd, repo_root)

        if not effective_skip_character_catalog:
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
            runner.run_command("build_character_catalog", character_cmd, repo_root)

        runner.record_artifacts({key: repo_root / value for key, value in GENERATED_ARTIFACTS.items()})
        runner.merge_counts(collect_generated_counts(repo_root))

        if not effective_skip_git_plan:
            git_plan_output = args.git_plan_output or (runner.log_dir / "GitCommitPlan.json")
            if not git_plan_output.is_absolute():
                git_plan_output = repo_root / git_plan_output
            git_planner_command = "commit-batches" if effective_git_commit_batches else "plan"
            stage_name = "git_commit_batches" if effective_git_commit_batches else "git_plan"
            message_version = "data"
            if archive_sources:
                message_version = archive_sources.dataset_version
            elif previous_summary:
                message_version = (
                    previous_summary.get("archive", {}).get("datasetVersion")
                    or message_version
                )
            git_cmd = [
                python_exe,
                "tools/PlanGitCommits.py",
                git_planner_command,
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
            if effective_git_commit_batches:
                git_cmd.append("--execute")
            if effective_git_push_each:
                git_cmd.append("--push-each")
            runner.run_command(stage_name, git_cmd, repo_root)
            compatibility_plan = runner.copy_git_plan_compatibility(git_plan_output)
            runner.record_git_plan(git_plan_output, compatibility_plan)

        runner.complete()
        if runner.data.get("releaseDecision", {}).get("status") == "fail":
            reasons = runner.data["releaseDecision"].get("reasons") or []
            for reason in reasons:
                print(f"[ERROR] Release policy failed: {reason}")
            return 1

        print("[INFO] Update pipeline complete.")
        return 0
    except PipelineStepError as exc:
        runner.fail(str(exc))
        return exc.returncode
    except Exception as exc:  # Defensive: failed runs should still leave a summary.
        print(f"[ERROR] {exc}")
        runner.fail(str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
