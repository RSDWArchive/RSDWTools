import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from icon_paths import extract_asset_reference, normalize_asset_path_to_png_rel


SKILL_DISPLAY_ORDER = (
    "Woodcutting",
    "Artisan",
    "Attack",
    "Construction",
    "Cooking",
    "Farming",
    "Fishing",
    "Magic",
    "Mining",
    "Ranged",
    "Runecrafting",
)


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def text_value(value: object) -> str:
    if not isinstance(value, dict):
        return ""
    for key in ("SourceString", "LocalizedString", "CultureInvariantString"):
        text = value.get(key)
        if isinstance(text, str) and text:
            return text
    return ""


def extract_rows(data: object) -> list[str]:
    rows = {}
    if isinstance(data, list) and data:
        first = data[0]
        if isinstance(first, dict):
            rows = first.get("Rows", {}) or {}
    elif isinstance(data, dict):
        rows = data.get("Rows", {}) or {}
    if not isinstance(rows, dict):
        return []
    return sorted(rows.keys())


def pick_skill_entry(data: object) -> dict[str, Any] | None:
    if not isinstance(data, list) or not data:
        return None
    for entry in data:
        if not isinstance(entry, dict):
            continue
        props = entry.get("Properties") or {}
        if entry.get("Type") == "SkillData" and isinstance(props, dict):
            return entry
    for entry in data:
        if not isinstance(entry, dict):
            continue
        props = entry.get("Properties") or {}
        if (
            isinstance(props, dict)
            and props.get("SkillType")
            and props.get("PersistenceID")
        ):
            return entry
    return None


def normalize_object_path(object_path: str) -> Path | None:
    return normalize_asset_path_to_png_rel(object_path)


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
    for png in sorted(root.rglob("*.png")):
        index.setdefault(png.name.lower(), []).append(png)
    return index


def resolve_icon_abs(
    object_path: str,
    icon_root: Path,
    png_index: dict[str, list[Path]],
) -> Path | None:
    icon_rel = normalize_object_path(object_path)
    if not icon_rel:
        return None
    for candidate in (icon_root / icon_rel, icon_root / "textures" / icon_rel):
        if candidate.exists():
            return candidate
    by_name = png_index.get(icon_rel.name.lower(), [])
    if not by_name:
        return None
    if len(by_name) == 1:
        return by_name[0]
    tail = icon_rel.as_posix().lower()
    for candidate in by_name:
        if candidate.as_posix().lower().endswith(tail):
            return candidate
    return by_name[0]


def copy_icon(icon_abs: Path, icons_dir: Path) -> str:
    icons_dir.mkdir(parents=True, exist_ok=True)
    dest = icons_dir / icon_abs.name
    if dest.exists():
        if file_hash(dest) == file_hash(icon_abs):
            return dest.name
        suffix = file_hash(icon_abs)[:8]
        dest = icons_dir / f"{icon_abs.stem}_{suffix}{icon_abs.suffix}"
    dest.write_bytes(icon_abs.read_bytes())
    return dest.name


def display_name_for_skill(
    entry: dict[str, Any], props: dict[str, Any], path: Path
) -> str:
    display_name = text_value(props.get("Name"))
    if display_name:
        return display_name
    skill_type = str(props.get("SkillType") or "")
    if "::" in skill_type:
        return skill_type.split("::")[-1]
    internal_name = str(props.get("InternalName") or "")
    if internal_name.startswith("skill_"):
        return internal_name.removeprefix("skill_").replace("_", " ").title()
    entry_name = str(entry.get("Name") or path.stem)
    return entry_name.removeprefix("SKILL_").replace("_", " ").title()


def skill_sort_key(skill: dict[str, Any]) -> tuple[int, int | str]:
    name = str(skill.get("display_name") or "")
    if name in SKILL_DISPLAY_ORDER:
        return (0, SKILL_DISPLAY_ORDER.index(name))
    return (1, name.lower())


