# RSDWTools

Browser-based editors for **RuneScape: Dragonwilds** save files, plus
read-only browsers for recipes, spells, and drop tables.

## Layout
- `website/` — published site (GitHub Pages publish source). Custom domain
  `rsd.tools` via `website/CNAME`.
- `data/` — raw ingest output (canonical inputs for the builders). Produced
  by `tools/ingest_game_data.py` from the `RSDWArchive` game files.
- `tools/` — Python builders that read `data/` and write straight into
  `website/` (catalogs, icons, map index, etc.).
- `update.py` — top-level orchestrator: ingest → builders → optional cleanup.
- `docs/` — these developer notes (this folder).

## Tools (live pages)
- `/tools/character-editor/` — edit player name, type, GUID, customization,
  skills, and unlocks.
- `/tools/item-editor/` — add, remove, modify items in a character save.
- `/tools/spell-editor/` — configure spellbooks and unlocked spells.
- `/tools/recipe-unlocker/` — browse all recipes and toggle unlocks.
- `/tools/enemy-drop-tables/` — look up loot tables by NPC.
- `/tools/chest-drop-tables/` — browse chest loot rolls.

## Save File Location (Windows)
`%localappdata%\RSDragonwilds\Saved\SaveCharacters\`

## Character File Notes
- Empty inventory slots are omitted from JSON; only occupied slots are stored.
- `ItemData` is the UID used to identify the item.
- `GUID` is a per-instance identifier that must be generated for injected items.
- `Count` appears on stackable items.
- `VitalShield` appears on equippable items (currently observed as 0).

## Inventory Slot Ranges
- `Inventory[0-7]` — action bar
- `Inventory[8-31]` — main bag
- `Inventory[32-55]` — runes
- `Inventory[56-79]` — arrows
- `Inventory[80-103]` — quest items
- `PersonalInventory[0-19]` — personal items
- `Loadout[0..4]` — Head, Body, Legs, Cape, Jewellery
