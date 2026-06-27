from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


SUMMARY_SCHEMA = "RSDWTools.UpdatePipeline.v1"
WARNING_SCHEMA = "RSDWTools.WarningSummary.v1"

KNOWN_NONFATAL = "known_nonfatal"
WARNING = "warning"
FATAL = "fatal"


WARNING_RULES: list[tuple[str, str, tuple[str, ...]]] = [
    ("missing_location_data", FATAL, ("LocationData", "not found")),
    ("missing_loot_data", FATAL, ("LootData", "not found")),
    ("missing_quest_data", FATAL, ("QuestData", "not found")),
    ("missing_item_icon", KNOWN_NONFATAL, ("Icon missing:",)),
    ("missing_item_icon", KNOWN_NONFATAL, ("Icon not found:",)),
    ("missing_item_icon", KNOWN_NONFATAL, ("Missing item icons:",)),
    ("missing_recipe_icon", KNOWN_NONFATAL, ("Missing recipe icons:",)),
    ("placeholder_icon_used", KNOWN_NONFATAL, ("Placeholder icons used:",)),
    ("placeholder_icon_used", KNOWN_NONFATAL, ("Placeholder icon missing",)),
    ("placeholder_icon_used", KNOWN_NONFATAL, ("Placeholder icon not found",)),
    ("missing_spell_icon", KNOWN_NONFATAL, ("Spell icon not found:",)),
    ("missing_spell_icon", KNOWN_NONFATAL, ("Tag icon not found:",)),
    ("missing_spell_icon", KNOWN_NONFATAL, ("Missing spell icons:",)),
    ("missing_spell_icon", KNOWN_NONFATAL, ("Placeholder spell icon missing",)),
    ("missing_skill_icon", WARNING, ("Skill icon not found:",)),
    ("missing_skill_icon", WARNING, ("Skill tag icon not found:",)),
    ("missing_skill_icon", WARNING, ("Missing skill icons:",)),
    ("missing_mount_icon", WARNING, ("Mount icon not found:",)),
    ("missing_mount_icon", WARNING, ("Missing mount icons:",)),
    ("missing_mount_data", WARNING, ("Mount asset directory not found:",)),
    ("missing_mount_data", WARNING, ("Mount string table not found:",)),
    ("missing_vendor_reputation_data", WARNING, ("Vendor reputation source directory not found:",)),
    ("json_parse_failed", WARNING, ("JSON parse failed:",)),
    ("unexpected_json_shape", WARNING, ("Unexpected JSON root:",)),
    ("missing_source", WARNING, ("Source missing:",)),
    ("missing_source", WARNING, ("Item source not found:",)),
    ("missing_table", WARNING, ("Missing table:",)),
    ("missing_skill_data", WARNING, ("Skills directory not found:",)),
    ("missing_skill_data", WARNING, ("Skill data missing:",)),
    ("missing_skill_data", WARNING, ("Skill PersistenceID missing:",)),
    ("quest_definitions_skipped", WARNING, ("Quest definitions skipped:",)),
]


COUNT_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"JSON scanned:\s*([\d,]+)"), "ingestJsonScanned"),
    (re.compile(r"JSON unmatched:\s*([\d,]+)"), "ingestJsonUnmatched"),
    (re.compile(r"Duplicate files skipped:\s*([\d,]+)"), "ingestDuplicatesSkipped"),
    (re.compile(r"Recipes indexed:\s*([\d,]+)"), "recipesIndexed"),
    (re.compile(r"Recipes skipped \(no output item\):\s*([\d,]+)"), "recipesSkippedNoOutputItem"),
    (re.compile(r"Missing recipe icons:\s*([\d,]+)"), "missingRecipeIcons"),
    (re.compile(r"Placeholder icons used:\s*([\d,]+)"), "placeholderRecipeIconsUsed"),
    (re.compile(r"Quests indexed:\s*([\d,]+)"), "questsIndexed"),
    (re.compile(r"Spells indexed:\s*([\d,]+)"), "spellsIndexed"),
    (re.compile(r"Missing spell icons:\s*([\d,]+)"), "missingSpellIcons"),
    (re.compile(r"Points indexed:\s*([\d,]+)"), "mapPointsIndexed"),
    (re.compile(r"Skipped files:\s*([\d,]+)"), "mapFilesSkipped"),
    (re.compile(r"Skills indexed:\s*([\d,]+)"), "characterSkillsIndexed"),
    (re.compile(r"Skills skipped:\s*([\d,]+)"), "characterSkillsSkipped"),
    (re.compile(r"Missing skill icons:\s*([\d,]+)"), "missingSkillIcons"),
    (re.compile(r"Mounts indexed:\s*([\d,]+)"), "mountsIndexed"),
    (re.compile(r"Missing mount icons:\s*([\d,]+)"), "missingMountIcons"),
    (re.compile(r"Vendor reputations indexed:\s*([\d,]+)"), "vendorReputationsIndexed"),
]


