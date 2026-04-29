# Character Save Output

This note describes exactly what the editor writes when you click Save.

## What Gets Written
- `Inventory`: rewritten from the current UI state.
- `PersonalInventory`: rewritten from the current UI state.
- `Loadout`: rewritten from the equipment loadout row (Head/Body/Legs/Cape/Jewellery).

Each of the above sections:
- Includes the occupied slot indices as keys.
- Preserves `MaxSlotIndex` if present; otherwise sets it to the known max.

## Item Fields We Write
When an item is created or moved, we write:
- `ItemData`: the item UID (required).
- `GUID`: generated per new item.
- `Count`: only set for stackable items; omitted for single‑stack items.
- `VitalShield`: set to `0` when the item requires it (per catalog metadata).

## What We Do NOT Change
- Any other top‑level fields in the character JSON are preserved as-is.
- Any unknown fields inside items are preserved if they were already present.

## Notes
- Empty slots are omitted from the output (only occupied slots are written).
- Loadout slot indices map to: `0=Head`, `1=Body`, `2=Legs`, `3=Cape`, `4=Jewellery`.
