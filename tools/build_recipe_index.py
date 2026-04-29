import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


ITEM_ID_PATTERN = re.compile(r"(ITEM_[A-Za-z0-9_]+|DA_[A-Za-z0-9_]+)")


def load_json(path: Path) -> list[dict[str, Any]] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"[WARN] JSON parse failed: {path} ({exc})")
        return None
    if not isinstance(data, list) or not data:
        print(f"[WARN] Unexpected JSON root: {path}")
        return None
    return data


def extract_entry(data: list[dict[str, Any]]) -> dict[str, Any] | None:
    for entry in data:
        if isinstance(entry, dict) and entry.get("Properties"):
            return entry
    return data[0] if data else None


def resolve_object_path(object_path: str) -> Path | None:
    if not object_path:
        return None
    cleaned = object_path.replace("RSDragonwilds/Content/", "")
    cleaned = cleaned.rstrip(".0")
    return Path(cleaned + ".png")


def file_hash(path: Path) -> str:
    hasher = hashlib.sha1()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def build_png_name_index(root: Path) -> dict[str, list[Path]]:
    index: dict[str, list[Path]] = {}
    if not root.exists():
        return index
    for png in root.rglob("*.png"):
        key = png.name.lower()
        index.setdefault(key, []).append(png)
    return index


def resolve_icon_abs(object_path: str, content_root: Path, png_index: dict[str, list[Path]]) -> Path | None:
    icon_rel = resolve_object_path(object_path)
    if not icon_rel:
        return None
    direct = content_root / icon_rel
    if direct.exists():
        return direct
    content_prefixed = content_root / "Content" / icon_rel
    if content_prefixed.exists():
        return content_prefixed
    by_name = png_index.get(icon_rel.name.lower(), [])
    if not by_name:
        return None
    if len(by_name) == 1:
        return by_name[0]
    rel_tail = icon_rel.as_posix().lower()
    for candidate in by_name:
        if candidate.as_posix().lower().endswith(rel_tail):
            return candidate
    return by_name[0]


def copy_icon(icon_abs: Path, icons_dir: Path) -> str:
    icons_dir.mkdir(parents=True, exist_ok=True)
    dest = icons_dir / icon_abs.name
    if dest.exists():
        if file_hash(dest) == file_hash(icon_abs):
            return dest.name
        base = icon_abs.stem
        suffix = file_hash(icon_abs)[:8]
        dest = icons_dir / f"{base}_{suffix}{icon_abs.suffix}"
    dest.write_bytes(icon_abs.read_bytes())
    return dest.name


def extract_item_id(item_data: dict[str, Any]) -> str:
    object_name = item_data.get("ObjectName", "")
    object_path = item_data.get("ObjectPath", "")
    match = ITEM_ID_PATTERN.search(str(object_name))
    if match:
        return match.group(1)
    if object_path:
        return Path(object_path).stem
    return ""


def build_item_lookup(
    source_dirs: list[Path],
    content_root: Path,
    icons_dir: Path,
    placeholder_icon: str,
) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    icon_missing = 0
    item_count = 0
    png_index = build_png_name_index(content_root)

    for source_dir in source_dirs:
        if not source_dir.exists():
            print(f"[WARN] Item source not found: {source_dir}")
            continue
        for pattern in ("ITEM_*.json", "DA_Consumable_*.json"):
            for file_path in sorted(source_dir.rglob(pattern)):
                if "_MeshData_" in file_path.name:
                    continue
                data = load_json(file_path)
                if not data:
                    continue
                entry = extract_entry(data)
                if not entry:
                    continue
                props = entry.get("Properties", {})
                item_id = entry.get("Name") or file_path.stem
                display_name = (
                    props.get("Name", {}).get("SourceString")
                    or props.get("Name", {}).get("LocalizedString")
                    or props.get("InternalName")
                    or item_id
                )
                icon_obj = props.get("Icon", {}).get("ObjectPath") or ""
                icon_file = ""
                icon_abs = resolve_icon_abs(icon_obj, content_root, png_index)
                if icon_abs and icon_abs.exists():
                    icon_file = copy_icon(icon_abs, icons_dir)
                else:
                    icon_missing += 1
                    if icon_obj:
                        print(f"[WARN] Icon not found: {file_path} -> {icon_obj}")
                    else:
                        print(f"[WARN] Icon missing: {file_path}")

                if not icon_file and placeholder_icon:
                    icon_file = placeholder_icon

                lookup[item_id] = {
                    "item_id": item_id,
                    "display_name": display_name,
                    "persistence_id": props.get("PersistenceID") or "",
                    "internal_name": props.get("InternalName") or "",
                    "icon": icon_file,
                }
                item_count += 1

    print(f"[INFO] Items indexed: {item_count}")
    print(f"[INFO] Missing item icons: {icon_missing}")
    return lookup


