# Recipe Unlocker

Tool page at `/tools/recipe-unlocker/` that lists every recipe in the game
and highlights which are unlocked for a loaded character via the
`RecipesUnlocked` array in the player JSON.

## Data Source
- Recipe files use the `RECIPE_*.json` naming convention and are discovered
  from the game archive during ingest.
- Canonical recipe source for tooling is `data/recipes` (produced by
  `tools/ingest_game_data.py`).

## Catalog Index Step
Build the UI-friendly recipe index and copy required icons:

```
python tools/build_recipe_index.py
```

Outputs:
- `website/tools/recipe-unlocker/data/recipes.json`
- Icons copied into `website/shared/icons/`

Useful options:
- `--recipes data/recipes`
- `--items data/items`
- `--consumables data/consumables`
- `--content-root data/icons`

### Filtering and Placeholders
- Recipes with no valid output item (`ItemsCreated` empty/null/Count 0) are
  skipped from the catalog.
- The script indexes both `ITEM_*.json` and `DA_*.json` items.
- Missing icons fall back to `T_Icon_Placeholder.png` (copied into
  `website/shared/icons/`).

## Verified Mappings
- `RecipesUnlocked` in the player JSON stores **recipe `PersistenceID` values**.
- The recipe catalog uses `persistence_id` for unlock matching and keeps
  `name` / `display_name` for UI labels.