SCRIPT_COUNT_KEYS: dict[str, dict[str, str]] = {
    "build_chest_item_catalog.py": {
        "Items indexed": "itemsIndexed",
        "Missing item icons": "missingItemIcons",
    },
    "build_recipe_index.py": {
        "Items indexed": "recipeSourceItemsIndexed",
        "Missing item icons": "missingRecipeSourceItemIcons",
    },
    "build_spell_catalog.py": {
        "Items indexed": "spellSourceItemsIndexed",
        "Missing item icons": "missingSpellSourceItemIcons",
    },
}


class PipelineStepError(RuntimeError):
    def __init__(self, stage_name: str, returncode: int, command: Iterable[str]):
        self.stage_name = stage_name
        self.returncode = returncode
        self.command = list(command)
        super().__init__(
            f"Stage {stage_name} failed with exit code {returncode}: {' '.join(self.command)}"
        )


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def format_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_int(value: str) -> int:
    return int(value.replace(",", ""))


def classify_warning(line: str) -> tuple[str, str]:
    for category, severity, needles in WARNING_RULES:
        if all(needle in line for needle in needles):
            return category, severity
    return "unknown_warning", WARNING


def detect_child_script(line: str, current: str | None) -> str | None:
    if not line.startswith("[STEP]"):
        return current
    for script in SCRIPT_COUNT_KEYS:
        if script in line:
            return script
    if "ingest_game_data.py" in line:
        return "ingest_game_data.py"
    if "build_quest_catalog.py" in line:
        return "build_quest_catalog.py"
    if "build_mapdata_index.py" in line:
        return "build_mapdata_index.py"
    if "build_character_catalog.py" in line:
        return "build_character_catalog.py"
    return current


def extract_count(line: str, current_script: str | None) -> tuple[str, int] | None:
    info_match = re.search(r"\[INFO\]\s*([^:]+):\s*([\d,]+)\s*$", line)
    if info_match and current_script in SCRIPT_COUNT_KEYS:
        label = info_match.group(1).strip()
        key = SCRIPT_COUNT_KEYS[current_script].get(label)
        if key:
            return key, parse_int(info_match.group(2))

    for pattern, key in COUNT_PATTERNS:
        match = pattern.search(line)
        if match:
            return key, parse_int(match.group(1))
    return None


