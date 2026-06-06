import json
import re
from dataclasses import dataclass
from pathlib import Path


DEFAULT_ARCHIVE_ROOT = Path(r"E:\Github\RSDWArchive")
DATA_CONFIG_RELATIVE = Path("website") / "data.config.json"
LOCATION_DATA_RELATIVE = Path("website") / "tools" / "LocationData"
LOOT_DATA_RELATIVE = Path("website") / "tools" / "LootData"
VERSION_RE = re.compile(r"^\d+(?:\.\d+)*$")


@dataclass(frozen=True)
class ArchiveSources:
    archive_root: Path
    game_root: Path
    dataset_version: str
    location_data_root: Path
    loot_data_root: Path
    source: str


def _version_key(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def _read_config_version(config_path: Path) -> str:
    if not config_path.exists():
        return ""
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Archive config is not valid JSON: {config_path} ({exc})") from exc
    version = str(payload.get("datasetVersion") or "").strip()
    if not version:
        raise ValueError(f"Archive config is missing datasetVersion: {config_path}")
    return version


def _find_latest_dataset_version(archive_root: Path) -> str:
    candidates = [
        path.name
        for path in archive_root.iterdir()
        if path.is_dir() and VERSION_RE.match(path.name) and (path / "json").is_dir()
    ]
    if not candidates:
        raise ValueError(f"No versioned archive datasets found under: {archive_root}")
    return max(candidates, key=_version_key)


def _validate_path(path: Path, label: str) -> None:
    if not path.exists():
        raise ValueError(f"{label} not found: {path}")


def resolve_archive_sources(
    archive_root: str | Path = DEFAULT_ARCHIVE_ROOT,
    game_root: str | Path | None = None,
    location_data_root: str | Path | None = None,
    loot_data_root: str | Path | None = None,
) -> ArchiveSources:
    archive_root = Path(archive_root)
    _validate_path(archive_root, "Archive root")

    source = "explicit --game-root"
    if game_root:
        resolved_game_root = Path(game_root)
        dataset_version = resolved_game_root.name
    else:
        config_path = archive_root / DATA_CONFIG_RELATIVE
        dataset_version = _read_config_version(config_path)
        resolved_game_root = archive_root / dataset_version
        source = str(config_path)
        if not resolved_game_root.exists():
            fallback_version = _find_latest_dataset_version(archive_root)
            resolved_game_root = archive_root / fallback_version
            dataset_version = fallback_version
            source = f"directory scan fallback from {config_path}"

    _validate_path(resolved_game_root, "Game archive root")
    if not (resolved_game_root / "json").is_dir():
        raise ValueError(f"Game archive root has no json directory: {resolved_game_root}")

    resolved_location_data_root = (
        Path(location_data_root)
        if location_data_root
        else archive_root / LOCATION_DATA_RELATIVE
    )
    resolved_loot_data_root = (
        Path(loot_data_root)
        if loot_data_root
        else archive_root / LOOT_DATA_RELATIVE
    )
    _validate_path(resolved_location_data_root, "LocationData root")
    _validate_path(resolved_loot_data_root, "LootData root")

    return ArchiveSources(
        archive_root=archive_root,
        game_root=resolved_game_root,
        dataset_version=dataset_version,
        location_data_root=resolved_location_data_root,
        loot_data_root=resolved_loot_data_root,
        source=source,
    )


def print_archive_sources(sources: ArchiveSources) -> None:
    print(f"[INFO] Archive root: {sources.archive_root}")
    print(f"[INFO] Archive dataset: {sources.dataset_version}")
    print(f"[INFO] Archive source: {sources.source}")
    print(f"[INFO] Game archive root: {sources.game_root}")
    print(f"[INFO] LocationData root: {sources.location_data_root}")
    print(f"[INFO] LootData root: {sources.loot_data_root}")
