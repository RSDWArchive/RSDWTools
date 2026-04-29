import argparse
import json
import shutil
from pathlib import Path
from typing import Any


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def to_resource(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "SpawnedItemData": {"ObjectName": item.get("itemObjectName", "")},
        "MinimumDropAmount": item.get("minimumDropAmount", 0),
        "MaximumDropAmount": item.get("maximumDropAmount", 0),
        "DropChance": item.get("dropChance", 0),
    }


def prettify_enemy_name(value: str) -> str:
    if not value:
        return value
    out = []
    prev = ""
    for ch in value:
        if prev and prev.islower() and ch.isupper():
            out.append(" ")
        out.append(ch)
        prev = ch
    return "".join(out).replace("_", " ").strip()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export website/data files from unified data outputs."
    )
    parser.add_argument(
        "--raw-core",
        default="data",
        help="Data directory produced by ingest_game_data.py.",
    )
    parser.add_argument(
        "--docs-data",
        default="website/data",
        help="website data output directory.",
    )
    parser.add_argument(
        "--chest-catalog",
        default="website/data/chest_item_catalog.json",
        help="Chest item catalog path for item display names.",
    )
    parser.add_argument(
        "--write-legacy",
        action="store_true",
        help="Also write legacy split loot/chest files for compatibility.",
    )
    args = parser.parse_args()

    raw_core = Path(args.raw_core)
    docs_data = Path(args.docs_data)
    loot_path = raw_core / "loot_data" / "LootData.json"
    location_path = raw_core / "location_data" / "LocationData.json"
    chest_catalog_path = Path(args.chest_catalog)

    if not loot_path.exists():
        print(f"[ERROR] Missing loot data source: {loot_path}")
        return 1

    loot_data = load_json(loot_path)
    enemies = loot_data.get("enemies", {}) if isinstance(loot_data, dict) else {}
    chests = loot_data.get("chests", {}) if isinstance(loot_data, dict) else {}
    item_sets = loot_data.get("itemSets", {}) if isinstance(loot_data, dict) else {}

    chest_catalog: list[dict[str, Any]] = []
    if chest_catalog_path.exists():
        loaded_catalog = load_json(chest_catalog_path)
        if isinstance(loaded_catalog, list):
            chest_catalog = loaded_catalog
    name_by_item_id = {
        str(entry.get("item_id", "")): str(entry.get("display_name", "")).strip()
        for entry in chest_catalog
        if entry.get("item_id")
    }

    # Unified copies for newer docs consumers.
    shutil.copyfile(loot_path, docs_data / "loot_data.json")
    print(f"[INFO] Copied unified loot data -> {docs_data / 'loot_data.json'}")
    if location_path.exists():
        shutil.copyfile(location_path, docs_data / "location_data.json")
        print(f"[INFO] Copied unified location data -> {docs_data / 'location_data.json'}")

    if args.write_legacy:
        # Legacy enemy loot files for older frontend contracts.
        loot_rows: dict[str, Any] = {}
        enemy_names: dict[str, str] = {}
        loot_item_names: dict[str, str] = {}
        for enemy_key, enemy in sorted(enemies.items()):
            drops = enemy.get("drops", []) if isinstance(enemy, dict) else []
            loot_rows[enemy_key] = {"Resources": [to_resource(drop) for drop in drops]}
            enemy_names[enemy_key] = prettify_enemy_name(enemy_key)
            for drop in drops:
                item_id = str(drop.get("itemId", "")).strip()
                if not item_id:
                    continue
                loot_item_names[item_id] = name_by_item_id.get(item_id, item_id)

        write_json(docs_data / "loot_drop_table.json", [{"Rows": loot_rows}])
        write_json(docs_data / "loot_drop_table_enemy_names.json", enemy_names)
        write_json(docs_data / "loot_drop_table_item_names.json", loot_item_names)
        print("[INFO] Wrote legacy enemy loot files")

        # Legacy chest files for older frontend contracts.
        respawn_rows: dict[str, Any] = {}
        prefab_rows: dict[str, Any] = {}
        set_rows: dict[str, Any] = {}
        chest_item_names: dict[str, str] = {}

        for set_name, items in sorted(item_sets.items()):
            if not isinstance(items, list):
                continue
            set_rows[set_name] = {"SpawnableItems": [to_resource(item) for item in items]}
            for item in items:
                item_id = str(item.get("itemId", "")).strip()
                if item_id:
                    chest_item_names[item_id] = name_by_item_id.get(item_id, item_id)

        for chest_key, chest in sorted(chests.items()):
            if not isinstance(chest, dict):
                continue
            prefab_ref = chest.get("prefabRef", {}) or {}
            prefab_name = str(prefab_ref.get("row", "")).strip() or chest_key
            respawn_rows[chest_key] = {
                "InGameRespawnTime": (chest.get("respawn", {}) or {}).get("inGameRespawnTime", {}),
                "LootRollHandle": {"RowName": prefab_name},
            }
            guaranteed_sets = [
                {"RowName": set_name}
                for set_name in chest.get("guaranteedSetRows", []) or []
                if set_name
            ]
            additional_sets = [
                {
                    "LootItemSetHandle": {"RowName": entry.get("setRow", "")},
                    "DropChance": entry.get("setRollChance", 0),
                }
                for entry in chest.get("additionalSetRows", []) or []
                if entry.get("setRow")
            ]
            prefab_rows[prefab_name] = {
                "GuaranteedStandaloneItems": [],
                "GuaranteedItemSets": guaranteed_sets,
                "AdditionalItemSets": additional_sets,
                "MinAdditionalSetRolls": 0,
                "MaxAdditionalSetRolls": len(additional_sets),
            }
            for resolved in chest.get("resolvedItems", []) or []:
                item = resolved.get("item", {}) or {}
                item_id = str(item.get("itemId", "")).strip()
                if item_id:
                    chest_item_names[item_id] = name_by_item_id.get(item_id, item_id)

        write_json(docs_data / "chest_respawn_profiles.json", [{"Rows": respawn_rows}])
        write_json(docs_data / "chest_prefabs.json", [{"Rows": prefab_rows}])
        write_json(docs_data / "chest_sets.json", [{"Rows": set_rows}])
        write_json(docs_data / "chest_drop_table_item_names.json", chest_item_names)
        print("[INFO] Wrote legacy chest files")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