class PipelineRun:
    def __init__(
        self,
        repo_root: Path,
        argv: list[str],
        *,
        mode: str,
        git_mode: str | None,
        log_dir: Path | None = None,
        latest_summary_path: Path | None = None,
        allow_unknown_warnings: bool = False,
    ) -> None:
        self.repo_root = repo_root.resolve()
        self.started = utc_now()
        self.run_id = self.started.strftime("%Y%m%d-%H%M%SZ")
        self.log_dir = (log_dir or (self.repo_root / "PipelineLogs" / self.run_id)).resolve()
        self.logs_dir = self.log_dir / "logs"
        self.summary_path = self.log_dir / "PipelineRun.json"
        self.latest_summary_path = (latest_summary_path or (self.repo_root / "PipelineRun.json")).resolve()
        self.allow_unknown_warnings = allow_unknown_warnings
        self.warning_details: dict[str, dict[str, Any]] = {}

        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)

        self.data: dict[str, Any] = {
            "schema": SUMMARY_SCHEMA,
            "project": "RSDWTools",
            "status": "running",
            "runId": self.run_id,
            "canonicalPath": str(self.summary_path),
            "startedUtc": format_utc(self.started),
            "finishedUtc": None,
            "durationS": None,
            "mode": mode,
            "gitMode": git_mode,
            "allowUnknownWarnings": allow_unknown_warnings,
            "commands": {
                "argv": argv,
                "cwd": str(self.repo_root),
            },
            "archive": {},
            "stages": [],
            "counts": {},
            "warnings": {
                "categories": {},
                "unknownWarnings": [],
            },
            "releaseDecision": {
                "status": "pass",
                "reasons": [],
            },
            "artifacts": {},
            "git": {},
        }
        self.write()

    def archive_payload(self, sources: Any) -> dict[str, str]:
        archive_root = Path(sources.archive_root)
        quest_data_path = archive_root / "website" / "tools" / "QuestData" / "QuestData.json"
        return {
            "archiveRoot": str(archive_root),
            "datasetVersion": sources.dataset_version,
            "datasetRoot": str(Path(sources.game_root)),
            "configPath": str(archive_root / "website" / "data.config.json"),
            "locationDataRoot": str(Path(sources.location_data_root)),
            "lootDataRoot": str(Path(sources.loot_data_root)),
            "questDataPath": str(quest_data_path),
            "source": str(sources.source),
        }

    def set_archive(self, sources: Any) -> None:
        self.data["archive"] = self.archive_payload(sources)
        self.write()

    def set_archive_from_summary(self, summary: dict[str, Any]) -> None:
        archive = summary.get("archive")
        if isinstance(archive, dict):
            self.data["archive"] = archive
            self.write()

    def set_validated_summary(self, summary: dict[str, Any], summary_path: Path) -> None:
        self.set_archive_from_summary(summary)
        self.data["validatedBuild"] = {
            "summaryPath": str(summary_path.resolve()),
            "canonicalPath": summary.get("canonicalPath"),
            "status": summary.get("status"),
            "mode": summary.get("mode"),
            "startedUtc": summary.get("startedUtc"),
            "finishedUtc": summary.get("finishedUtc"),
        }
        counts = summary.get("counts")
        if isinstance(counts, dict):
            self.data["counts"] = counts

        warnings = summary.get("warnings")
        if isinstance(warnings, dict):
            categories = warnings.get("categories") if isinstance(warnings.get("categories"), dict) else {}
            unknown_warnings = (
                warnings.get("unknownWarnings")
                if isinstance(warnings.get("unknownWarnings"), list)
                else []
            )
            self.data["warnings"] = {
                "categories": categories,
                "unknownWarnings": unknown_warnings,
            }
            self.warning_details = {
                category: {
                    "category": category,
                    "severity": details.get("severity", WARNING) if isinstance(details, dict) else WARNING,
                    "count": details.get("count", 0) if isinstance(details, dict) else 0,
                    "examples": details.get("examples", []) if isinstance(details, dict) else [],
                }
                for category, details in categories.items()
            }
        self.update_release_decision()
        self.write()

    def begin_stage(
        self,
        name: str,
        *,
        command: list[str] | None = None,
        cwd: Path | None = None,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        started = utc_now()
        log_path = self.logs_dir / f"{len(self.data['stages']) + 1:02d}_{name}.log"
        stage: dict[str, Any] = {
            "name": name,
            "status": "running",
            "startedUtc": format_utc(started),
            "finishedUtc": None,
            "durationS": None,
            "command": command or [],
            "cwd": str((cwd or self.repo_root).resolve()),
            "logPath": str(log_path),
            "exitCode": None,
            "warnings": {},
            "counts": {},
            "ok": False,
        }
        if details:
            stage["details"] = details
        stage["_started"] = started
        stage["_currentScript"] = None
        self.data["stages"].append(stage)
        self.write()
        return stage

    def finish_stage(
        self,
        stage: dict[str, Any],
        *,
        status: str,
        exit_code: int | None = 0,
        error: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        finished = utc_now()
        started = stage.pop("_started", finished)
        stage.pop("_currentScript", None)
        stage["status"] = status
        stage["finishedUtc"] = format_utc(finished)
        stage["durationS"] = round((finished - started).total_seconds(), 3)
        stage["exitCode"] = exit_code
        stage["ok"] = status == "complete" and (exit_code in (0, None))
        if error:
            stage["error"] = error
        if details:
            stage.setdefault("details", {}).update(details)
        self.update_release_decision()
        self.write()

    def record_stage(
        self,
        name: str,
        *,
        details: dict[str, Any] | None = None,
        status: str = "complete",
        error: str | None = None,
    ) -> None:
        stage = self.begin_stage(name, details=details)
        self.finish_stage(stage, status=status, exit_code=0 if status == "complete" else 1, error=error)

    def handle_output_line(self, stage: dict[str, Any], line: str) -> None:
        stage["_currentScript"] = detect_child_script(line, stage.get("_currentScript"))

        count = extract_count(line, stage.get("_currentScript"))
        if count:
            key, value = count
            stage["counts"][key] = value
            self.data["counts"][key] = value

        if "[WARN]" not in line:
            return

        category, severity = classify_warning(line)
        stage["warnings"][category] = stage["warnings"].get(category, 0) + 1

        details = self.warning_details.setdefault(
            category,
            {
                "category": category,
                "severity": severity,
                "count": 0,
                "examples": [],
            },
        )
        details["count"] += 1
        if line.strip() not in details["examples"] and len(details["examples"]) < 10:
            details["examples"].append(line.strip())

        if category == "unknown_warning":
            unknowns = self.data["warnings"].setdefault("unknownWarnings", [])
            if line.strip() not in unknowns and len(unknowns) < 50:
                unknowns.append(line.strip())

        self.data["warnings"]["categories"] = {
            key: {
                "severity": value["severity"],
                "count": value["count"],
                "examples": value["examples"],
            }
            for key, value in sorted(self.warning_details.items())
        }

    def run_command(self, name: str, command: list[str], cwd: Path) -> None:
        printable = " ".join(command)
        print(f"[STEP] {printable}")
        stage = self.begin_stage(name, command=command, cwd=cwd)
        log_path = Path(stage["logPath"])
        with log_path.open("w", encoding="utf-8", errors="replace") as log:
            log.write(f"[STEP] {printable}\n")
            log.flush()
            proc = subprocess.Popen(
                command,
                cwd=str(cwd),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )
            assert proc.stdout is not None
            for line in proc.stdout:
                print(line, end="")
                log.write(line)
                self.handle_output_line(stage, line)
            returncode = proc.wait()

        if returncode != 0:
            self.finish_stage(stage, status="failed", exit_code=returncode)
            raise PipelineStepError(name, returncode, command)

        self.finish_stage(stage, status="complete", exit_code=returncode)

    def record_artifacts(self, artifacts: dict[str, Path]) -> None:
        payload: dict[str, dict[str, Any]] = {}
        for key, path in artifacts.items():
            resolved = path.resolve()
            item: dict[str, Any] = {
                "path": str(resolved),
                "exists": resolved.exists(),
            }
            if resolved.exists() and resolved.is_file():
                item["sizeBytes"] = resolved.stat().st_size
            payload[key] = item
        self.data["artifacts"].update(payload)
        self.write()

    def merge_counts(self, counts: dict[str, int]) -> None:
        self.data["counts"].update(counts)
        self.write()

    def record_git_plan(self, canonical_plan: Path, compatibility_plan: Path | None = None) -> None:
        git_payload: dict[str, Any] = {
            "planPath": str(canonical_plan.resolve()),
            "planExists": canonical_plan.exists(),
        }
        if compatibility_plan:
            git_payload["compatibilityPlanPath"] = str(compatibility_plan.resolve())
            git_payload["compatibilityPlanExists"] = compatibility_plan.exists()

        if canonical_plan.exists():
            try:
                plan = json.loads(canonical_plan.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                git_payload["planError"] = f"invalid JSON: {exc}"
            else:
                git_payload["schema"] = plan.get("schema")
                git_payload["changedPathCount"] = plan.get("changed_path_count")
                git_payload["allowedPathCount"] = plan.get("allowed_path_count")
                git_payload["blockedPathCount"] = plan.get("blocked_path_count")
                git_payload["batchCount"] = len(plan.get("batches") or [])
                git_payload["statusCounts"] = plan.get("status_counts") or {}
                git_payload["batches"] = [
                    {
                        "index": batch.get("index"),
                        "pathCount": batch.get("path_count"),
                        "sizeBytes": batch.get("size_bytes"),
                    }
                    for batch in (plan.get("batches") or [])
                ]
        self.data["git"].update(git_payload)
        self.write()

    def copy_git_plan_compatibility(self, canonical_plan: Path) -> Path | None:
        if not canonical_plan.exists():
            return None
        compatibility_plan = self.repo_root / "GitCommitPlan.json"
        if canonical_plan.resolve() != compatibility_plan.resolve():
            shutil.copyfile(canonical_plan, compatibility_plan)
        return compatibility_plan

    def update_release_decision(self) -> None:
        reasons: list[str] = []
        categories = self.data.get("warnings", {}).get("categories", {})
        for category, details in sorted(categories.items()):
            severity = details.get("severity")
            if severity == FATAL:
                reasons.append(f"fatal warning category present: {category}")
            if category == "unknown_warning" and not self.allow_unknown_warnings:
                reasons.append("unknown warning category present")
        failed_stages = [
            stage["name"]
            for stage in self.data.get("stages", [])
            if stage.get("status") == "failed"
        ]
        for stage_name in failed_stages:
            reasons.append(f"stage failed: {stage_name}")
        self.data["releaseDecision"] = {
            "status": "fail" if reasons else "pass",
            "reasons": reasons,
        }

    def warning_summary_payload(self) -> dict[str, Any]:
        return {
            "schema": WARNING_SCHEMA,
            "generatedAtUtc": format_utc(utc_now()),
            "categories": self.data["warnings"].get("categories", {}),
            "unknownWarnings": self.data["warnings"].get("unknownWarnings", []),
            "releaseDecision": self.data.get("releaseDecision", {}),
        }

    def write_warning_files(self) -> None:
        payload = self.warning_summary_payload()
        warnings_json = self.log_dir / "warnings.json"
        warnings_json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

        lines = ["# Pipeline Warnings", ""]
        categories = payload["categories"]
        if not categories:
            lines.append("No warnings were captured.")
        else:
            for category, details in sorted(categories.items()):
                lines.append(
                    f"- {category}: {details.get('count', 0)} ({details.get('severity', WARNING)})"
                )
                for example in details.get("examples", [])[:3]:
                    lines.append(f"  - `{example}`")
        lines.append("")
        lines.append(f"Release decision: {payload['releaseDecision'].get('status', 'unknown')}")
        (self.log_dir / "warnings.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

        self.data["artifacts"]["warningSummary"] = {
            "path": str(warnings_json.resolve()),
            "exists": True,
            "sizeBytes": warnings_json.stat().st_size,
        }

    def complete(self) -> None:
        self.data["status"] = "complete"
        finished = utc_now()
        self.data["finishedUtc"] = format_utc(finished)
        self.data["durationS"] = round((finished - self.started).total_seconds(), 3)
        self.update_release_decision()
        self.write_warning_files()
        self.write()

    def fail(self, error: str) -> None:
        self.data["status"] = "failed"
        self.data["error"] = error
        finished = utc_now()
        self.data["finishedUtc"] = format_utc(finished)
        self.data["durationS"] = round((finished - self.started).total_seconds(), 3)
        self.update_release_decision()
        self.write_warning_files()
        self.write()

    def write(self) -> None:
        public_data = self._public_data()
        self.summary_path.parent.mkdir(parents=True, exist_ok=True)
        self.summary_path.write_text(json.dumps(public_data, indent=2) + "\n", encoding="utf-8")
        if self.latest_summary_path:
            self.latest_summary_path.parent.mkdir(parents=True, exist_ok=True)
            self.latest_summary_path.write_text(json.dumps(public_data, indent=2) + "\n", encoding="utf-8")

    def _public_data(self) -> dict[str, Any]:
        def clean(value: Any) -> Any:
            if isinstance(value, dict):
                return {key: clean(item) for key, item in value.items() if not key.startswith("_")}
            if isinstance(value, list):
                return [clean(item) for item in value]
            return value

        return clean(self.data)


def read_summary(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def command_argv() -> list[str]:
    return [Path(sys.executable).name, *sys.argv]
