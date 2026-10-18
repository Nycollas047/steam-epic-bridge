from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class DiscoveryResult:
    steam_roots: list[Path] = field(default_factory=list)
    steam_user_ids: list[str] = field(default_factory=list)
    legendary_bins: list[Path] = field(default_factory=list)
    epic_launcher_bins: list[Path] = field(default_factory=list)

    @property
    def preferred_steam_root(self) -> Path | None:
        return self.steam_roots[0] if self.steam_roots else None

    @property
    def preferred_steam_user_id(self) -> str | None:
        return self.steam_user_ids[0] if self.steam_user_ids else None

    @property
    def preferred_legendary_bin(self) -> Path | None:
        return self.legendary_bins[0] if self.legendary_bins else None

    @property
    def preferred_epic_launcher_bin(self) -> Path | None:
        return self.epic_launcher_bins[0] if self.epic_launcher_bins else None


@dataclass(slots=True)
class EpicGame:
    app_name: str
    title: str
    launch_command: str = ""
    install_path: str | None = None
    is_installed: bool = False


@dataclass(slots=True)
class SyncResult:
    created: int = 0
    updated: int = 0
    skipped: int = 0
    planned: int = 0
    removed: int = 0
    artwork_downloaded: int = 0
    missing_artwork: int = 0
    backup_path: Path | None = None
