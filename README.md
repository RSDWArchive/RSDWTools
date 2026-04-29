# RSDWTools.com

Source for **RSDWTools.com** — a small set of save-file editors and
reference tables for *RuneScape: Dragonwilds*. Sister site to
[RSDWArchive.com](https://rsdwarchive.com).

## Tools

- **Character Editor** — edit player name, type, GUID, customization, skills, unlocks
- **Item Editor** — add, remove, modify items in your character save
- **Spell Editor** — configure spellbooks and unlocked spells
- **Recipe Unlocker** — browse all recipes and unlock them
- **Enemy Drop Tables** — look up loot tables for any NPC
- **Chest Drop Tables** — browse chest loot rolls by chest type

## Layout

```
website/                       # GitHub Pages source (publish folder)
├── CNAME                      # Custom domain (rsd.tools)
├── index.html                 # Landing page
├── shared/                    # Everything shared by all tools / the site shell
│   ├── site-shell.css         # RSDWTools header / footer / dropdown / landing
│   ├── styles.css             # Tool-specific styles (inventory, spell wheel, etc.)
│   ├── shared-header.css
│   ├── shared-header.js       # Header injector + tools dropdown
│   ├── assets/                # Site chrome (logo, bg.jpg, github.svg, tool-icons/, ...)
│   ├── game-ui/               # Game UI atlases (Inventory, ItemBrowser, ToolTip, ...)
│   └── icons/                 # Game item icons (pipeline-generated)
├── data/                      # JSON shared by multiple tools (loot_data, chest_item_catalog, ...)
└── tools/
    ├── character-editor/      # index.html + character-editor.js + data/ + assets/
    ├── item-editor/           # index.html + item-editor.js + data/
    ├── spell-editor/          # index.html + spell-editor.js + data/ + assets/
    ├── recipe-unlocker/       # index.html + recipe-unlocker.js + data/
    ├── enemy-drop-tables/     # index.html + drop-tables.js
    └── chest-drop-tables/     # index.html + chest-drop-tables.js

data/                          # Pipeline ingest output (raw, not served)
tools/                         # Python build pipeline
docs/                          # Developer notes (this folder is not served)
```

> GitHub Pages publish source must be set to **`/website`** on the deploy
> branch (Settings → Pages → Build and deployment → Branch: `<branch>` /
> `/website`). The repo no longer ships a `/docs` site.

Each tool's `index.html` declares `<base href="/">` so internal `./...`
refs resolve from the publish root. Path conventions:

- `/shared/...` — shell CSS/JS + chrome (`assets/`) + game UI (`game-ui/`, `icons/`)
- `/data/...` — JSON shared by multiple tools
- `/tools/<name>/data/...` — JSON owned by a single tool
- `/tools/<name>/assets/...` — images owned by a single tool

## Running locally

```powershell
cd website
python -m http.server 8000
# open http://localhost:8000/
```

## Update pipeline

Before a full refresh, confirm:

1. `--game-root` points at the newest game archive (default in `update.py`)
2. External generated inputs are current:
   - `LocationData` (`--location-data-root`)
   - `LootData` (`--loot-data-root`)

Then:

```powershell
python update.py
```

By default this runs in `--fresh` mode (cleans and regenerates everything).
All builders write directly into `website/` under the per-tool layout above.
Pass alternate paths as CLI args instead of editing defaults.