def build_skill_catalog(
    skills_dir: Path, icon_root: Path, icons_dir: Path
) -> list[dict[str, Any]]:
    if not skills_dir.exists():
        print(f"[WARN] Skills directory not found: {skills_dir}")
        return []

    png_index = build_png_name_index(icon_root)
    skills_by_id: dict[str, dict[str, Any]] = {}
    skipped = 0
    icon_missing = 0

    for path in sorted(skills_dir.rglob("SKILL_*.json")):
        if any(part.lower() == "deprecatedskills" for part in path.parts):
            skipped += 1
            continue
        data = load_json(path)
        entry = pick_skill_entry(data)
        if not entry:
            print(f"[WARN] Skill data missing: {path}")
            skipped += 1
            continue
        props = entry.get("Properties") or {}
        if not isinstance(props, dict):
            skipped += 1
            continue
        persistence_id = str(props.get("PersistenceID") or "")
        if not persistence_id:
            print(f"[WARN] Skill PersistenceID missing: {path}")
            skipped += 1
            continue

        icon_file = ""
        icon_props = props.get("Icon")
        icon_path = extract_asset_reference(icon_props)
        icon_abs = resolve_icon_abs(icon_path, icon_root, png_index)
        if icon_abs:
            icon_file = copy_icon(icon_abs, icons_dir)
        elif icon_path:
            icon_missing += 1
            print(f"[WARN] Skill icon not found: {path} -> {icon_path}")

        tag_icon_file = ""
        tag_icon_props = props.get("TagIcon")
        tag_icon_path = extract_asset_reference(tag_icon_props)
        tag_icon_abs = resolve_icon_abs(tag_icon_path, icon_root, png_index)
        if tag_icon_abs:
            tag_icon_file = copy_icon(tag_icon_abs, icons_dir)
        elif tag_icon_path:
            icon_missing += 1
            print(f"[WARN] Skill tag icon not found: {path} -> {tag_icon_path}")

        skills_by_id[persistence_id] = {
            "id": persistence_id,
            "display_name": display_name_for_skill(entry, props, path),
            "internal_name": props.get("InternalName") or "",
            "skill_type": str(props.get("SkillType") or ""),
            "max_level": props.get("MaxLevel") or 0,
            "icon": icon_file,
            "tag_icon": tag_icon_file,
        }

    skills = sorted(skills_by_id.values(), key=skill_sort_key)
    print(f"[INFO] Skills indexed: {len(skills)}")
    print(f"[INFO] Skills skipped: {skipped}")
    print(f"[INFO] Missing skill icons: {icon_missing}")
    return skills


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a character customization catalog from data tables."
    )
    parser.add_argument(
        "--source",
        default="website/tools/character-editor/data",
        help="Directory containing customization data tables.",
    )
    parser.add_argument(
        "--output",
        default="website/tools/character-editor/data/character_catalog.json",
        help="Output JSON path for the catalog.",
    )
    parser.add_argument(
        "--skills-source",
        default="data/skills",
        help="Directory containing SKILL_*.json files produced by ingest.",
    )
    parser.add_argument(
        "--content-root",
        default="data/icons",
        help="Icon root used to resolve skill Icon ObjectPath values.",
    )
    parser.add_argument(
        "--icons-dir",
        default="website/shared/icons",
        help="Directory to copy generated character-editor icons into.",
    )
    args = parser.parse_args()

    source_dir = Path(args.source)
    output_path = Path(args.output)
    skills_dir = Path(args.skills_source)
    content_root = Path(args.content_root)
    icons_dir = Path(args.icons_dir)
    if not source_dir.exists():
        print(f"[ERROR] Source directory not found: {source_dir}")
        return 1

    mapping = {
        "BodyType": "DT_Customization_BodyType.json",
        "Head": "DT_Customization_FaceType.json",
        "HairPreset": "DT_Customization_HairPresets.json",
        "FacialHairPreset": "DT_Customization_FacialHairPresets.json",
        "SkinTone": "DT_Customization_SkinTone.json",
        "HairColor": "DT_Customization_HairColor.json",
        "EyeColor": "DT_Customization_EyeColor.json",
        "EyebrowColor": "DT_Customization_EyebrowColor.json",
    }

    catalog: dict[str, Any] = {}
    for key, filename in mapping.items():
        path = source_dir / filename
        if not path.exists():
            print(f"[WARN] Missing table: {path}")
            catalog[key] = []
            continue
        data = load_json(path)
        catalog[key] = extract_rows(data)

    catalog["Skills"] = build_skill_catalog(skills_dir, content_root, icons_dir)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(catalog, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    print(f"[INFO] Wrote catalog: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
