import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_FILE = ROOT / "website" / "tools" / "item-editor" / "data" / "catalog.json"
DOCS_ICONS_DIR = ROOT / "website" / "shared" / "icons"
PLACEHOLDER_SOURCE = ROOT / "website" / "shared" / "game-ui" / "T_Icon_Placeholder.png"

TAB_LABELS = {
    "bag": "Bag Items",
    "rune": "Rune Items",
    "ammo": "Ammo Items",
    "quest": "Quest Items",
}

FILTER_TO_BAG_CATEGORY = {
    "Heavy": "Armour",
    "Medium": "Armour",
    "Light": "Armour",
    "Cape": "Armour",
    "Food": "Consumables",
    "Drink": "Consumables",
    "Tome": "Consumables",
    "Potion": "Consumables",
    "BasicMaterial": "Materials",
    "ProcessedMaterial": "Materials",
    "Resource": "Materials",
    "RawIngredient": "Materials",
    "Component": "Materials",
    "Container": "Tools",
    "Melee": "Weapons",
    "Ranged": "Weapons",
    "Magic": "Weapons",
}

EQUIPMENT_SLOTS = ("Head", "Body", "Legs", "Cape", "Jewellery")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def pick_entry(data: Any) -> dict[str, Any] | None:
    if not isinstance(data, list) or not data:
        return None
    for row in data:
        if not isinstance(row, dict):
            continue
        props = row.get("Properties") or {}
        if isinstance(props, dict) and props.get("PersistenceID"):
            return row
    return data[0] if isinstance(data[0], dict) else None


def filter_tag(props: dict[str, Any]) -> str:
    tags = props.get("ItemFilterTags") or []
    candidates = [tag for tag in tags if isinstance(tag, str) and tag.startswith("ItemFilter.")]
    if candidates:
        return candidates[-1].split(".")[-1]
    category_tag = (props.get("Category") or {}).get("TagName") or ""
    if category_tag:
        return str(category_tag).split(".")[-1]
    return "Misc"


def resolve_icon_abs(props: dict[str, Any], icon_root: Path) -> Path | None:
    obj_path = ((props.get("Icon") or {}).get("ObjectPath") or "").strip()
    if not obj_path:
        return None
    cleaned = obj_path.replace("RSDragonwilds/Content/", "").rstrip(".0")
    stem = Path(cleaned).name
    candidates = list(icon_root.rglob(f"{stem}.png"))
    if not candidates:
        return None
    return candidates[0]


def sha1_file(path: Path) -> str:
    hasher = hashlib.sha1()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def copy_icon(icon_abs: Path, docs_icons_dir: Path) -> str:
    docs_icons_dir.mkdir(parents=True, exist_ok=True)
    dest = docs_icons_dir / icon_abs.name
    if dest.exists():
        if sha1_file(dest) == sha1_file(icon_abs):
            return dest.name
        suffix = sha1_file(icon_abs)[:8]
        dest = docs_icons_dir / f"{icon_abs.stem}_{suffix}{icon_abs.suffix}"
    dest.write_bytes(icon_abs.read_bytes())
    return dest.name


def resolve_placeholder_icon(icon_root: Path, docs_icons_dir: Path) -> str:
    if PLACEHOLDER_SOURCE.exists():
        return copy_icon(PLACEHOLDER_SOURCE, docs_icons_dir)
    fallback = next(icon_root.rglob("T_Icon_Placeholder.png"), None)
    if fallback:
        return copy_icon(fallback, docs_icons_dir)
    print(f"[WARN] Placeholder icon not found: {PLACEHOLDER_SOURCE}")
    return ""


def is_excluded_file(path: Path) -> bool:
    name = path.name.lower()
    if "_meshdata_" in name:
        return True
    return False


def classify_tab_and_category(path: Path, tag: str) -> tuple[str, str]:
    lowered = tag.lower()
    if lowered == "rune":
        return "rune", "Runes"
    if lowered == "arrow":
        return "ammo", "Arrows"
    if lowered == "questitem":
        return "quest", "Quest"

    lower_parts = [part.lower() for part in path.parts]
    if "vestiges" in lower_parts:
        return "bag", "Vestiges"
    if path.name.startswith("DA_Consumable_"):
        return "bag", "Plans"

    root = FILTER_TO_BAG_CATEGORY.get(tag, "Materials")
    sub = path.parent.name.replace("_", " ").strip()
    if not sub or sub.lower() in {"items", "resources", "consumables"}:
        return "bag", root
    return "bag", f"{root}/{sub}"


def equipment_slot_from_path(path: Path) -> str | None:
    lower_parts = [part.lower() for part in path.parts]
    if "equipment" not in lower_parts:
        return None
    for slot in EQUIPMENT_SLOTS:
        if slot.lower() in lower_parts:
            return slot
    return None


