import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from archive_sources import DEFAULT_ARCHIVE_ROOT, resolve_archive_sources
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

MOUNT_ASSET_DIRS = (
    Path("Content/Gameplay/Mounts/TerrorbirdVariants"),
    Path("Plugins/GameFeatures/UmbralSands/Content/Gameplay/Mounts/FlyingCarpetVariants"),
)
MOUNT_UNLOCK_DIRS = (
    Path("Content/Gameplay/Items/Mounts"),
    Path("Plugins/GameFeatures/UmbralSands/Content/Gameplay/Items/Mounts"),
)
MOUNT_UNLOCK_GLOB = "DA_Consumabe_Mount_*.json"
MOUNT_STRING_TABLE = Path(
    "Plugins/GameFeatures/UmbralSands/Content/Gameplay/Mounts/ST_MountVariants.json"
)
VENDOR_REPUTATION_DIRS = (
    Path("Plugins/GameFeatures/UmbralSands/Content/Gameplay/Items/Recipes/Vendor"),
    Path("Plugins/GameFeatures/UmbralSands/Content/Gameplay/Quests"),
)
CARPET_NAME_KEYS = {
    "01_01": "Carpet.Default.Item",
    "01_02": "Carpet.Default.Teal.Item",
    "01_03": "Carpet.Default.Blue.Item",
    "01_04": "Carpet.Default.Purple.Item",
    "01_05": "Carpet.Default.Orange.Item",
}
TERRORBIRD_NAME_KEYS = {
    "00_00": "Terrorbird.Default",
    "01_01": "Green.5.Item",
    "01_02": "Green.4.Item",
    "01_03": "Green.3.Item",
    "01_04": "Green.2.Item",
    "01_05": "Green.1.Item",
    "02_01": "Yellow.5.Item",
    "02_02": "Yellow.4.Item",
    "03_01": "Red.5.Item",
    "03_02": "Red.4.Item",
    "03_03": "Red.3.Item",
    "03_04": "Red.2.Item",
    "03_05": "Red.1.Item",
}
VENDOR_REPUTATION_RE = re.compile(r"(?<!^)(?=[A-Z])")


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


def tag_name(value: object) -> str:
    if not isinstance(value, dict):
        return ""
    tag = value.get("TagName")
    return tag if isinstance(tag, str) else ""


def object_ref_name(value: object) -> str:
    if not isinstance(value, dict):
        return ""
    object_name = value.get("ObjectName")
    if isinstance(object_name, str) and "'" in object_name:
        parts = object_name.split("'")
        if len(parts) >= 2:
            return parts[1]
    object_path = value.get("ObjectPath")
    if isinstance(object_path, str) and object_path:
        return object_path.rsplit("/", 1)[-1].split(".", 1)[0]
    return ""


def strip_mount_prefix(value: str) -> str:
    value = value.strip()
    if value.upper().startswith("MOUNT:"):
        return value.split(":", 1)[1].strip()
    return value


def load_string_table(path: Path) -> dict[str, str]:
    if not path.exists():
        print(f"[WARN] Mount string table not found: {path}")
        return {}
    data = load_json(path)
    if not isinstance(data, list):
        return {}
    for entry in data:
        if not isinstance(entry, dict):
            continue
        table = entry.get("StringTable") or {}
        if not isinstance(table, dict):
            continue
        rows = table.get("KeysToEntries") or {}
        if isinstance(rows, dict):
            return {
                str(key): str(value)
                for key, value in rows.items()
                if isinstance(value, str)
            }
    return {}


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


def game_json_root(game_root: Path) -> Path:
    root = game_root / "json" / "RSDragonwilds"
    if not root.exists():
        raise ValueError(f"Game JSON root not found: {root}")
    return root


def mount_type_for_entry(entry: dict[str, Any], asset_name: str) -> str:
    entry_type = str(entry.get("Type") or "")
    if "FlyingCarpet" in entry_type or "FlyingCarpet" in asset_name:
        return "Magic Carpet"
    if "Terrorbird" in entry_type or "Terrorbird" in asset_name:
        return "Terrorbird"
    return entry_type or "Mount"


def infer_mount_id_from_unlock_internal(internal_name: str) -> str:
    internal = internal_name.lower()
    if internal.startswith("mountunlock_terrorbird_"):
        suffix = internal.removeprefix("mountunlock_terrorbird_")
        return f"DA_Mount_Terrorbird_{suffix}"
    if internal.startswith("mountunlock_flyingcarpet_"):
        suffix = internal.removeprefix("mountunlock_flyingcarpet_")
        return f"DA_Mount_FlyingCarpet_{suffix}"
    return ""


