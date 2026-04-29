import argparse
import hashlib
import json
import shutil
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


JSON_SUFFIX = ".json"
PNG_SUFFIX = ".png"
CORE_CATEGORIES = ("recipes", "items", "consumables", "spells", "icons")
ICON_PREFIXES = ("t_icon_", "t_skill_")


def sha1_file(path: Path) -> str:
    hasher = hashlib.sha1()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def sanitize_rel_path(relative_path: Path) -> Path:
    parts = [part.replace(":", "_") for part in relative_path.parts]
    return Path(*parts)


def classify_core_json(path: Path) -> str | None:
    upper_name = path.name.upper()
    if "_MESHDATA_" in upper_name:
        return None
    if upper_name.startswith("RECIPE_"):
        return "recipes"
    if upper_name.startswith("ITEM_"):
        return "items"
    if upper_name.startswith("DA_CONSUMABLE_"):
        return "consumables"
    if upper_name.startswith("USD_"):
        return "spells"
    return None


def is_icon_file(path: Path) -> bool:
    return path.suffix.lower() == PNG_SUFFIX and path.name.lower().startswith(ICON_PREFIXES)


def normalize_object_path_to_png_rel(object_path: str) -> Path | None:
    raw = str(object_path or "").strip()
    if not raw:
        return None
    cleaned = raw.replace("\\", "/")
    cleaned = cleaned.replace("RSDragonwilds/Content/", "")
    cleaned = cleaned.rstrip(".0")
    cleaned = cleaned.lstrip("/")
    if not cleaned:
        return None
    parts = cleaned.split("/")
    leaf = parts[-1]
    if "." in leaf:
        leaf = leaf.split(".")[0]
    parts[-1] = leaf
    rel = Path("/".join(parts))
    if rel.suffix.lower() != PNG_SUFFIX:
        rel = rel.with_suffix(PNG_SUFFIX)
    return rel


def iter_object_paths(value: object):
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).lower() == "objectpath" and isinstance(item, str):
                yield item
            yield from iter_object_paths(item)
    elif isinstance(value, list):
        for item in value:
            yield from iter_object_paths(item)


def resolve_referenced_icon(
    rel_png: Path,
    png_by_rel: dict[str, Path],
    png_by_name: dict[str, list[Path]],
) -> Path | None:
    key = rel_png.as_posix().lower()
    direct = png_by_rel.get(key)
    if direct:
        return direct
    by_name = png_by_name.get(rel_png.name.lower(), [])
    if not by_name:
        return None
    if len(by_name) == 1:
        return by_name[0]
    tail = rel_png.as_posix().lower()
    for candidate in by_name:
        if candidate.as_posix().lower().endswith(tail):
            return candidate
    return by_name[0]


def destination_path(
    source_file: Path,
    source_root: Path,
    category_dir: Path,
    flat: bool,
) -> Path:
    if flat:
        return category_dir / source_file.name
    rel = sanitize_rel_path(source_file.relative_to(source_root))
    return category_dir / rel


def unique_destination(dest: Path, source_file: Path) -> Path:
    if not dest.exists():
        return dest
    if sha1_file(dest) == sha1_file(source_file):
        return dest
    suffix = sha1_file(source_file)[:8]
    return dest.with_name(f"{dest.stem}__{suffix}{dest.suffix}")


def copy_file(source_file: Path, dest: Path, dry_run: bool) -> str:
    if dest.exists():
        if sha1_file(dest) == sha1_file(source_file):
            return "duplicate-skip"
    if dry_run:
        return "copied-dry-run"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(source_file.read_bytes())
    return "copied"


def copy_external_jsons(
    source_dir: Path,
    output_dir: Path,
    dry_run: bool,
) -> tuple[int, int]:
    if not source_dir.exists():
        return 0, 0
    discovered = 0
    copied = 0
    for source_file in sorted(source_dir.rglob(f"*{JSON_SUFFIX}")):
        discovered += 1
        rel = sanitize_rel_path(source_file.relative_to(source_dir))
        dest = unique_destination(output_dir / rel, source_file)
        action = copy_file(source_file, dest, dry_run)
        if action != "duplicate-skip":
            copied += 1
    return discovered, copied


