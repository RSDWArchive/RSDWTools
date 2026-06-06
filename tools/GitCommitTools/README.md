# Vendored GitCommitTools

This is the vendored copy of the generic git batch planner used by RSDWTools.
Prefer the project wrapper unless you are changing the generic planner itself:

```powershell
python .\tools\PlanGitCommits.py
```

The tool inspects the working tree, flags files over GitHub's 100 MiB file
limit, and splits the remaining changed paths into conservative commit batches
under a configurable size cap.

`commit-batches` is a dry run unless `--execute` is provided.