def build_mount_asset_index(root: Path) -> dict[str, dict[str, Any]]:
    assets: dict[str, dict[str, Any]] = {}
    for relative_dir in MOUNT_ASSET_DIRS:
        directory = root / relative_dir
        if not directory.exists():
            print(f"[WARN] Mount asset directory not found: {directory}")
            continue
        for path in sorted(directory.glob("DA_Mount_*.json")):
            data = load_json(path)
            if not isinstance(data, list) or not data:
                continue
            entry = data[0]
            if not isinstance(entry, dict):
                continue
            asset_name = str(entry.get("Name") or path.stem)
            assets[asset_name] = {
                "asset_name": asset_name,
                "mount_type": mount_type_for_entry(entry, asset_name),
                "source": str(path.relative_to(root)),
            }
    return assets


def build_mount_unlock_index(
    root: Path,
    asset_names: set[str],
) -> dict[str, dict[str, str]]:
    unlocks: dict[str, dict[str, str]] = {}
    paths: list[Path] = []
    for relative_dir in MOUNT_UNLOCK_DIRS:
        directory = root / relative_dir
        if directory.exists():
            paths.extend(directory.glob(MOUNT_UNLOCK_GLOB))
    for path in sorted(paths):
        data = load_json(path)
        if not isinstance(data, list):
            continue
        for entry in data:
            if not isinstance(entry, dict):
                continue
            props = entry.get("Properties") or {}
            if not isinstance(props, dict) or "MountToUnlock" not in props:
                continue
            internal_name = str(props.get("InternalName") or "")
            inferred_id = infer_mount_id_from_unlock_internal(internal_name)
            referenced_id = object_ref_name(props.get("MountToUnlock"))
            mount_id = inferred_id if inferred_id in asset_names else referenced_id
            if not mount_id:
                continue
            unlocks[mount_id] = {
                "unlock_item_persistence_id": str(props.get("PersistenceID") or ""),
                "unlock_item_internal_name": internal_name,
                "name_key": str((props.get("Name") or {}).get("Key") or ""),
                "icon_path": extract_asset_reference(props.get("Icon")),
            }
    return unlocks


def inferred_mount_icon_path(asset_name: str) -> str:
    if asset_name.startswith("DA_Mount_Terrorbird_"):
        suffix = asset_name.removeprefix("DA_Mount_Terrorbird_")
        if suffix == "00_00":
            return ""
        return (
            "/Game/Art/UI/Icons/Icons_0_12_UmS/Icons/"
            f"T_Icon_SM_Terro_bird_{suffix}.T_Icon_SM_Terro_bird_{suffix}"
        )
    if asset_name.startswith("DA_Mount_FlyingCarpet_"):
        suffix = asset_name.removeprefix("DA_Mount_FlyingCarpet_")
        return (
            "/Game/Art/UI/Icons/Icons_0_12_UmS/Icons/"
            f"T_Icon_SM_Carpet_{suffix}.T_Icon_SM_Carpet_{suffix}"
        )
    return ""


def mount_name_key(asset_name: str, unlock: dict[str, str]) -> str:
    if asset_name.startswith("DA_Mount_Terrorbird_"):
        suffix = asset_name.removeprefix("DA_Mount_Terrorbird_")
        known_key = TERRORBIRD_NAME_KEYS.get(suffix, "")
        if known_key:
            return known_key
    if asset_name.startswith("DA_Mount_FlyingCarpet_"):
        suffix = asset_name.removeprefix("DA_Mount_FlyingCarpet_")
        known_key = CARPET_NAME_KEYS.get(suffix, "")
        if known_key:
            return known_key
    name_key = unlock.get("name_key", "")
    if name_key:
        return name_key
    return ""


def display_name_for_mount(
    asset_name: str,
    unlock: dict[str, str],
    string_table: dict[str, str],
) -> str:
    name_key = mount_name_key(asset_name, unlock)
    if name_key:
        display_name = strip_mount_prefix(string_table.get(name_key, ""))
        if display_name:
            return display_name
    return asset_name.removeprefix("DA_Mount_").replace("_", " ")


def mount_sort_key(mount: dict[str, Any]) -> tuple[int, str]:
    mount_type = str(mount.get("mount_type") or "")
    type_order = 0 if mount_type == "Terrorbird" else 1
    return (type_order, str(mount.get("display_name") or "").lower())


