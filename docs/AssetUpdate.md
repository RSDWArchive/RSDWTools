# Asset Update Pipeline

Streamlined data pipeline that takes raw game files and produces every JSON
catalog and icon the website serves.

## Source of Truth
- Archive root: `E:\Github\RSDWArchive`
- Latest dataset pointer: `E:\Github\RSDWArchive\website\data.config.json`
- Game archive root: `E:\Github\RSDWArchive\<datasetVersion>`
- In this repo, all extracted/canonical raw inputs live under `data/`.
- Website runtime data is written **directly into `website/`** by the
  builders (no `/docs` mirror step).

## Core Discovery Rules
The ingest step discovers files from the archive root by pattern:
- Items: `ITEM_*.json`
- Recipes: `RECIPE_*.json`
- Consumables (plans/vestiges): `DA_Consumable_*.json`
- Spells: `USD_*.json`
- Skills: active `SKILL_*.json` files, excluding `DeprecatedSkills`
- Icons: PNGs referenced by `ObjectPath` in discovered data, plus
  `t_icon_*` and `t_skill_*` fallback prefixes.
- Character Editor extras: mount assets, mount unlock consumables, vendor
  recipes, and Umbral Sands quest reputation modifiers from the resolved
  archive dataset.

Location and loot are imported from external generated outputs:
- `E:\Github\RSDWArchive\website\tools\LocationData`
- `E:\Github\RSDWArchive\website\tools\LootData`

Quest metadata is imported from the generated archive output:
- `E:\Github\RSDWArchive\website\tools\QuestData\QuestData.json`

## One-Command Rebuild
```
python update.py
```

Runs ingest, all builders, and the character catalog step. By default it reads
RSDWArchive's `website/data.config.json`, resolves `datasetVersion`, and uses
that version folder for ingest. Useful flags:
- `--mode build-local` - fresh rebuild without Git planning
- `--mode validate-local` - read-only validation of generated outputs
- `--mode publish --git-mode plan-only` - validate existing outputs, then write a Git plan
- `--mode publish --git-mode commit-only` - validate existing outputs, then commit batches
- `--mode publish --git-mode push-each` - validate existing outputs, then commit and push each batch
- `--no-fresh` — disable default clean rebuild behavior
- `--skip-ingest` — reuse existing `data/`
- `--clean-ingest` — remove stale files before ingest
- `--skip-catalog` — skip `build_dwe_catalog.py`
- `--archive-root <path>` - override the RSDWArchive checkout root
- `--game-root <path>` - override auto-detected `<archive-root>/<datasetVersion>`
- `--location-data-root <path>` - override generated LocationData
- `--loot-data-root <path>` - override generated LootData
- `--skip-git-plan` - skip the final Git commit batch plan
- `--git-commit-batches` - stage and commit planned batches
- `--git-push-each` - push each committed batch immediately

## Manual Step Order (if running individually)
1. `python tools/rebuild_docs_data.py`
2. `python tools/build_character_catalog.py`
3. `python tools/PlanGitCommits.py`
4. `python tools/validate_pipeline_outputs.py --summary PipelineRun.json`

`rebuild_docs_data.py` auto-detects RSDWArchive latest by default and runs
ingest, item catalog, chest item catalog, recipe index, spell catalog, map
index, quest catalog, and shared loot/location exports.

`build_character_catalog.py` auto-detects the same archive latest by default
and writes customization rows, skills, mounts, and vendor reputation tiers to
`website/tools/character-editor/data/character_catalog.json`.

`PlanGitCommits.py commit-batches` is a dry run unless `--execute` is passed.

All icons land under `website/shared/icons/` and are referenced by catalogs
as `/shared/icons/<name>.png`.

## Pipeline Artifacts

`update.py` writes structured run artifacts for RSDWMasterPipeline and human
release review:

- `PipelineLogs/<timestamp>/PipelineRun.json` - canonical run summary
- `PipelineRun.json` - latest-run compatibility copy
- `PipelineLogs/<timestamp>/warnings.json` - warning category summary
- `PipelineLogs/<timestamp>/GitCommitPlan.json` - canonical Git plan
- `GitCommitPlan.json` - ignored compatibility copy
- `pipeline.contract.json` - machine-readable command and artifact contract

Known nonfatal warning categories, such as missing placeholder icons for
deprecated or mesh-only assets, are summarized instead of hidden. Fatal and
unknown warning categories fail validation unless the run explicitly uses
`--allow-unknown-warnings`.

## Notes
- `tools/ingest_game_data.py` writes a manifest at `data/_ingest_manifest.json`.
- Missing-icon warnings are expected for some test/deprecated assets and
  mesh-data-only definitions.
- Legacy helpers live in `tools/legacy/` and are not part of the current
  pipeline.
