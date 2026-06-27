from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from archive_sources import DEFAULT_ARCHIVE_ROOT, resolve_archive_sources


SUMMARY_SCHEMA = "RSDWTools.UpdatePipeline.v1"


REQUIRED_JSON_FILES: dict[str, Path] = {
    "ingest_manifest": Path("data") / "_ingest_manifest.json",
    "item_editor_catalog": Path("website") / "tools" / "item-editor" / "data" / "catalog.json",
    "recipe_catalog": Path("website") / "tools" / "recipe-unlocker" / "data" / "recipes.json",
    "quest_catalog": Path("website") / "tools" / "quest-editor" / "data" / "quests.json",
    "spell_catalog": Path("website") / "tools" / "spell-editor" / "data" / "spells.json",
    "character_catalog": Path("website") / "tools" / "character-editor" / "data" / "character_catalog.json",
    "chest_item_catalog": Path("website") / "data" / "chest_item_catalog.json",
    "loot_data": Path("website") / "data" / "loot_data.json",
    "location_data": Path("website") / "data" / "location_data.json",
    "mapdata_index": Path("website") / "data" / "mapdata_index.json",
}


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def fail(failures: list[str], message: str) -> None:
    failures.append(message)


def check(condition: bool, failures: list[str], message: str) -> None:
    if not condition:
        failures.append(message)


def count_list(value: Any) -> int:
    return len(value) if isinstance(value, list) else 0


def validate_catalogs(repo_root: Path, failures: list[str], notes: list[str]) -> dict[str, int]:
    loaded: dict[str, Any] = {}
    counts: dict[str, int] = {}

    for key, rel_path in REQUIRED_JSON_FILES.items():
        path = repo_root / rel_path
        if not path.exists():
            fail(failures, f"Missing generated JSON: {rel_path}")
            continue
        try:
            loaded[key] = load_json(path)
        except json.JSONDecodeError as exc:
            fail(failures, f"Invalid generated JSON: {rel_path} ({exc})")

    item_catalog = loaded.get("item_editor_catalog")
    if isinstance(item_catalog, dict):
        tabs = item_catalog.get("tabs")
        check(isinstance(tabs, dict), failures, "Item editor catalog is missing tabs.")
        if isinstance(tabs, dict):
            item_count = 0
            for tab in ("bag", "rune", "ammo", "quest"):
                tab_payload = tabs.get(tab)
                if isinstance(tab_payload, list):
                    item_count += len(tab_payload)
                elif isinstance(tab_payload, dict) and isinstance(tab_payload.get("items"), list):
                    item_count += len(tab_payload["items"])
                else:
                    fail(failures, f"Item editor tab missing items: {tab}")
            counts["itemEditorItems"] = item_count
            check(counts["itemEditorItems"] > 0, failures, "Item editor catalog is empty.")

    recipes = loaded.get("recipe_catalog")
    counts["recipes"] = count_list(recipes)
    check(counts["recipes"] > 0, failures, "Recipe catalog is empty or not a list.")

    quest_catalog = loaded.get("quest_catalog")
    if isinstance(quest_catalog, dict):
        quests = quest_catalog.get("quests")
        counts["quests"] = count_list(quests)
        check(counts["quests"] > 0, failures, "Quest catalog has no quests.")
    else:
        fail(failures, "Quest catalog is not an object.")

    spells = loaded.get("spell_catalog")
    counts["spells"] = count_list(spells)
    check(counts["spells"] > 0, failures, "Spell catalog is empty or not a list.")

    character = loaded.get("character_catalog")
    if isinstance(character, dict):
        for key, count_key in (
            ("Skills", "characterSkills"),
            ("Mounts", "mounts"),
            ("VendorReputations", "vendorReputations"),
        ):
            counts[count_key] = count_list(character.get(key))
            check(counts[count_key] > 0, failures, f"Character catalog has no {key}.")
    else:
        fail(failures, "Character catalog is not an object.")

    chest_items = loaded.get("chest_item_catalog")
    counts["chestItems"] = count_list(chest_items)
    check(counts["chestItems"] > 0, failures, "Chest item catalog is empty or not a list.")

    mapdata = loaded.get("mapdata_index")
    if isinstance(mapdata, dict):
        counts["mapPoints"] = count_list(mapdata.get("points"))
        check(counts["mapPoints"] > 0, failures, "Map data index has no points.")
    else:
        fail(failures, "Map data index is not an object.")

    location_data = loaded.get("location_data")
    counts["locationEntries"] = len(location_data) if isinstance(location_data, dict) else 0
    check(counts["locationEntries"] > 0, failures, "Location data output is empty or not an object.")

    loot_data = loaded.get("loot_data")
    if isinstance(loot_data, dict):
        tables = loot_data.get("tables")
        counts["lootTables"] = len(tables) if isinstance(tables, dict) else 0
        check(counts["lootTables"] > 0, failures, "Loot data has no tables.")
    else:
        fail(failures, "Loot data output is not an object.")

    manifest = loaded.get("ingest_manifest")
    if isinstance(manifest, dict):
        summary = manifest.get("summary")
        scanned = summary.get("json_scanned") if isinstance(summary, dict) else 0
        counts["ingestJsonScanned"] = int(scanned or 0)
        check(counts["ingestJsonScanned"] > 0, failures, "Ingest manifest has no scanned JSON count.")
    else:
        fail(failures, "Ingest manifest is not an object.")

    notes.append(
        "Catalog counts: "
        + ", ".join(f"{key}={value:,}" for key, value in sorted(counts.items()))
    )
    return counts


