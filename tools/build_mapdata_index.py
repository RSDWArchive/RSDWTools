import argparse
import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"[WARN] JSON parse failed: {path} ({exc})")
        return None


def parse_xyz_string(value: Any) -> tuple[float | None, float | None, float | None]:
    parts = str(value).strip().split()
    if len(parts) < 2:
        return None, None, None
    try:
        x = float(parts[0])
        y = float(parts[1])
        z = float(parts[2]) if len(parts) > 2 else None
    except ValueError:
        return None, None, None
    return x, y, z


def build_from_location_file(source_file: Path) -> tuple[list[dict[str, Any]], dict[str, set[str]], int]:
    points: list[dict[str, Any]] = []
    categories: dict[str, set[str]] = {"Locations": {"All"}}
    skipped = 0
    data = load_json(source_file)
    if not isinstance(data, dict):
        print(f"[ERROR] Expected object JSON in: {source_file}")
        return points, categories, 1
    for key, value in data.items():
        x, y, z = parse_xyz_string(value)
        if x is None or y is None:
            skipped += 1
            continue
        points.append(
            {
                "x": x,
                "y": y,
                "z": z,
                "label": str(key),
                "category": "Locations",
                "subtype": "All",
                "path": source_file.name,
            }
        )
    return points, categories, skipped


def build_from_json_folder(source_dir: Path) -> tuple[list[dict[str, Any]], dict[str, set[str]], int]:
    points = []
    categories: dict[str, set[str]] = {}
    skipped = 0

    for file_path in sorted(source_dir.rglob("*.json")):
        data = load_json(file_path)
        if not isinstance(data, dict):
            skipped += 1
            continue
        props = data.get("Properties") or {}
        location = props.get("RelativeLocation")
        if not isinstance(location, dict):
            skipped += 1
            continue

        rel = file_path.relative_to(source_dir)
        parts = rel.parts
        category = parts[0] if parts else "Unknown"
        subtype = parts[1] if len(parts) > 2 else (parts[1] if len(parts) > 1 else category)

        categories.setdefault(category, set()).add(subtype)

        points.append(
            {
                "x": location.get("X"),
                "y": location.get("Y"),
                "z": location.get("Z"),
                "label": file_path.stem,
                "category": category,
                "subtype": subtype,
                "path": str(rel).replace("\\", "/"),
            }
        )
    return points, categories, skipped


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a mapdata index for map filtering."
    )
    parser.add_argument(
        "--source",
        default="data/location_data/LocationData.json",
        help="Map source: folder of map object JSONs or LocationData.json file.",
    )
    parser.add_argument(
        "--output",
        default="website/data/mapdata_index.json",
        help="Output JSON index path.",
    )
    args = parser.parse_args()

    source_path = Path(args.source)
    output_path = Path(args.output)

    if not source_path.exists():
        print(f"[ERROR] Source path not found: {source_path}")
        return 1

    if source_path.is_file():
        points, categories, skipped = build_from_location_file(source_path)
    else:
        points, categories, skipped = build_from_json_folder(source_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(
            {
                "points": points,
                "categories": {
                    key: sorted(values) for key, values in sorted(categories.items())
                },
            },
            indent=2,
            ensure_ascii=True,
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"[INFO] Points indexed: {len(points)}")
    print(f"[INFO] Skipped files: {skipped}")
    print(f"[INFO] Wrote index: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
