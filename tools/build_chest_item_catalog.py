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


def extract_item_id(entry: dict[str, Any], file_path: Path) -> str:
    name = entry.get("Name") or ""
    match = ITEM_ID_PATTERN.search(str(name))
    if match:
        return match.group(1)
    return file_path.stem


def extract_display_name(props: dict[str, Any], fallback: str) -> str:
    return (
        props.get("Name", {}).get("SourceString")
        or props.get("Name", {}).get("LocalizedString")
        or props.get("InternalName")
        or fallback
    )


def build_item_catalog(
    source_dirs: list[Path], content_root: Path, icons_dir: Path
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    icon_missing = 0
    item_count = 0
    png_index = build_png_name_index(content_root)

    for source_dir in source_dirs:
        if not source_dir.exists():
            print(f"[WARN] Item source not found: {source_dir}")
            continue
        for file_path in sorted(source_dir.rglob("ITEM_*.json")) + sorted(
            source_dir.rglob("DA_Consumable_*.json")
        ):
            if "_MeshData_" in file_path.name:
                continue
            data = load_json(file_path)
            if not data:
                continue
            entry = next((row for row in data if row.get("Properties")), data[0])
            props = entry.get("Properties", {})
            item_id = extract_item_id(entry, file_path)
            display_name = extract_display_name(props, item_id)

            icon_obj = props.get("Icon", {}).get("ObjectPath") or ""
            icon_file = ""
            icon_abs = resolve_icon_abs(icon_obj, content_root, png_index)
            if icon_abs and icon_abs.exists():
                icon_file = copy_icon(icon_abs, icons_dir)
            else:
                icon_missing += 1
                if icon_obj:
                    print(f"[WARN] Icon not found: {file_path} -> {icon_obj}")

            items.append(
                {
                    "item_id": item_id,
                    "display_name": display_name,
                    "icon": icon_file,
                }
            )
            item_count += 1

    print(f"[INFO] Items indexed: {item_count}")
    print(f"[INFO] Missing item icons: {icon_missing}")
    return items


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a chest item catalog from ITEM_*/DA_* definitions."
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
        help="Content root used to resolve icon ObjectPath values.",
    )
    parser.add_argument(
        "--output",
        default="website/data/chest_item_catalog.json",
        help="Output JSON path for the chest item catalog.",
    )
    parser.add_argument(
        "--icons-dir",
        default="website/shared/icons",
        help="Directory to copy chest item icons into.",
    )
    args = parser.parse_args()

    items_dir = Path(args.items)
    consumables_dir = Path(args.consumables)
    content_root = Path(args.content_root)
    output_path = Path(args.output)
    icons_dir = Path(args.icons_dir)

    if not items_dir.exists():
        print(f"[ERROR] Items directory not found: {items_dir}")
        return 1

    items = build_item_catalog([items_dir, consumables_dir], content_root, icons_dir)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(items, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    print(f"[INFO] Wrote chest item catalog: {output_path}")
    print(f"[INFO] Icons output: {icons_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