def build_recipe_index(
    recipes_dir: Path,
    item_lookup: dict[str, dict[str, Any]],
    content_root: Path,
    icons_dir: Path,
    placeholder_icon: str,
) -> list[dict[str, Any]]:
    recipes: list[dict[str, Any]] = []
    icon_missing = 0
    placeholder_used = 0
    skipped_recipes = 0
    recipe_count = 0

    for file_path in sorted(recipes_dir.rglob("RECIPE_*.json")):
        data = load_json(file_path)
        if not data:
            continue
        entry = extract_entry(data)
        if not entry:
            continue
        props = entry.get("Properties", {})

        def enrich_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
            nonlocal icon_missing
            nonlocal placeholder_used
            enriched: list[dict[str, Any]] = []
            for item in items:
                item_data = item.get("ItemData", {}) or {}
                item_id = extract_item_id(item_data)
                count = item.get("Count", 1)
                details = item_lookup.get(item_id, {})
                icon_name = details.get("icon", "")
                if not icon_name:
                    icon_missing += 1
                    if placeholder_icon:
                        icon_name = placeholder_icon
                        placeholder_used += 1
                enriched.append(
                    {
                        "item_id": item_id,
                        "count": count,
                        "display_name": details.get("display_name", item_id),
                        "persistence_id": details.get("persistence_id", ""),
                        "icon": icon_name,
                    }
                )
            return enriched

        items_consumed = enrich_items(props.get("ItemsConsumed", []) or [])
        items_created = enrich_items(props.get("ItemsCreated", []) or [])

        valid_created = [
            item for item in items_created if item.get("item_id") and item.get("count", 0) > 0
        ]
        if not valid_created:
            skipped_recipes += 1
            continue

        icon = valid_created[0]["icon"]
        if not icon and placeholder_icon:
            icon = placeholder_icon
            placeholder_used += 1

        display_name = valid_created[0]["display_name"] or entry.get("Name")

        recipes.append(
            {
                "name": entry.get("Name", ""),
                "internal_name": props.get("InternalName", ""),
                "persistence_id": props.get("PersistenceID", ""),
                "row_name": props.get("OnCraftXpEvent", {}).get("RowName", ""),
                "display_name": display_name,
                "icon": icon,
                "items_created": items_created,
                "items_consumed": items_consumed,
            }
        )
        recipe_count += 1

    print(f"[INFO] Recipes indexed: {recipe_count}")
    print(f"[INFO] Recipes skipped (no output item): {skipped_recipes}")
    print(f"[INFO] Missing recipe icons: {icon_missing}")
    print(f"[INFO] Placeholder icons used: {placeholder_used}")
    return recipes


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a UI-friendly recipe catalog with icons and tooltips."
    )
    parser.add_argument(
        "--recipes",
        default="data/recipes",
        help="Directory containing RECIPE_*.json files.",
    )
    parser.add_argument(
        "--items",
        default="data/items",
        help="Directory containing ITEM_*.json files.",
    )
    parser.add_argument(
        "--consumables",
        default="data/consumables",
        help="Directory containing DA_Consumable_*.json files.",
    )
    parser.add_argument(
        "--content-root",
        default="data/icons",
        help="Root used to resolve icon ObjectPath values.",
    )
    parser.add_argument(
        "--output",
        default="website/tools/recipe-unlocker/data/recipes.json",
        help="Output JSON path for the recipe catalog.",
    )
    parser.add_argument(
        "--icons-dir",
        default="website/shared/icons",
        help="Directory to copy recipe/item icons into.",
    )
    args = parser.parse_args()

    recipes_dir = Path(args.recipes)
    items_dir = Path(args.items)
    consumables_dir = Path(args.consumables)
    content_root = Path(args.content_root)
    output_path = Path(args.output)
    icons_dir = Path(args.icons_dir)

    if not recipes_dir.exists():
        print(f"[ERROR] Recipes directory not found: {recipes_dir}")
        return 1
    if not items_dir.exists():
        print(f"[ERROR] Items directory not found: {items_dir}")
        return 1

    placeholder_source = Path("website") / "shared" / "game-ui" / "T_Icon_Placeholder.png"
    placeholder_icon = ""
    if placeholder_source.exists():
        placeholder_icon = copy_icon(placeholder_source, icons_dir)
    else:
        fallback = next(content_root.rglob("T_Icon_Placeholder.png"), None)
        if fallback:
            placeholder_icon = copy_icon(fallback, icons_dir)
            print(f"[INFO] Using fallback placeholder icon from content: {fallback}")
        else:
            print(f"[WARN] Placeholder icon missing: {placeholder_source}")

    item_lookup = build_item_lookup(
        source_dirs=[items_dir, consumables_dir],
        content_root=content_root,
        icons_dir=icons_dir,
        placeholder_icon=placeholder_icon,
    )
    recipes = build_recipe_index(
        recipes_dir, item_lookup, content_root, icons_dir, placeholder_icon
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(recipes, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    print(f"[INFO] Wrote recipe catalog: {output_path}")
    print(f"[INFO] Icons output: {icons_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
