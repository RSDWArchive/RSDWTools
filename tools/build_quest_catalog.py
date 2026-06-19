import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from archive_sources import DEFAULT_ARCHIVE_ROOT


QUEST_DATA_RELATIVE = Path("website") / "tools" / "QuestData" / "QuestData.json"


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_quest_data(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"QuestData source not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("quests"), dict):
        raise ValueError(f"Unexpected QuestData shape: {path}")
    return data


def clean_text(value: Any) -> str:
    return str(value or "").strip()


def build_catalog(source: Path) -> dict[str, Any]:
    quest_data = load_quest_data(source)
    source_quests = quest_data["quests"]
    name_counts = Counter(
        clean_text(quest.get("displayName") or quest.get("internalName") or key)
        for key, quest in source_quests.items()
        if isinstance(quest, dict)
    )

    quests: list[dict[str, Any]] = []
    skipped = 0
    for key, quest in source_quests.items():
        if not isinstance(quest, dict):
            skipped += 1
            continue
        persistence_id = clean_text(quest.get("persistenceId"))
        if not persistence_id:
            skipped += 1
            continue
        internal_name = clean_text(quest.get("internalName") or quest.get("id") or key)
        display_name = clean_text(quest.get("displayName") or internal_name)
        quests.append(
            {
                "persistence_id": persistence_id,
                "internal_name": internal_name,
                "display_name": display_name,
                "is_main_quest": bool(quest.get("isMainQuest")),
                "quest_region": quest.get("questRegion"),
                "duplicate_display_name": name_counts[display_name] > 1,
            }
        )

    quests.sort(
        key=lambda quest: (
            not quest["is_main_quest"],
            quest["display_name"].casefold(),
            quest["internal_name"].casefold(),
            quest["persistence_id"],
        )
    )

    if skipped:
        print(f"[WARN] Quest definitions skipped: {skipped}")

    return {
        "version": quest_data.get("version") or "",
        "generatedAtUtc": utc_timestamp(),
        "quests": quests,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the Quest Editor catalog.")
    parser.add_argument(
        "--archive-root",
        default=str(DEFAULT_ARCHIVE_ROOT),
        help="RSDWArchive checkout root containing website/tools/QuestData/QuestData.json.",
    )
    parser.add_argument(
        "--source",
        default="",
        help="Explicit QuestData.json source path.",
    )
    parser.add_argument(
        "--out",
        default="website/tools/quest-editor/data/quests.json",
        help="Output path for the website quest catalog.",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    source = Path(args.source) if args.source else Path(args.archive_root) / QUEST_DATA_RELATIVE
    output = Path(args.out)
    if not output.is_absolute():
        output = repo_root / output

    catalog = build_catalog(source)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")

    print(f"[INFO] QuestData source: {source}")
    print(f"[INFO] Quest catalog written: {output}")
    print(f"[INFO] Quests indexed: {len(catalog['quests'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