def build_mount_catalog(
    root: Path,
    icon_root: Path,
    icons_dir: Path,
) -> list[dict[str, Any]]:
    assets = build_mount_asset_index(root)
    unlocks = build_mount_unlock_index(root, set(assets))
    string_table = load_string_table(root / MOUNT_STRING_TABLE)
    png_index = build_png_name_index(icon_root)
    icon_missing = 0
    mounts: list[dict[str, Any]] = []

    for asset_name, asset in sorted(assets.items()):
        unlock = unlocks.get(asset_name, {})
        icon_file = ""
        icon_path = inferred_mount_icon_path(asset_name) or unlock.get("icon_path")
        icon_abs = resolve_icon_abs(icon_path, icon_root, png_index)
        if icon_abs:
            icon_file = copy_icon(icon_abs, icons_dir)
        elif icon_path:
            icon_missing += 1
            print(f"[WARN] Mount icon not found: {asset_name} -> {icon_path}")

        mounts.append(
            {
                "save_value": f"MountDataAsset:{asset_name}",
                "display_name": display_name_for_mount(asset_name, unlock, string_table),
                "internal_name": asset_name,
                "mount_type": asset["mount_type"],
                "icon": icon_file,
                "unlock_item_persistence_id": unlock.get(
                    "unlock_item_persistence_id", ""
                ),
                "unlock_item_internal_name": unlock.get(
                    "unlock_item_internal_name", ""
                ),
            }
        )

    mounts.sort(key=mount_sort_key)
    print(f"[INFO] Mounts indexed: {len(mounts)}")
    print(f"[INFO] Missing mount icons: {icon_missing}")
    return mounts


def split_gameplay_tag_label(value: str) -> str:
    parts = [part for part in value.split(".") if part]
    if parts and parts[0] == "Vendor":
        parts = parts[1:]
    label = " ".join(VENDOR_REPUTATION_RE.sub(" ", part) for part in parts)
    return " ".join(label.split())


def walk_reputation_entries(value: object) -> list[tuple[str, int]]:
    found: list[tuple[str, int]] = []
    if isinstance(value, dict):
        reputation_tag = value.get("ReputationTag")
        reputation_amount = value.get("ReputationAmount")
        tag = tag_name(reputation_tag)
        if tag.startswith("Vendor.") and reputation_amount is not None:
            try:
                found.append((tag, int(reputation_amount)))
            except (TypeError, ValueError):
                pass
        for child in value.values():
            found.extend(walk_reputation_entries(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(walk_reputation_entries(child))
    return found


def build_vendor_reputation_catalog(root: Path) -> list[dict[str, Any]]:
    tiers_by_tag: dict[str, set[int]] = {}
    paths: list[Path] = []
    for relative_dir in VENDOR_REPUTATION_DIRS:
        directory = root / relative_dir
        if not directory.exists():
            print(f"[WARN] Vendor reputation source directory not found: {directory}")
            continue
        paths.extend(directory.rglob("*.json"))
    for path in sorted(paths):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        if "ReputationTag" not in text or "ReputationAmount" not in text:
            continue
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            continue
        for tag, amount in walk_reputation_entries(data):
            tiers_by_tag.setdefault(tag, set()).add(amount)

    reputations = [
        {
            "tag": tag,
            "display_name": split_gameplay_tag_label(tag),
            "tiers": [0] + sorted(amount for amount in amounts if amount > 0),
        }
        for tag, amounts in sorted(tiers_by_tag.items())
    ]
    print(f"[INFO] Vendor reputations indexed: {len(reputations)}")
    return reputations


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
    parser.add_argument(
        "--archive-root",
        default=str(DEFAULT_ARCHIVE_ROOT),
        help="RSDWArchive checkout root used to resolve the latest game dataset.",
    )
    parser.add_argument(
        "--game-root",
        default="",
        help=(
            "Explicit top-level game archive root. Defaults to "
            "<archive-root>/<datasetVersion> from RSDWArchive."
        ),
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
    try:
        archive_sources = resolve_archive_sources(
            archive_root=args.archive_root,
            game_root=args.game_root or None,
        )
        archive_json_root = game_json_root(archive_sources.game_root)
    except ValueError as exc:
        print(f"[ERROR] {exc}")
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
    catalog["Mounts"] = build_mount_catalog(archive_json_root, content_root, icons_dir)
    catalog["VendorReputations"] = build_vendor_reputation_catalog(archive_json_root)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(catalog, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    print(f"[INFO] Wrote catalog: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
