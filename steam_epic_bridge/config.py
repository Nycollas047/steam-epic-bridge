from __future__ import annotations

import json
import os
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path

from steam_epic_bridge.models import DiscoveryResult


APP_NAME = "Steam Epic Bridge"
APP_ID_PREFIX = "epic-"
SHORTCUT_TAG = "Epic Games"

if os.name == "nt":
    _CONFIG_DIR = Path(os.getenv("APPDATA", "~/AppData/Roaming")).expanduser() / "steam-epic-bridge"
else:
    _CONFIG_DIR = Path(os.getenv("XDG_CONFIG_HOME", "~/.config")).expanduser() / "steam-epic-bridge"
_CONFIG_FILE = _CONFIG_DIR / "config.json"


def _unique_existing(paths: list[Path]) -> list[Path]:
    seen: set[str] = set()
    results: list[Path] = []
    for path in paths:
        try:
            resolved = str(path.resolve())
        except OSError:
            resolved = str(path)
        if resolved in seen or not path.exists():
            continue
        seen.add(resolved)
        results.append(path)
    return results


def find_steam_roots() -> list[Path]:
    candidates: list[Path] = []
    env_value = os.getenv("STEAM_PATH")
    if env_value:
        candidates.append(Path(env_value).expanduser())

    if sys.platform == "win32":
        try:
            import winreg

            for hive, subkey in [
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Wow6432Node\Valve\Steam"),
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam"),
                (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Valve\Steam"),
            ]:
                try:
                    with winreg.OpenKey(hive, subkey) as key:
                        install_path, _ = winreg.QueryValueEx(key, "InstallPath")
                        if install_path:
                            candidates.append(Path(install_path))
                except FileNotFoundError:
                    continue
        except ImportError:
            pass

        candidates.extend(
            [
                Path(os.getenv("PROGRAMFILES(X86)", r"C:\Program Files (x86)")) / "Steam",
                Path(os.getenv("PROGRAMFILES", r"C:\Program Files")) / "Steam",
                Path.home() / "AppData" / "Local" / "Steam",
            ]
        )
    else:
        candidates.extend(
            [
                Path.home() / ".steam" / "steam",
                Path.home() / ".steam" / "root",
                Path.home() / ".local" / "share" / "Steam",
                Path.home() / ".var" / "app" / "com.valvesoftware.Steam" / ".steam" / "steam",
                Path.home() / ".var" / "app" / "com.valvesoftware.Steam" / ".steam" / "root",
                Path.home() / "Library" / "Application Support" / "Steam",
            ]
        )
    return _unique_existing(candidates)


def find_steam_user_ids(steam_root: Path | None = None) -> list[str]:
    roots = [steam_root] if steam_root else find_steam_roots()
    found: list[tuple[str, float]] = []
    for root in roots:
        userdata = root / "userdata"
        if not userdata.exists():
            continue
        try:
            for child in userdata.iterdir():
                if child.is_dir() and child.name.isdigit():
                    found.append((child.name, child.stat().st_mtime))
        except OSError:
            continue

    ordered = sorted(found, key=lambda item: item[1], reverse=True)
    seen: set[str] = set()
    result: list[str] = []
    for user_id, _ in ordered:
        if user_id not in seen:
            seen.add(user_id)
            result.append(user_id)
    return result


def _has_legendary_module() -> bool:
    import importlib.util

    return importlib.util.find_spec("legendary") is not None


def find_legendary_binaries() -> list[Path]:
    candidates: list[Path] = []
    configured = os.getenv("SEB_LEGENDARY_PATH")
    if configured:
        candidates.append(Path(configured))

    for binary_name in ("legendary", "legendary.exe"):
        found = shutil.which(binary_name)
        if found:
            candidates.append(Path(found))

    if sys.platform != "win32":
        candidates.extend(
            [
                Path.home() / ".local" / "bin" / "legendary",
                Path("/usr/bin/legendary"),
                Path("/usr/local/bin/legendary"),
            ]
        )
    return _unique_existing(candidates)


def find_epic_launcher_binaries() -> list[Path]:
    if sys.platform == "win32":
        candidates = [
            Path(os.getenv("PROGRAMFILES(X86)", r"C:\Program Files (x86)"))
            / "Epic Games" / "Launcher" / "Portal" / "Binaries" / "Win64" / "EpicGamesLauncher.exe",
            Path(os.getenv("PROGRAMFILES", r"C:\Program Files"))
            / "Epic Games" / "Launcher" / "Portal" / "Binaries" / "Win64" / "EpicGamesLauncher.exe",
        ]
    else:
        candidates = [
            Path.home() / ".local" / "share" / "com.epicgames.eglv2",
            Path("/usr/bin/epic-games-launcher"),
        ]
    return _unique_existing(candidates)


def discover_environment() -> DiscoveryResult:
    steam_roots = find_steam_roots()
    preferred_root = steam_roots[0] if steam_roots else None
    return DiscoveryResult(
        steam_roots=steam_roots,
        steam_user_ids=find_steam_user_ids(preferred_root),
        legendary_bins=find_legendary_binaries(),
        epic_launcher_bins=find_epic_launcher_binaries(),
    )


def load_config_file() -> dict:
    if not _CONFIG_FILE.exists():
        return {}
    try:
        return json.loads(_CONFIG_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_config_file(data: dict) -> None:
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    _CONFIG_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


@dataclass(slots=True)
class Settings:
    steam_root: Path
    steam_user_id: str | None
    legendary_bin: str
    steamgriddb_api_key: str | None
    debug: bool = False
    prefer_animated: bool = False
    artwork_style: str = "any"
    launch_backend: str = "legendary"
    language: str = "pt-BR"
    discovery: DiscoveryResult = field(default_factory=discover_environment)

    @property
    def is_flatpak_steam(self) -> bool:
        return "com.valvesoftware.Steam" in str(self.steam_root)

    @property
    def userdata_dir(self) -> Path | None:
        if not self.steam_user_id:
            return None
        return self.steam_root / "userdata" / self.steam_user_id

    @property
    def config_dir(self) -> Path | None:
        if not self.userdata_dir:
            return None
        return self.userdata_dir / "config"

    @property
    def shortcuts_path(self) -> Path | None:
        if not self.config_dir:
            return None
        return self.config_dir / "shortcuts.vdf"

    @property
    def grid_dir(self) -> Path | None:
        if not self.config_dir:
            return None
        return self.config_dir / "grid"

    @property
    def log_path(self) -> Path:
        return _CONFIG_DIR / "sync.log"

    @property
    def epic_launcher_bin(self) -> Path | None:
        return self.discovery.preferred_epic_launcher_bin


def get_settings() -> Settings:
    file_config = load_config_file()
    discovery = discover_environment()

    env_steam = os.getenv("STEAM_PATH")
    cfg_steam = file_config.get("steam_root")
    if env_steam:
        steam_root = Path(env_steam).expanduser()
    elif cfg_steam:
        steam_root = Path(cfg_steam).expanduser()
    elif discovery.preferred_steam_root:
        steam_root = discovery.preferred_steam_root
    else:
        steam_root = Path(os.getenv("PROGRAMFILES(X86)", r"C:\Program Files (x86)")) / "Steam"

    forced_uid = os.getenv("SEB_STEAM_USER_ID") or file_config.get("steam_user_id")
    if forced_uid:
        steam_user_id = str(forced_uid)
    else:
        ids = find_steam_user_ids(steam_root)
        steam_user_id = ids[0] if ids else discovery.preferred_steam_user_id

    legendary_bin = (
        os.getenv("SEB_LEGENDARY_PATH")
        or file_config.get("legendary_bin")
        or ("python -m legendary" if _has_legendary_module() else None)
        or (str(discovery.preferred_legendary_bin) if discovery.preferred_legendary_bin else "legendary")
    )

    api_key = os.getenv("STEAMGRIDDB_API_KEY") or file_config.get("steamgriddb_api_key")

    return Settings(
        steam_root=steam_root,
        steam_user_id=steam_user_id,
        legendary_bin=legendary_bin,
        steamgriddb_api_key=api_key,
        debug=os.getenv("SEB_DEBUG", "").strip() in {"1", "true", "TRUE", "yes"},
        prefer_animated=bool(file_config.get("prefer_animated", False)),
        artwork_style=str(file_config.get("artwork_style", "any")),
        launch_backend=str(file_config.get("launch_backend", "legendary")),
        language=str(file_config.get("language", "pt-BR")),
        discovery=discovery,
    )
