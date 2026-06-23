from pathlib import Path
from typing import Any, Iterable


ICON_REFERENCE_KEYS = ("ObjectPath", "AssetPathName")


def extract_asset_reference(value: Any) -> str:
    if isinstance(value, dict):
        for key in ICON_REFERENCE_KEYS:
            ref = value.get(key)
            if isinstance(ref, str) and ref.strip():
                return ref.strip()
    if isinstance(value, str) and value.strip():
        return value.strip()
    return ""


def iter_asset_references(value: Any) -> Iterable[str]:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in ICON_REFERENCE_KEYS and isinstance(item, str) and item.strip():
                yield item.strip()
            yield from iter_asset_references(item)
    elif isinstance(value, list):
        for item in value:
            yield from iter_asset_references(item)


def normalize_asset_path_to_png_rel(asset_path: str) -> Path | None:
    raw = str(asset_path or "").strip().strip("\"")
    if not raw:
        return None

    if "'" in raw:
        first_quote = raw.find("'")
        last_quote = raw.rfind("'")
        if last_quote > first_quote:
            raw = raw[first_quote + 1 : last_quote]

    cleaned = raw.replace("\\", "/").strip()
    if not cleaned:
        return None

    parts = cleaned.strip("/").split("/")
    if not parts or not parts[-1]:
        return None

    leaf = parts[-1]
    if "." in leaf:
        leaf = leaf.split(".", 1)[0]
    parts[-1] = leaf
    cleaned = "/".join(parts)

    if cleaned.startswith("textures/"):
        logical = cleaned
    elif cleaned.startswith("Game/"):
        logical = f"textures/RSDragonwilds/Content/{cleaned.removeprefix('Game/')}"
    elif cleaned.startswith("RSDragonwilds/Content/") or cleaned.startswith(
        "RSDragonwilds/Plugins/"
    ):
        logical = f"textures/{cleaned}"
    else:
        mount, sep, rest = cleaned.partition("/")
        if sep and mount not in {"Engine", "Script"}:
            logical = f"textures/RSDragonwilds/Plugins/GameFeatures/{mount}/Content/{rest}"
        else:
            logical = f"textures/{cleaned}"

    rel = Path(logical)
    if rel.suffix.lower() != ".png":
        rel = rel.with_suffix(".png")
    return rel


def build_png_name_index(root: Path) -> dict[str, list[Path]]:
    index: dict[str, list[Path]] = {}
    if not root.exists():
        return index
    for png in sorted(root.rglob("*.png")):
        index.setdefault(png.name.lower(), []).append(png)
    return index


def resolve_png_reference(
    asset_path: str,
    content_root: Path,
    png_index: dict[str, list[Path]],
) -> Path | None:
    icon_rel = normalize_asset_path_to_png_rel(asset_path)
    if not icon_rel:
        return None

    direct = content_root / icon_rel
    if direct.exists():
        return direct

    by_name = png_index.get(icon_rel.name.lower(), [])
    if not by_name:
        return None
    if len(by_name) == 1:
        return by_name[0]

    rel_tail = icon_rel.as_posix().lower()
    unprefixed_tail = rel_tail.removeprefix("textures/")
    for candidate in by_name:
        candidate_path = candidate.as_posix().lower()
        if candidate_path.endswith(rel_tail) or candidate_path.endswith(unprefixed_tail):
            return candidate
    return by_name[0]
