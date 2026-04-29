# Spell Editor

Tool page at `/tools/spell-editor/` that displays and edits the player's
spellbooks. The UI mirrors the in-game radial wheel and lets users assign
spells, remove spells, and save updates to `Spellcasting.SelectedSpells`.

## Data Source
- Spell definitions live in the game archive under
  `Content/Gameplay/**/USD_*.json`.
- Each spell provides `PersistenceID`, display name, requirements, icons,
  and optional cost items (runes/items).

## Catalog Build Step
Generate a UI-friendly catalog from `USD_*.json` and copy icons into
`website/shared/icons/`:

```
python tools/build_spell_catalog.py
```

Output: `website/tools/spell-editor/data/spells.json`

### Icon Fallback
If `SpellIcon` is missing, the script falls back to
`T_Skill_Placeholder_Active_Spells.png` (copied into
`website/shared/icons/`).

## Player Save Mapping
- Player JSON stores spell data under `Spellcasting.SelectedSpells`.
- There are **48 slots** total (4 spellbooks × 12 slots).
- Slot order is **clockwise**, starting at the top (slot 0 = top).
- Empty slots are stored as empty strings (`""`).
- On save, any spell present in `SelectedSpells` is also added to
  `Progress.SpellsUnlocked` to keep them usable.

## UI Notes
- Spell browser (left) shows all spells from `spells.json`.
- Radial wheel (right) shows the active spellbook (12 slots).
- Drag/drop from browser to wheel assigns a spell.
- Dragging a spell off the wheel clears the slot.
- Right-click a slot for **Remove**.
- Save button overwrites `Spellcasting.SelectedSpells` and writes the file.

## When the Game Updates
1. Run `python tools/build_spell_catalog.py` (or `python update.py`).
2. Verify new spells appear in the browser grid.
3. Validate a few spell tooltips (name, requirements, cooldown, costs).
4. Load/save a player file to confirm the `SelectedSpells` array updates.