def validate_summary(
    summary: dict[str, Any],
    *,
    failures: list[str],
    allow_unknown_warnings: bool,
) -> None:
    check(summary.get("schema") == SUMMARY_SCHEMA, failures, "Pipeline summary schema is missing or invalid.")
    check(summary.get("project") == "RSDWTools", failures, "Pipeline summary project is not RSDWTools.")
    check(summary.get("status") == "complete", failures, "Pipeline summary status is not complete.")

    release_decision = summary.get("releaseDecision")
    if isinstance(release_decision, dict):
        decision_status = release_decision.get("status")
        if decision_status == "fail" and not allow_unknown_warnings:
            reasons = ", ".join(release_decision.get("reasons") or [])
            fail(failures, f"Pipeline release decision failed: {reasons}")

    categories = summary.get("warnings", {}).get("categories", {})
    if isinstance(categories, dict):
        for category, details in categories.items():
            severity = details.get("severity") if isinstance(details, dict) else None
            if severity == "fatal":
                fail(failures, f"Fatal warning category present: {category}")
            if category == "unknown_warning" and not allow_unknown_warnings:
                fail(failures, "Unknown warning category present.")


def validate_archive_identity(
    summary: dict[str, Any],
    *,
    archive_root: Path,
    game_root: str,
    expected_dataset_version: str,
    failures: list[str],
    notes: list[str],
) -> None:
    archive = summary.get("archive")
    check(isinstance(archive, dict) and bool(archive), failures, "Pipeline summary has no archive identity.")
    if not isinstance(archive, dict):
        return

    summary_version = str(archive.get("datasetVersion") or "")
    summary_dataset_root = Path(str(archive.get("datasetRoot") or ""))

    if expected_dataset_version:
        expected_version = expected_dataset_version
    elif game_root:
        expected_version = Path(game_root).name
    else:
        try:
            sources = resolve_archive_sources(archive_root=archive_root, game_root=None)
        except ValueError as exc:
            fail(failures, f"Could not resolve current archive config: {exc}")
            return
        expected_version = sources.dataset_version
        check(
            summary_dataset_root.resolve() == sources.game_root.resolve(),
            failures,
            f"Archive dataset root mismatch: summary={summary_dataset_root}, current={sources.game_root}",
        )

    check(
        summary_version == expected_version,
        failures,
        f"Archive dataset version mismatch: summary={summary_version}, expected={expected_version}",
    )

    for key in ("datasetRoot", "configPath", "locationDataRoot", "lootDataRoot", "questDataPath"):
        raw = archive.get(key)
        check(bool(raw) and Path(str(raw)).exists(), failures, f"Archive path missing: {key}={raw}")

    notes.append(f"Archive dataset: {summary_version}")


def run_git(repo_root: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def validate_published(summary: dict[str, Any], repo_root: Path, failures: list[str], notes: list[str]) -> None:
    upstream = run_git(repo_root, ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"])
    if upstream.returncode != 0:
        fail(failures, "Current branch has no upstream configured.")
        return
    upstream_name = upstream.stdout.strip()
    notes.append(f"Upstream: {upstream_name}")

    status = run_git(repo_root, ["status", "--porcelain=v1", "--untracked-files=all"])
    if status.returncode != 0:
        fail(failures, f"Could not inspect git status: {status.stderr.strip()}")
    elif status.stdout.strip():
        git_mode = summary.get("gitMode")
        if git_mode in ("commit-only", "push-each"):
            fail(failures, "Working tree is not clean after publish mode.")

    git_mode = summary.get("gitMode")
    if git_mode == "push-each":
        divergence = run_git(repo_root, ["rev-list", "--left-right", "--count", f"HEAD...{upstream_name}"])
        if divergence.returncode != 0:
            fail(failures, f"Could not compare branch to upstream: {divergence.stderr.strip()}")
        else:
            ahead, behind = [int(part) for part in divergence.stdout.strip().split()]
            check(ahead == 0 and behind == 0, failures, f"Branch differs from upstream: ahead={ahead}, behind={behind}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate RSDWTools generated pipeline outputs.")
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--summary", type=Path, default=None, help="PipelineRun.json to validate.")
    parser.add_argument("--archive-root", type=Path, default=DEFAULT_ARCHIVE_ROOT)
    parser.add_argument("--game-root", default="", help="Expected archive dataset root.")
    parser.add_argument("--expected-dataset-version", default="", help="Expected archive dataset version.")
    parser.add_argument(
        "--allow-unknown-warnings",
        action="store_true",
        help="Allow unknown warning categories during validation.",
    )
    parser.add_argument(
        "--mode",
        choices=["local", "published"],
        default="local",
        help="Validation scope.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    repo_root = args.repo_root.resolve()
    summary_path = args.summary or (repo_root / "PipelineRun.json")
    if not summary_path.is_absolute():
        summary_path = repo_root / summary_path

    failures: list[str] = []
    notes: list[str] = []

    if not summary_path.exists():
        print(f"[ERROR] Pipeline summary not found: {summary_path}")
        return 1

    try:
        summary = load_json(summary_path)
    except json.JSONDecodeError as exc:
        print(f"[ERROR] Pipeline summary is not valid JSON: {summary_path} ({exc})")
        return 1

    validate_summary(
        summary,
        failures=failures,
        allow_unknown_warnings=args.allow_unknown_warnings,
    )
    validate_archive_identity(
        summary,
        archive_root=args.archive_root,
        game_root=args.game_root,
        expected_dataset_version=args.expected_dataset_version,
        failures=failures,
        notes=notes,
    )
    validate_catalogs(repo_root, failures, notes)

    if args.mode == "published":
        validate_published(summary, repo_root, failures, notes)

    for note in notes:
        print(f"[INFO] {note}")

    if failures:
        for failure in failures:
            print(f"[ERROR] {failure}")
        return 1

    print("[INFO] Pipeline output validation complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