def has_equipment_loadout_slot(props: dict[str, Any]) -> bool:
    """True when the item occupies a loadout slot (weapon, armour, cape, ammo, etc.)."""
    slot_val = props.get("Slot")
    return isinstance(slot_val, str) and "ELoadoutSlotStrategy::" in slot_val


def is_equippable_ammo_row_type(item_type: str) -> bool:
    """
    True for ammo definitions that use the ammo slots (runes/arrows/bolts).

    Game exports often omit Properties.Slot for these, but Unreal row Type still
    distinguishes MagicAmmoData / RangedAmmoData from plain ItemData runes.
    """
    return item_type in ("MagicAmmoData", "RangedAmmoData")


def build_catalog(data_root: Path, icon_root: Path, docs_icons_dir: Path) -> dict[str, Any]:
    tabs: dict[str, list[dict[str, Any]]] = {"bag": [], "rune": [], "ammo": [], "quest": []}
    fallback_icon_name = resolve_placeholder_icon(icon_root, docs_icons_dir)

    sources = [
        (data_root / "items", "ITEM_*.json"),
        (data_root / "consumables", "DA_Consumable_*.json"),
    ]

    for source_root, pattern in sources:
        if not source_root.exists():
            print(f"[WARN] Source missing: {source_root}")
            continue
        for json_path in sorted(source_root.rglob(pattern)):
            if is_excluded_file(json_path):
                continue
            try:
                data = load_json(json_path)
            except json.JSONDecodeError as exc:
                print(f"[WARN] JSON parse failed: {json_path} ({exc})")
                continue

            entry = pick_entry(data)
            if not entry:
                continue
            props = entry.get("Properties") or {}
            if not isinstance(props, dict):
                continue
            entry_type = str(entry.get("Type") or "")

            item_data = props.get("PersistenceID") or ""
            if not item_data:
                continue
            name = (
                (props.get("Name") or {}).get("SourceString")
                or (props.get("Name") or {}).get("LocalizedString")
                or props.get("InternalName")
                or entry.get("Name")
                or json_path.stem
            )
            max_stack = props.get("MaxStackSize")
            if max_stack is None:
                max_stack = 1
            description = (
                (props.get("Description") or {}).get("SourceString")
                or (props.get("FlavourText") or {}).get("SourceString")
                or ""
            )

            tag = filter_tag(props)
            tab_key, category = classify_tab_and_category(json_path, tag)

            icon_abs = resolve_icon_abs(props, icon_root)
            icon_name = copy_icon(icon_abs, docs_icons_dir) if icon_abs else fallback_icon_name
            icon_path = f"/shared/icons/{icon_name}" if icon_name else ""
            source_path = json_path.as_posix()

            item = {
                "name": str(name),
                "itemData": str(item_data),
                "maxStack": max_stack,
                "iconPath": icon_path,
                "sourcePath": source_path,
                "category": category,
            }
            if description:
                item["description"] = description
            if props.get("BaseDurability") is not None:
                item["baseDurability"] = props.get("BaseDurability")
            if props.get("PowerLevel") is not None:
                item["powerLevel"] = props.get("PowerLevel")
            if props.get("Weight") is not None:
                item["weight"] = props.get("Weight")

            slot = equipment_slot_from_path(json_path)
            if slot:
                item["equipment"] = slot
            # Save JSON expects VitalShield on equipped gear; use game Slot when present
            # (covers Held weapons, armour, capes, ammo, etc., not only folder-based armour).
            # MagicAmmoData / RangedAmmoData = runes-as-ammo and arrows/bolts (Slot often absent in export).
            if (
                slot
                or has_equipment_loadout_slot(props)
                or is_equippable_ammo_row_type(entry_type)
            ):
                item["vitalShield"] = 0

            tabs[tab_key].append(item)

    return {
        "tabs": {
            key: {
                "label": TAB_LABELS[key],
                "items": sorted(
                    value,
                    key=lambda item: (item.get("category") or "", item.get("name") or ""),
                ),
            }
            for key, value in tabs.items()
        }
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build item editor catalog directly from unified data sources."
    )
    parser.add_argument(
        "--data-root",
        default="data",
        help="Root folder containing items/consumables data.",
    )
    parser.add_argument(
        "--icon-root",
        default="data/icons",
        help="Root folder containing discovered source icons.",
    )
    args = parser.parse_args()

    catalog = build_catalog(Path(args.data_root), Path(args.icon_root), DOCS_ICONS_DIR)
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(
        json.dumps(catalog, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    print(f"[INFO] Wrote catalog: {OUTPUT_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
