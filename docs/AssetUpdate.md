# Asset Update Pipeline

Streamlined data pipeline that takes raw game files and produces every JSON
catalog and icon the website serves.

## Source of Truth
- Game archive root: `E:\Github\RSDWArchive\<version>`
- In this repo, all extracted/canonical raw inputs live under `data/`.
- Website runtime data is written **directly into `website/`** by the
  builders (no `/docs` mirror step).

## Core Discovery Rules
The ingest step discovers files from the archive root by pattern:
- Items: `ITEM_*.json`
- Recipes: `RECIPE_*.json`
- Consumables (plans/vestiges): `DA_Consumable_*.json`
- Spells: `USD_*.json`
- Icons: PNGs referenced by `ObjectPath` in discovered data, plus
  `t_icon_*` and `t_skill_*` fallback prefixes.

Location and loot are imported from external generated outputs:
- `E:\Github\RSDWArchive\website\tools\LocationData`
- `E:\Github\RSDWArchive\website\tools\LootData`

## One-Command Rebuild
```
python update.py
```

Runs ingest, all builders, and the character catalog step. Useful flags:
- `--no-fresh` — disable default clean rebuild behavior
- `--skip-ingest` — reuse existing `data/`
- `--clean-ingest` — remove stale files before ingest
- `--skip-catalog` — skip `build_dwe_catalog.py`
- `--game-root <path>`
- `--location-data-root <path>`
- `--loot-data-root <path>`

## Manual Step Order (if running individually)
1. `python tools/ingest_game_data.py --game-root E:\Github\RSDWArchive\<ver> --output-root data --location-data-root ... --loot-data-root ... --clean`
2. `python tools/build_dwe_catalog.py` → `website/tools/item-editor/data/catalog.json`
3. `python tools/build_chest_item_catalog.py` → `website/data/chest_item_catalog.json`
4. `python tools/build_recipe_index.py` → `website/tools/recipe-unlocker/data/recipes.json`
5. `python tools/build_spell_catalog.py` → `website/tools/spell-editor/data/spells.json`
6. `python tools/build_mapdata_index.py` → `website/data/mapdata_index.json`
7. `python tools/export_docs_data_from_raw_core.py` → `website/data/{loot_data,location_data}.json`
8. `python tools/build_character_catalog.py` → `website/tools/character-editor/data/`

All icons land under `website/shared/icons/` and are referenced by catalogs
as `/shared/icons/<name>.png`.

## Notes
- `tools/ingest_game_data.py` writes a manifest at `data/_ingest_manifest.json`.
- Missing-icon warnings are expected for some test/deprecated assets and
  mesh-data-only definitions.
- Legacy helpers live in `tools/legacy/` and are not part of the current
  pipeline.
