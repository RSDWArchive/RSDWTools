# RSDWTools Pipeline Handoff

This is the automation handoff contract for RSDWTools.

Use this document when an external orchestrator needs to run RSDWTools as one
stage in a larger multi-project pipeline.

## Pipeline Position

RSDWTools depends on RSDWArchive and must run after the RSDWArchive pipeline has
produced current archive data.

Required upstream inputs:

- `E:\Github\RSDWArchive\website\data.config.json`
- `E:\Github\RSDWArchive\<datasetVersion>`
- `E:\Github\RSDWArchive\website\tools\LocationData`
- `E:\Github\RSDWArchive\website\tools\LootData`
- `E:\Github\RSDWArchive\website\tools\QuestData\QuestData.json`
- Mount assets, mount unlock items, vendor recipes, and Umbral Sands quest
  files under `E:\Github\RSDWArchive\<datasetVersion>\json\RSDragonwilds`

`datasetVersion` is read from `RSDWArchive\website\data.config.json`. By
default, RSDWTools ingests from `E:\Github\RSDWArchive\<datasetVersion>`.

## Execution Contract

Default orchestration command:

```powershell
cd E:\Github\RSDWTools
python update.py --git-commit-batches --git-push-each
```

The orchestrator should treat a nonzero exit code as fatal and stop the larger
pipeline before downstream projects run.

The default command lets RSDWTools create its own git commit batches and push
each batch. If the larger orchestrator needs centralized push control, use
`python update.py --git-commit-batches` instead.

## Internal Stage Order

`update.py` runs these stages in order:

1. Resolve archive sources from `RSDWArchive`.
2. Clean generated RSDWTools data because `--fresh` is enabled by default.
3. Run `tools/rebuild_docs_data.py`.
4. Run `tools/build_character_catalog.py`.
5. Run `tools/PlanGitCommits.py commit-batches --execute`.
6. Push each created git batch when `--git-push-each` is present.

`tools/rebuild_docs_data.py` runs ingest and the website data builders. It
refreshes item catalogs, chest item catalogs, recipe data, quest data, spell
data, map data, loot/location exports, and shared icons.

## Produced Outputs

Primary generated outputs:

- Website JSON under `website\data\`
- Per-tool catalogs under `website\tools\*\data\`
- Character catalog under
  `website\tools\character-editor\data\character_catalog.json`, including
  customization rows, skills, mounts, and vendor reputation tiers
- Quest catalog under `website\tools\quest-editor\data\quests.json`
- Generated item and skill icons under `website\shared\icons\`
- Raw ingest manifest at `data\_ingest_manifest.json`
- Git commit batches created by the pipeline command
- Pushed commits when `--git-push-each` is used

The git planner writes `GitCommitPlan.json` in the repo root. This file is an
ignored local artifact and should not be committed.

## Success Criteria

The RSDWTools stage is successful when all of these are true:

- The process exits with code `0`.
- Output includes `[INFO] Update pipeline complete.`
- Generated website data has been refreshed under `website\`.
- If files changed, git commit batches were created.
- With `--git-push-each`, created commits were pushed to the configured remote.

No changed files is a valid successful outcome if the upstream data did not
produce any RSDWTools changes.

## Failure Modes

Treat these as fatal for the larger orchestrator:

- `RSDWArchive` checkout is missing.
- `RSDWArchive\website\data.config.json` is missing or invalid.
- The resolved `E:\Github\RSDWArchive\<datasetVersion>` folder is missing.
- The resolved archive dataset has no `json` directory.
- `LocationData` or `LootData` is missing.
- `QuestData\QuestData.json` is missing or invalid.
- Git has staged changes before commit batching starts.
- A changed file exceeds the git planner file limit.
- Commit creation fails.
- Push fails because of authentication, permissions, network, or remote changes.

Missing-icon warnings for deprecated, test, or mesh-only assets can be
non-fatal when the pipeline still exits with code `0`.

## Useful Overrides

Use these only when the orchestrator intentionally needs non-default sources or
behavior:

- `--archive-root <path>`: use another RSDWArchive checkout.
- `--game-root <path>`: use an explicit archive dataset folder.
- `--location-data-root <path>`: use explicit LocationData.
- `--loot-data-root <path>`: use explicit LootData.
- `--no-fresh`: skip the default clean rebuild behavior.
- `--skip-git-plan`: rebuild data without git planning.
- `--git-commit-batches`: create commits without pushing.

## References

- `README.md`: project layout and human-facing update instructions.
- `docs\AssetUpdate.md`: detailed data pipeline notes.
- `update.py`: authoritative top-level orchestration entrypoint.
- `tools\archive_sources.py`: archive source resolution rules.