def discover_and_copy(
    game_root: Path,
    output_root: Path,
    manifest_path: Path,
    location_data_root: Path | None,
    loot_data_root: Path | None,
    clean: bool,
    flat: bool,
    dry_run: bool,
) -> int:
    if not game_root.exists():
        print(f"[ERROR] Game root not found: {game_root}")
        return 1

    if clean and output_root.exists():
        if dry_run:
            print(f"[INFO] Dry-run clean: would delete {output_root}")
        else:
            shutil.rmtree(output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    category_counts: dict[str, int] = defaultdict(int)
    category_samples: dict[str, list[str]] = defaultdict(list)
    category_roots: dict[str, set[str]] = defaultdict(set)
    copied_counts: dict[str, int] = defaultdict(int)
    skipped_duplicates = 0
    scanned_json = 0
    unmatched_json = 0
    unmatched_samples: list[str] = []
    referenced_icon_rels: set[Path] = set()

    for source_file in sorted(game_root.rglob(f"*{JSON_SUFFIX}")):
        scanned_json += 1
        category = classify_core_json(source_file)
        if category is None:
            unmatched_json += 1
            if len(unmatched_samples) < 20:
                unmatched_samples.append(source_file.relative_to(game_root).as_posix())
            continue

        category_counts[category] += 1
        rel = source_file.relative_to(game_root)
        top = rel.parts[0] if rel.parts else "."
        category_roots[category].add(top)
        if len(category_samples[category]) < 5:
            category_samples[category].append(rel.as_posix())

        category_dir = output_root / category
        initial_dest = destination_path(source_file, game_root, category_dir, flat)
        dest = unique_destination(initial_dest, source_file)
        action = copy_file(source_file, dest, dry_run)
        if action == "duplicate-skip":
            skipped_duplicates += 1
        else:
            copied_counts[category] += 1

        try:
            parsed = json.loads(source_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            parsed = None
        if parsed is not None:
            for object_path in iter_object_paths(parsed):
                rel_png = normalize_object_path_to_png_rel(object_path)
                if rel_png:
                    referenced_icon_rels.add(rel_png)

    png_by_rel: dict[str, Path] = {}
    png_by_name: dict[str, list[Path]] = defaultdict(list)
    all_pngs = sorted(game_root.rglob(f"*{PNG_SUFFIX}"))
    for png in all_pngs:
        rel_key = png.relative_to(game_root).as_posix().lower()
        png_by_rel[rel_key] = png
        png_by_name[png.name.lower()].append(png)

    selected_icons: set[Path] = set()
    referenced_icons_resolved = 0
    for rel_png in sorted(referenced_icon_rels, key=lambda p: p.as_posix().lower()):
        resolved = resolve_referenced_icon(rel_png, png_by_rel, png_by_name)
        if not resolved:
            continue
        selected_icons.add(resolved)
        referenced_icons_resolved += 1

    for source_icon in all_pngs:
        if is_icon_file(source_icon):
            selected_icons.add(source_icon)

    icons_discovered = len(selected_icons)
    icons_copied = 0
    icon_samples: list[str] = []
    icons_dir = output_root / "icons"
    for source_icon in sorted(selected_icons):
        if len(icon_samples) < 20:
            icon_samples.append(source_icon.relative_to(game_root).as_posix())
        icon_dest = destination_path(source_icon, game_root, icons_dir, flat=False)
        icon_dest = unique_destination(icon_dest, source_icon)
        action = copy_file(source_icon, icon_dest, dry_run)
        if action != "duplicate-skip":
            icons_copied += 1

    category_counts["icons"] = icons_discovered
    copied_counts["icons"] = icons_copied

    external_imports: dict[str, dict[str, object]] = {}
    if location_data_root:
        loc_discovered, loc_copied = copy_external_jsons(
            location_data_root, output_root / "location_data", dry_run
        )
        external_imports["location_data"] = {
            "source_root": str(location_data_root),
            "files_discovered": loc_discovered,
            "files_copied": loc_copied,
            "found": location_data_root.exists(),
        }
    if loot_data_root:
        loot_discovered, loot_copied = copy_external_jsons(
            loot_data_root, output_root / "loot_data", dry_run
        )
        external_imports["loot_data"] = {
            "source_root": str(loot_data_root),
            "files_discovered": loot_discovered,
            "files_copied": loot_copied,
            "found": loot_data_root.exists(),
        }

    manifest = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "game_root": str(game_root),
        "output_root": str(output_root),
        "options": {
            "core_categories": CORE_CATEGORIES,
            "location_data_root": str(location_data_root) if location_data_root else "",
            "loot_data_root": str(loot_data_root) if loot_data_root else "",
            "clean": clean,
            "flat": flat,
            "dry_run": dry_run,
        },
        "summary": {
            "json_scanned": scanned_json,
            "json_unmatched": unmatched_json,
            "duplicates_skipped": skipped_duplicates,
            "unmatched_samples": unmatched_samples,
        },
        "categories": {
            name: {
                "files_discovered": category_counts[name],
                "files_copied": copied_counts.get(name, 0),
                "source_roots": sorted(category_roots[name]),
                "sample_files": category_samples[name],
            }
            for name in sorted(category_counts)
        },
        "icons": {"sample_files": icon_samples},
        "external_imports": external_imports,
        "icon_discovery": {
            "object_paths_found": len(referenced_icon_rels),
            "object_paths_resolved": referenced_icons_resolved,
            "prefixes": ICON_PREFIXES,
        },
    }

    if not dry_run:
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=True) + "\n",
            encoding="utf-8",
        )

    print(f"[INFO] Game root: {game_root}")
    print(f"[INFO] Output root: {output_root}")
    print(f"[INFO] JSON scanned: {scanned_json}")
    print(f"[INFO] JSON unmatched: {unmatched_json}")
    print(f"[INFO] Duplicate files skipped: {skipped_duplicates}")
    for name in sorted(category_counts):
        print(
            f"[INFO] Category {name}: "
            f"discovered={category_counts[name]} copied={copied_counts.get(name, 0)}"
        )
    for key in ("location_data", "loot_data"):
        details = external_imports.get(key)
        if details:
            print(
                f"[INFO] External {key}: discovered={details['files_discovered']} "
                f"copied={details['files_copied']} found={details['found']}"
            )
    if dry_run:
        print("[INFO] Dry run only: no files were written.")
    else:
        print(f"[INFO] Wrote manifest: {manifest_path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Discover and ingest core game files from a root folder into "
            "typed raw data folders. Focuses on ITEM_, RECIPE_, "
            "DA_Consumable_, USD_, and icon PNG discovery from ObjectPath references."
        )
    )
    parser.add_argument(
        "--game-root",
        required=True,
        help="Top-level game archive root to scan (e.g. E:\\Github\\RSDWArchive\\0.11.0.3).",
    )
    parser.add_argument(
        "--output-root",
        default="data",
        help="Destination root for discovered files.",
    )
    parser.add_argument(
        "--manifest",
        default="",
        help="Path to write discovery manifest JSON (default: <output-root>/_ingest_manifest.json).",
    )
    parser.add_argument(
        "--location-data-root",
        default="",
        help="Optional external LocationData folder to import JSON outputs from.",
    )
    parser.add_argument(
        "--loot-data-root",
        default="",
        help="Optional external LootData folder to import JSON outputs from.",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Delete output root before ingest to remove stale files.",
    )
    parser.add_argument(
        "--flat",
        action="store_true",
        help="Flatten copied files per category (default: preserve relative paths).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print discovery stats without writing files.",
    )
    args = parser.parse_args()

    output_root = Path(args.output_root)
    manifest_path = Path(args.manifest) if args.manifest else output_root / "_ingest_manifest.json"

    return discover_and_copy(
        game_root=Path(args.game_root),
        output_root=output_root,
        manifest_path=manifest_path,
        location_data_root=Path(args.location_data_root) if args.location_data_root else None,
        loot_data_root=Path(args.loot_data_root) if args.loot_data_root else None,
        clean=args.clean,
        flat=args.flat,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    raise SystemExit(main())
