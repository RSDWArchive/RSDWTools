# RSDWTools Pipeline Handoff

This is the automation handoff contract for RSDWTools.

Use this document when an external orchestrator needs to run RSDWTools as one
stage in a larger multi-project pipeline. The machine-readable version of this
contract lives in `pipeline.contract.json`.

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

Historical full build and publish command:

```powershell
cd E:\Github\RSDWTools
python update.py --git-commit-batches --git-push-each
```

Preferred explicit orchestration commands:

```powershell
cd E:\Github\RSDWTools
python update.py --mode build-local
python update.py --mode validate-local
python update.py --mode publish --git-mode plan-only
python update.py --mode publish --git-mode commit-only
python update.py --mode publish --git-mode push-each
python update.py --mode validate-published
```

The orchestrator should treat a nonzero exit code as fatal and stop the larger
pipeline before downstream projects run.

`build-local` performs a fresh rebuild without Git. `validate-local` is
read-only. `publish` validates the existing generated outputs first, then runs
the Git planner, commit batches, or push-each flow requested by `--git-mode`.

## Structured Artifacts

Every build or publish run writes a timestamped run directory:

```text
PipelineLogs\<timestamp>\
  PipelineRun.json
  warnings.json
  warnings.md
  GitCommitPlan.json
  logs\
```

The repo root `PipelineRun.json` is a latest-run compatibility copy of the
canonical timestamped summary. It includes `canonicalPath` pointing back to the
timestamped summary.

The canonical Git plan path is:

```text
PipelineLogs\<timestamp>\GitCommitPlan.json
```

The root `GitCommitPlan.json` remains an ignored compatibility copy.

## Internal Stage Order

`update.py --mode full` and the historical command run these stages in order:

1. Resolve archive sources from `RSDWArchive`.
2. Clean generated RSDWTools data because `--fresh` is enabled by default.
3. Run `tools/rebuild_docs_data.py`.
4. Run `tools/build_character_catalog.py`.
5. Run `tools/PlanGitCommits.py`.
6. Commit batches when requested.
7. Push each created batch when requested.
8. Write `PipelineRun.json`, warning summaries, and artifact metadata.

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
- Structured run summary at `PipelineLogs\<timestamp>\PipelineRun.json`
- Latest-run summary copy at `PipelineRun.json`
- Warning summary at `PipelineLogs\<timestamp>\warnings.json`
- Git plan at `PipelineLogs\<timestamp>\GitCommitPlan.json`
- Git commit batches created by the pipeline command
- Pushed commits when `--git-push-each` or `--git-mode push-each` is used

## Success Criteria

The RSDWTools stage is successful when all of these are true:

- The process exits with code `0`.
- Output includes `[INFO] Update pipeline complete.` for build/full/publish
  runs that complete successfully.
- `PipelineRun.json` has schema `RSDWTools.UpdatePipeline.v1` and status
  `complete`.
- `PipelineRun.json` records the Archive dataset identity consumed.
- Required generated JSON files exist, parse, and have nonempty expected
  catalog sections.
- Warning policy passes: known nonfatal categories pass, fatal categories fail,
  and `unknown_warning` fails unless `--allow-unknown-warnings` is explicitly
  used.
- If files changed during commit/push modes, git commit batches were created.
- With `--git-mode push-each`, created commits were pushed to the configured
  remote.

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
- Required generated JSON is missing or invalid.
- The summary Archive identity does not match the current or requested Archive
  dataset.
- A fatal or unknown warning category is present without an explicit override.
- Git has staged changes before commit batching starts.
- A changed file exceeds the git planner file limit.
- Commit creation fails.
- Push fails because of authentication, permissions, network, or remote changes.

Missing-icon warnings for deprecated, test, or mesh-only assets can be
non-fatal when they are classified as known warning categories.

## Validation

Project-owned validation command:

```powershell
python tools/validate_pipeline_outputs.py --summary PipelineRun.json
```

Equivalent orchestration wrapper:

```powershell
python update.py --mode validate-local
```

Published validation:

```powershell
python update.py --mode validate-published
```

`validate-local` compares the summary Archive dataset against the current
`RSDWArchive\website\data.config.json` by default. Pass
`--expected-dataset-version` or `--game-root` for intentional historical or
recovery validation.

## Useful Overrides

Use these only when the orchestrator intentionally needs non-default sources or
behavior:

- `--archive-root <path>`: use another RSDWArchive checkout.
- `--game-root <path>`: use an explicit archive dataset folder.
- `--location-data-root <path>`: use explicit LocationData.
- `--loot-data-root <path>`: use explicit LootData.
- `--pipeline-log-dir <path>`: choose a run artifact directory.
- `--pipeline-summary-output <path>`: choose the latest-summary copy path.
- `--no-fresh`: skip the default clean rebuild behavior.
- `--skip-git-plan`: rebuild data without git planning.
- `--git-commit-batches`: create commits without pushing.
- `--git-mode plan-only`: create only the Git plan.
- `--git-mode commit-only`: create commits without pushing.
- `--git-mode push-each`: create commits and push each batch.
- `--allow-unknown-warnings`: permit unknown warning categories for an
  intentional run.

## References

- `pipeline.contract.json`: machine-readable command and artifact contract.
- `README.md`: project layout and human-facing update instructions.
- `docs\AssetUpdate.md`: detailed data pipeline notes.
- `update.py`: authoritative top-level orchestration entrypoint.
- `tools\validate_pipeline_outputs.py`: project-owned validator.
- `tools\archive_sources.py`: archive source resolution rules.
