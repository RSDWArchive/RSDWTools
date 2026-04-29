# Drop Table Update Guide

How to refresh the drop-table data used by the website's enemy and chest
drop pages.

## Source Files
- Primary source: `data/loot_data/LootData.json`
- Produced by ingest:
  ```
  python tools/ingest_game_data.py --game-root E:\Github\RSDWArchive\<ver> \
    --output-root data \
    --loot-data-root E:\Github\RSDWArchive\website\tools\LootData \
    --clean
  ```

## Web Data Files
Files consumed by the live pages:
- `website/data/loot_data.json`
- `website/data/chest_item_catalog.json`

## Update Steps
1. Refresh ingest output (command above).
2. Refresh chest item display catalog:
   ```
   python tools/build_chest_item_catalog.py
   ```
3. Export drop data from raw core:
   ```
   python tools/export_docs_data_from_raw_core.py
   ```
   Optional legacy output: `--write-legacy`

## Notes
- Enemy display names are auto-derived from enemy keys during export.
- Item display names are resolved from `chest_item_catalog.json` when
  available.
