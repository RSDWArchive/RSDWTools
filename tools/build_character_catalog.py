import argparse
import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def extract_rows(data: object) -> list[str]:
    rows = {}
    if isinstance(data, list) and data:
        first = data[0]
        if isinstance(first, dict):
            rows = first.get("Rows", {}) or {}
    elif isinstance(data, dict):
        rows = data.get("Rows", {}) or {}
    if not isinstance(rows, dict):
        return []
    return sorted(rows.keys())


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a character customization catalog from data tables."
    )
    parser.add_argument(
        "--source",
        default="website/tools/character-editor/data",
        help="Directory containing customization data tables.",
    )
    parser.add_argument(
        "--output",
        default="website/tools/character-editor/data/character_catalog.json",
        help="Output JSON path for the catalog.",
    )
    args = parser.parse_args()

    source_dir = Path(args.source)
    output_path = Path(args.output)
    if not source_dir.exists():
        print(f"[ERROR] Source directory not found: {source_dir}")
        return 1

    mapping = {
        "BodyType": "DT_Customization_BodyType.json",
        "Head": "DT_Customization_FaceType.json",
        "HairPreset": "DT_Customization_HairPresets.json",
        "FacialHairPreset": "DT_Customization_FacialHairPresets.json",
        "SkinTone": "DT_Customization_SkinTone.json",
        "HairColor": "DT_Customization_HairColor.json",
        "EyeColor": "DT_Customization_EyeColor.json",
        "EyebrowColor": "DT_Customization_EyebrowColor.json",
    }

    catalog: dict[str, list[str]] = {}
    for key, filename in mapping.items():
        path = source_dir / filename
        if not path.exists():
            print(f"[WARN] Missing table: {path}")
            catalog[key] = []
            continue
        data = load_json(path)
        catalog[key] = extract_rows(data)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(catalog, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    print(f"[INFO] Wrote catalog: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
